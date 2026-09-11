from __future__ import annotations

from pathlib import Path

import pandas as pd

from polymarket_forecast.config import load_config
from polymarket_forecast.data.storage import ResearchStorage


def test_configuration_is_typed_and_hash_is_stable() -> None:
    first = load_config("configs/study.yaml")
    second = load_config("configs/study.yaml")

    assert first.study.primary_horizon_days == 7
    assert first.inference.alpha == 0.05
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64


def test_local_storage_round_trip_and_duckdb(tmp_path: Path) -> None:
    storage = ResearchStorage(str(tmp_path / "research"))
    frame = pd.DataFrame(
        {
            "market_id": ["a", "b"],
            "probability": [0.25, 0.75],
        }
    )

    json_hash = storage.write_json("manifest.json", {"version": 1})
    parquet_hash = storage.write_parquet("tables/markets.parquet", frame)
    storage.write_jsonl_gz("raw/rows.jsonl.gz", [{"id": 1}, {"id": 2}])
    database = storage.materialize_duckdb("tables/study.duckdb", {"markets": frame})

    assert len(json_hash) == 64
    assert len(parquet_hash) == 64
    assert storage.read_json("manifest.json") == {"version": 1}
    pd.testing.assert_frame_equal(storage.read_parquet("tables/markets.parquet"), frame)
    assert storage.read_jsonl_gz("raw/rows.jsonl.gz") == [{"id": 1}, {"id": 2}]
    assert database.exists()
