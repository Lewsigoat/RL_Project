from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from polymarket_forecast.config import ProjectConfig, load_config


@pytest.fixture
def small_config(tmp_path: Path) -> ProjectConfig:
    config = load_config("configs/study.yaml")
    return replace(
        config,
        api=replace(
            config.api,
            max_markets=20,
            page_size=10,
            concurrency=2,
            max_retries=1,
        ),
        inference=replace(
            config.inference,
            bootstrap_repetitions=199,
            power_repetitions=200,
        ),
        paths=replace(
            config.paths,
            data_uri=str(tmp_path / "data"),
            artifacts_uri=str(tmp_path / "artifacts"),
            reports_uri=str(tmp_path / "reports"),
        ),
    )
