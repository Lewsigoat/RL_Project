"""Pinned Polymarket-v1 ingestion for pre-V2 historical coverage."""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import httpx
import numpy as np
import pandas as pd

from polymarket_forecast.cohort import COHORT_COLUMNS, audit_cohort
from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.storage import ResearchStorage


@dataclass(frozen=True)
class HistoricalCollectionSummary:
    run_id: str
    dataset_revision: str
    downloaded_files: int
    reused_files: int
    missing_days: int
    total_bytes: int
    manifest_sha256: str


def _dates(start: datetime, end: datetime) -> list[date]:
    current = start.date()
    result: list[date] = []
    while current <= end.date():
        result.append(current)
        current += timedelta(days=1)
    return result


def _dataset_url(config: ProjectConfig, day: date) -> str:
    filename = day.strftime("%Y_%m_%d.parquet")
    historical = config.historical
    return (
        "https://huggingface.co/datasets/"
        f"{historical.repository}/resolve/{historical.revision}/"
        f"{historical.layer}/{filename}"
    )


async def _download_file(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    destination: Path,
) -> dict[str, Any]:
    if destination.exists() and destination.stat().st_size > 0:
        payload = destination.read_bytes()
        return {
            "url": url,
            "path": str(destination),
            "status": "reused",
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    async with semaphore:
        for attempt in range(4):
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code == 404:
                        return {
                            "url": url,
                            "path": str(destination),
                            "status": "missing",
                            "bytes": 0,
                            "sha256": "",
                        }
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                        await asyncio.sleep(2**attempt)
                        continue
                    response.raise_for_status()
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_suffix(".parquet.part")
                    digest = hashlib.sha256()
                    byte_count = 0
                    with temporary.open("wb") as handle:
                        async for chunk in response.aiter_bytes():
                            handle.write(chunk)
                            digest.update(chunk)
                            byte_count += len(chunk)
                    temporary.replace(destination)
                    return {
                        "url": url,
                        "path": str(destination),
                        "status": "downloaded",
                        "bytes": byte_count,
                        "sha256": digest.hexdigest(),
                    }
            except (httpx.HTTPError, OSError) as exc:
                if attempt == 3:
                    return {
                        "url": url,
                        "path": str(destination),
                        "status": "failed",
                        "bytes": 0,
                        "sha256": "",
                        "error": str(exc),
                    }
                await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")


async def collect_historical_v1_async(
    config: ProjectConfig,
    storage: ResearchStorage | None = None,
    *,
    run_id: str,
) -> HistoricalCollectionSummary | None:
    """Download the pinned CC-BY historical daily layer with resume support."""
    if not config.historical.enabled:
        return None
    target = storage or ResearchStorage(config.paths.data_uri)
    if not target.is_local:
        raise ValueError("Polymarket-v1 ingestion currently requires local staging")
    relative_root = f"raw/polymarket_v1/{config.historical.revision}/{config.historical.layer}"
    local_root = target.local_path(relative_root)
    semaphore = asyncio.Semaphore(config.historical.download_concurrency)
    timeout = httpx.Timeout(120, connect=30)
    headers = {"User-Agent": config.api.user_agent}
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        tasks = []
        for day in _dates(config.historical.start_date, config.historical.end_date):
            url = _dataset_url(config, day)
            destination = local_root / day.strftime("%Y_%m_%d.parquet")
            tasks.append(_download_file(client, semaphore, url, destination))
        records = await asyncio.gather(*tasks)

    failures = [record for record in records if record["status"] == "failed"]
    if failures:
        examples = "; ".join(str(record.get("error", "")) for record in failures[:3])
        raise RuntimeError(f"Failed to download {len(failures)} historical files: {examples}")
    manifest = {
        "schema_version": "1",
        "created_at": datetime.now(UTC),
        "run_id": run_id,
        "repository": config.historical.repository,
        "revision": config.historical.revision,
        "layer": config.historical.layer,
        "license": config.historical.license,
        "date_range": {
            "start": config.historical.start_date,
            "end": config.historical.end_date,
        },
        "files": records,
    }
    manifest_hash = target.write_json(
        f"raw/polymarket_v1/{config.historical.revision}/manifest.json",
        manifest,
    )
    return HistoricalCollectionSummary(
        run_id=run_id,
        dataset_revision=config.historical.revision,
        downloaded_files=sum(record["status"] == "downloaded" for record in records),
        reused_files=sum(record["status"] == "reused" for record in records),
        missing_days=sum(record["status"] == "missing" for record in records),
        total_bytes=sum(int(record["bytes"]) for record in records),
        manifest_sha256=manifest_hash,
    )


def collect_historical_v1(
    config: ProjectConfig,
    storage: ResearchStorage | None = None,
    *,
    run_id: str,
) -> HistoricalCollectionSummary | None:
    return asyncio.run(collect_historical_v1_async(config, storage, run_id=run_id))


def _logical_group(slug: str, category: str, event_time: pd.Timestamp) -> str:
    tokens = re.findall(r"[a-z]+", slug.casefold())
    stop = {
        "will",
        "yes",
        "no",
        "by",
        "before",
        "after",
        "above",
        "below",
        "over",
        "under",
        "at",
        "least",
        "more",
        "less",
    }
    core = "-".join(token for token in tokens if token not in stop)
    key = f"{category}|{event_time.date().isoformat()}|{core}"
    return "v1-" + hashlib.sha256(key.encode()).hexdigest()[:20]


def build_historical_v1_cohort(
    config: ProjectConfig,
    storage: ResearchStorage | None = None,
    *,
    run_id: str,
) -> pd.DataFrame:
    """Aggregate daily on-chain fills into matched-time horizon forecasts."""
    if not config.historical.enabled:
        return pd.DataFrame(columns=COHORT_COLUMNS)
    target = storage or ResearchStorage(config.paths.data_uri)
    if not target.is_local:
        raise ValueError("Polymarket-v1 cohort building requires local files")
    root = target.local_path(
        f"raw/polymarket_v1/{config.historical.revision}/{config.historical.layer}"
    )
    files = sorted(root.glob("*.parquet"))
    if not files:
        raise ValueError("No historical Polymarket-v1 files were downloaded")
    glob_path = str(root / "*.parquet").replace("'", "''")
    horizons = ", ".join(f"({int(value)})" for value in config.study.horizons_days)
    staleness_seconds = config.study.max_price_staleness_hours * 3600
    query = f"""
        WITH expanded AS (
            SELECT
                condition_id,
                market_slug,
                category_refined,
                category,
                winning_outcome_label,
                resolution_status,
                opens_at,
                close_at,
                resolved_at,
                block_timestamp,
                p_event,
                h.horizon_days,
                epoch(close_at) - h.horizon_days * 86400 AS cutoff_epoch
            FROM read_parquet('{glob_path}', union_by_name = true)
            CROSS JOIN (VALUES {horizons}) AS h(horizon_days)
            WHERE lower(resolution_status) = 'resolved'
              AND lower(winning_outcome_label) IN ('yes', 'no')
              AND close_at IS NOT NULL
              AND resolved_at IS NOT NULL
              AND p_event BETWEEN 0 AND 1
        ),
        eligible AS (
            SELECT *
            FROM expanded
            WHERE block_timestamp <= cutoff_epoch
              AND block_timestamp >= cutoff_epoch - 7 * 86400
        )
        SELECT
            condition_id AS market_id,
            horizon_days,
            min(opens_at) AS created_at,
            max(close_at) AS event_time,
            max(resolved_at) AS closed_time,
            max(cutoff_epoch) AS cutoff_epoch,
            max(block_timestamp) AS price_epoch,
            arg_max(p_event, block_timestamp) AS market_probability,
            arg_max(p_event, block_timestamp)
                FILTER (WHERE block_timestamp <= cutoff_epoch - 86400)
                AS probability_24h_before,
            arg_min(p_event, block_timestamp) AS earliest_probability_7d,
            avg(p_event) AS price_mean_7d,
            stddev_pop(p_event) AS price_std_7d,
            min(p_event) AS price_min_7d,
            max(p_event) AS price_max_7d,
            count(*) AS history_points_7d,
            arg_max(market_slug, block_timestamp) AS market_slug,
            arg_max(coalesce(category_refined, category, 'unknown'), block_timestamp)
                AS category,
            arg_max(winning_outcome_label, block_timestamp) AS winning_outcome_label
        FROM eligible
        GROUP BY condition_id, horizon_days
        HAVING max(cutoff_epoch) - max(block_timestamp) <= {staleness_seconds}
           AND min(opens_at) <= to_timestamp(max(cutoff_epoch))
           AND max(resolved_at) > to_timestamp(max(cutoff_epoch))
    """
    connection = duckdb.connect()
    try:
        aggregate = connection.execute(query).fetch_df()
    finally:
        connection.close()
    if aggregate.empty:
        return pd.DataFrame(columns=COHORT_COLUMNS)

    aggregate["created_at"] = pd.to_datetime(aggregate["created_at"], utc=True)
    aggregate["event_time"] = pd.to_datetime(aggregate["event_time"], utc=True)
    aggregate["closed_time"] = pd.to_datetime(aggregate["closed_time"], utc=True)
    aggregate["forecast_cutoff"] = pd.to_datetime(aggregate["cutoff_epoch"], unit="s", utc=True)
    aggregate["price_timestamp"] = pd.to_datetime(aggregate["price_epoch"], unit="s", utc=True)
    probability = aggregate["market_probability"].astype(float)
    clipped = np.clip(probability, config.model.probability_clip, 1 - config.model.probability_clip)
    text = aggregate["market_slug"].fillna("").str.replace("-", " ", regex=False)
    category = aggregate["category"].fillna("unknown").astype(str).str.lower()
    cohort = pd.DataFrame(
        {
            "market_id": aggregate["market_id"].astype(str),
            "event_id": aggregate["market_id"].astype(str),
            "event_group_id": [
                _logical_group(slug, cat, event_time)
                for slug, cat, event_time in zip(
                    aggregate["market_slug"].fillna("").astype(str),
                    category,
                    aggregate["event_time"],
                    strict=True,
                )
            ],
            "question_fingerprint": [
                hashlib.sha256(value.encode()).hexdigest()[:16] for value in text
            ],
            "horizon_days": aggregate["horizon_days"].astype(int),
            "forecast_cutoff": aggregate["forecast_cutoff"],
            "price_timestamp": aggregate["price_timestamp"],
            "price_age_hours": (
                aggregate["forecast_cutoff"] - aggregate["price_timestamp"]
            ).dt.total_seconds()
            / 3600,
            "market_probability": probability,
            "market_logit": np.log(clipped / (1 - clipped)),
            "price_return_24h": probability - aggregate["probability_24h_before"].astype(float),
            "price_return_7d": probability - aggregate["earliest_probability_7d"].astype(float),
            "price_mean_7d": aggregate["price_mean_7d"].astype(float),
            "price_std_7d": aggregate["price_std_7d"].astype(float).fillna(0),
            "price_min_7d": aggregate["price_min_7d"].astype(float),
            "price_max_7d": aggregate["price_max_7d"].astype(float),
            "history_points_7d": aggregate["history_points_7d"].astype(float),
            "contract_age_days": (
                aggregate["forecast_cutoff"] - aggregate["created_at"]
            ).dt.total_seconds()
            / 86400,
            "time_to_event_days": aggregate["horizon_days"].astype(float),
            "question_length": text.str.len().astype(float),
            "description_length": 0.0,
            "text": text,
            "category": category,
            "neg_risk": False,
            "label": aggregate["winning_outcome_label"]
            .astype(str)
            .str.casefold()
            .eq("yes")
            .astype(int),
            "label_source": "polymarket_v1_chain_aligned",
            "created_at": aggregate["created_at"],
            "event_time": aggregate["event_time"],
            "closed_time": aggregate["closed_time"],
        },
        columns=COHORT_COLUMNS,
    )
    cohort = cohort.drop_duplicates(["market_id", "horizon_days"]).sort_values(
        ["forecast_cutoff", "event_group_id", "market_id"]
    )
    cohort = cohort.reset_index(drop=True)
    audit_cohort(cohort, config)
    target.write_parquet(
        f"processed/{run_id}/historical_cohort.parquet",
        cohort,
    )
    target.write_json(
        f"processed/{run_id}/historical_summary.json",
        {
            "dataset": config.historical.repository,
            "revision": config.historical.revision,
            "license": config.historical.license,
            "files": len(files),
            "cohort_rows": len(cohort),
            "markets": int(cohort["market_id"].nunique()),
            "event_groups": int(cohort["event_group_id"].nunique()),
            "horizons": sorted(int(value) for value in cohort["horizon_days"].unique()),
        },
    )
    return cohort
