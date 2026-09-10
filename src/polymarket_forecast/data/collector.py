"""End-to-end acquisition of a versioned Polymarket research snapshot."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

import pandas as pd

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.clients import PolymarketClient, SourceResponse
from polymarket_forecast.data.normalize import normalize_market, normalize_price_history
from polymarket_forecast.data.schemas import (
    Exclusion,
    MarketRecord,
    PricePoint,
    ProvenanceRecord,
)
from polymarket_forecast.data.storage import ResearchStorage


@dataclass(frozen=True)
class CollectionSummary:
    run_id: str
    gamma_rows: int
    normalized_markets: int
    price_points: int
    excluded_rows: int
    clob_crosschecks: int
    config_sha256: str
    manifest_sha256: str


def _safe_json_object(response: SourceResponse) -> Mapping[str, Any]:
    if response.status_code == 404:
        return {}
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object from {response.request_url}")
    return {str(key): value for key, value in payload.items()}


def _provenance(artifact: str, response: SourceResponse) -> ProvenanceRecord:
    return ProvenanceRecord(
        artifact=artifact,
        source_url=response.url,
        retrieved_at=response.retrieved_at,
        sha256=hashlib.sha256(response.body).hexdigest(),
        byte_count=len(response.body),
        parameters_json=json.dumps(
            dict(response.parameters),
            sort_keys=True,
            separators=(",", ":"),
        ),
        status_code=response.status_code,
    )


def _raw_response_row(response: SourceResponse) -> dict[str, Any]:
    return {
        "url": response.url,
        "parameters": dict(response.parameters),
        "status_code": response.status_code,
        "retrieved_at": response.retrieved_at,
        "sha256": hashlib.sha256(response.body).hexdigest(),
        "body_utf8": response.body.decode("utf-8", errors="replace"),
    }


def _records_frame(records: list[Any], columns: list[str] | None = None) -> pd.DataFrame:
    rows = [record.to_dict() for record in records]
    return pd.DataFrame(rows, columns=columns)


async def collect_markets_async(
    config: ProjectConfig,
    storage: ResearchStorage | None = None,
    *,
    run_id: str | None = None,
) -> CollectionSummary:
    """Collect, validate, normalize, and persist a complete study snapshot."""
    target = storage or ResearchStorage(config.paths.data_uri)
    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_prefix = f"raw/{resolved_run_id}"
    normalized_prefix = f"processed/{resolved_run_id}"
    target.makedirs(raw_prefix)
    target.makedirs(normalized_prefix)

    client = PolymarketClient(config.api)
    gamma_responses = await client.list_closed_markets(
        end_date_min=config.study.study_start,
        end_date_max=config.study.data_cutoff,
    )
    provenance: list[ProvenanceRecord] = []
    gamma_rows: list[Mapping[str, Any]] = []
    for page_index, response in enumerate(gamma_responses):
        provenance.append(_provenance(f"gamma_page_{page_index:04d}", response))
        payload = response.json()
        if not isinstance(payload, list):
            raise TypeError("Gamma page must contain an array")
        gamma_rows.extend(
            {str(key): value for key, value in row.items()}
            for row in payload
            if isinstance(row, dict)
        )
    target.write_jsonl_gz(
        f"{raw_prefix}/gamma_pages.jsonl.gz",
        (_raw_response_row(response) for response in gamma_responses),
    )

    deduplicated: dict[str, Mapping[str, Any]] = {}
    pre_exclusions: list[Exclusion] = []
    for raw in gamma_rows:
        market_id = str(raw.get("id") or "")
        condition_id = str(raw.get("conditionId") or "")
        if not market_id or not condition_id:
            pre_exclusions.append(
                Exclusion(market_id=market_id or "unknown", reason="missing_identifier")
            )
            continue
        if market_id in deduplicated:
            pre_exclusions.append(Exclusion(market_id=market_id, reason="duplicate_market"))
            continue
        deduplicated[market_id] = raw

    condition_ids = [str(raw["conditionId"]) for raw in deduplicated.values()]
    clob_responses = await client.get_clob_markets(condition_ids)
    target.write_jsonl_gz(
        f"{raw_prefix}/clob_markets.jsonl.gz",
        (_raw_response_row(response) for response in clob_responses.values()),
    )
    provenance.extend(
        _provenance(f"clob_market_{condition_id}", response)
        for condition_id, response in clob_responses.items()
    )

    markets: list[MarketRecord] = []
    exclusions = list(pre_exclusions)
    for market_id, raw in deduplicated.items():
        condition_id = str(raw["conditionId"])
        response = clob_responses.get(condition_id)
        clob_payload = _safe_json_object(response) if response is not None else {}
        record, exclusion = normalize_market(raw, clob_payload)
        if exclusion is not None:
            exclusions.append(exclusion)
            continue
        if record is None:
            exclusions.append(Exclusion(market_id=market_id, reason="unknown_normalization_error"))
            continue
        if not config.study.include_neg_risk and record.neg_risk:
            exclusions.append(Exclusion(market_id=market_id, reason="neg_risk_excluded"))
            continue
        if not config.study.study_start <= record.event_time <= config.study.data_cutoff:
            exclusions.append(
                Exclusion(market_id=market_id, reason="event_time_outside_study_window")
            )
            continue
        if record.closed_time > config.study.data_cutoff:
            exclusions.append(
                Exclusion(market_id=market_id, reason="resolution_after_data_cutoff")
            )
            continue
        markets.append(record)

    max_horizon = max(config.study.horizons_days)
    history_requests: dict[str, tuple[str, int, int]] = {}
    for market in markets:
        start = max(
            market.created_at,
            market.event_time
            - timedelta(days=max(max_horizon, config.api.history_lookback_days)),
        )
        end = min(market.event_time, market.closed_time, config.study.data_cutoff)
        if start >= end:
            exclusions.append(
                Exclusion(market_id=market.market_id, reason="empty_history_window")
            )
            continue
        history_requests[market.market_id] = (
            market.yes_token_id,
            int(start.timestamp()),
            int(end.timestamp()),
        )

    price_responses = await client.get_price_histories(history_requests)
    target.write_jsonl_gz(
        f"{raw_prefix}/price_histories.jsonl.gz",
        (_raw_response_row(response) for response in price_responses.values()),
    )
    provenance.extend(
        _provenance(f"price_history_{market_id}", response)
        for market_id, response in price_responses.items()
    )

    price_points: list[PricePoint] = []
    for market_id, response in price_responses.items():
        market = next(item for item in markets if item.market_id == market_id)
        payload = _safe_json_object(response)
        points, point_exclusions = normalize_price_history(
            market_id,
            market.yes_token_id,
            payload,
        )
        if not points:
            exclusions.append(Exclusion(market_id=market_id, reason="empty_price_history"))
        price_points.extend(points)
        exclusions.extend(point_exclusions)

    market_frame = _records_frame(markets)
    price_frame = _records_frame(price_points)
    exclusion_frame = _records_frame(exclusions, ["market_id", "reason", "detail"])
    provenance_frame = _records_frame(provenance)

    event_frame = (
        market_frame.groupby("event_id", as_index=False)
        .agg(
            event_time=("event_time", "min"),
            category=("category", "first"),
            market_count=("market_id", "nunique"),
            earliest_created_at=("created_at", "min"),
            latest_closed_time=("closed_time", "max"),
        )
        .sort_values(["event_time", "event_id"])
        if not market_frame.empty
        else pd.DataFrame(
            columns=[
                "event_id",
                "event_time",
                "category",
                "market_count",
                "earliest_created_at",
                "latest_closed_time",
            ]
        )
    )
    resolution_frame = (
        market_frame[
            [
                "market_id",
                "condition_id",
                "question_id",
                "label",
                "label_source",
                "closed_time",
                "raw_sha256",
            ]
        ].copy()
        if not market_frame.empty
        else pd.DataFrame(
            columns=[
                "market_id",
                "condition_id",
                "question_id",
                "label",
                "label_source",
                "closed_time",
                "raw_sha256",
            ]
        )
    )

    tables = {
        "events": event_frame,
        "markets": market_frame,
        "price_points": price_frame,
        "resolutions": resolution_frame,
        "provenance": provenance_frame,
        "exclusions": exclusion_frame,
    }
    table_hashes = {
        table_name: target.write_parquet(
            f"{normalized_prefix}/{table_name}.parquet",
            frame,
        )
        for table_name, frame in tables.items()
    }
    if target.is_local:
        target.materialize_duckdb(f"{normalized_prefix}/study.duckdb", tables)

    manifest = {
        "schema_version": "1",
        "run_id": resolved_run_id,
        "created_at": datetime.now(UTC),
        "config": config.canonical_dict,
        "config_sha256": config.sha256,
        "source_counts": {
            "gamma_rows": len(gamma_rows),
            "deduplicated_gamma_markets": len(deduplicated),
            "clob_crosschecks": len(clob_responses),
            "normalized_markets": len(markets),
            "price_points": len(price_points),
            "exclusions": len(exclusions),
        },
        "table_sha256": table_hashes,
        "raw_artifacts": {
            "gamma_pages": f"{raw_prefix}/gamma_pages.jsonl.gz",
            "clob_markets": f"{raw_prefix}/clob_markets.jsonl.gz",
            "price_histories": f"{raw_prefix}/price_histories.jsonl.gz",
        },
        "notes": [
            "Final volume/liquidity are audit fields and are not eligible model features.",
            "Gamma terminal prices are labels only, never features.",
            "Public API access does not imply permission to redistribute bulk raw data.",
        ],
    }
    manifest_hash = target.write_json(f"{normalized_prefix}/manifest.json", manifest)
    target.write_json(
        "processed/latest.json",
        {
            "run_id": resolved_run_id,
            "manifest": f"{normalized_prefix}/manifest.json",
            "manifest_sha256": manifest_hash,
        },
    )
    return CollectionSummary(
        run_id=resolved_run_id,
        gamma_rows=len(gamma_rows),
        normalized_markets=len(markets),
        price_points=len(price_points),
        excluded_rows=len(exclusions),
        clob_crosschecks=len(clob_responses),
        config_sha256=config.sha256,
        manifest_sha256=manifest_hash,
    )


def collect_markets(
    config: ProjectConfig,
    storage: ResearchStorage | None = None,
    *,
    run_id: str | None = None,
) -> CollectionSummary:
    """Synchronous wrapper used by the command-line interface."""
    return asyncio.run(collect_markets_async(config, storage, run_id=run_id))
