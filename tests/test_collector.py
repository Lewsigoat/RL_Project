from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.clients import SourceResponse
from polymarket_forecast.data.collector import collect_markets
from polymarket_forecast.data.storage import ResearchStorage


def _fixture() -> dict[str, Any]:
    return json.loads(Path("tests/fixtures/real_market_snapshot.json").read_text(encoding="utf-8"))


def _response(url: str, payload: Any) -> SourceResponse:
    return SourceResponse(
        url=url,
        parameters={},
        status_code=200,
        retrieved_at=datetime(2026, 9, 10, tzinfo=UTC),
        body=json.dumps(payload, separators=(",", ":")).encode(),
    )


class FakeClient:
    def __init__(self, *_: Any, **__: Any) -> None:
        fixture = _fixture()
        self.gamma = fixture["gamma_market"]
        self.clob = fixture["clob_market"]
        self.prices = fixture["price_history"]

    async def list_closed_markets(self, **_: Any) -> list[SourceResponse]:
        return [_response("https://gamma.test/markets", [self.gamma])]

    async def get_clob_markets(
        self,
        condition_ids: list[str],
    ) -> dict[str, SourceResponse]:
        return {
            condition_ids[0]: _response(
                "https://clob.test/market",
                self.clob,
            )
        }

    async def get_price_histories(
        self,
        requests: dict[str, tuple[str, int, int]],
    ) -> dict[str, SourceResponse]:
        market_id = next(iter(requests))
        return {
            market_id: _response(
                "https://clob.test/prices-history",
                self.prices,
            )
        }


def test_collection_persists_raw_normalized_and_provenance(
    small_config: ProjectConfig,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "polymarket_forecast.data.collector.PolymarketClient",
        FakeClient,
    )
    storage = ResearchStorage(small_config.paths.data_uri)

    summary = collect_markets(small_config, storage, run_id="fixture-run")

    assert summary.normalized_markets == 1
    assert summary.price_points == 16
    assert storage.exists("raw/fixture-run/gamma_pages.jsonl.gz")
    assert storage.exists("processed/fixture-run/markets.parquet")
    assert storage.exists("processed/fixture-run/study.duckdb")
    manifest = storage.read_json("processed/fixture-run/manifest.json")
    assert manifest["config_sha256"] == small_config.sha256
    assert manifest["source_counts"]["normalized_markets"] == 1
