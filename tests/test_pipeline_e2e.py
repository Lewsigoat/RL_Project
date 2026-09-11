from __future__ import annotations

from pathlib import Path

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.storage import ResearchStorage
from polymarket_forecast.pipeline import (
    build_dataset,
    evaluate_study,
    export_result_tables,
    train_study,
)
from polymarket_forecast.reporting import generate_plots, generate_report
from tests.factories import synthetic_source_frames


def test_offline_end_to_end_pipeline(
    small_config: ProjectConfig,
    tmp_path: Path,
) -> None:
    markets, prices = synthetic_source_frames(event_count=60, contracts_per_event=2)
    storage = ResearchStorage(small_config.paths.data_uri)
    data_run = "offline-fixture"
    prefix = f"processed/{data_run}"
    storage.write_parquet(f"{prefix}/markets.parquet", markets)
    storage.write_parquet(f"{prefix}/price_points.parquet", prices)
    storage.write_json(
        f"{prefix}/manifest.json",
        {
            "source_counts": {
                "gamma_rows": len(markets),
                "normalized_markets": len(markets),
                "price_points": len(prices),
                "exclusions": 0,
            }
        },
    )
    storage.write_json("processed/latest.json", {"run_id": data_run})

    build = build_dataset(small_config, data_run_id=data_run)
    training = train_study(
        small_config,
        data_run_id=data_run,
        study_run_id="offline-study",
    )
    evaluation = evaluate_study(
        small_config,
        study_run_id=training.study_run_id,
    )
    destination = tmp_path / "exported"
    exported = export_result_tables(small_config, destination=destination)
    plots = generate_plots(small_config, export_directory=destination)
    report = generate_report(
        small_config,
        report_path=tmp_path / "final_report_de.md",
        readme_path=tmp_path / "README.md",
    )

    assert build.primary_rows == 120
    assert evaluation.holdout_rows > 0
    assert evaluation.holdout_event_groups > 0
    assert exported
    assert len(plots) == 3
    assert report.exists()
    assert "Primärresultat" in report.read_text(encoding="utf-8")
