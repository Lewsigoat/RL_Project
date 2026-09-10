"""Command-line entry point for every auditable study stage."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from polymarket_forecast.config import load_config
from polymarket_forecast.pipeline import (
    build_dataset,
    collect_data,
    evaluate_study,
    export_result_tables,
    run_power_analysis,
    run_study,
    train_study,
)
from polymarket_forecast.reporting import generate_plots, generate_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polymarket-study",
        description="Reproducible binary Polymarket forecasting study",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        item = subparsers.add_parser(name, help=help_text)
        item.add_argument(
            "--config",
            default="configs/study.yaml",
            help="Path to the frozen YAML configuration",
        )
        return item

    collect_parser = command("collect", "Collect and normalize public API data")
    collect_parser.add_argument("--run-id")

    build_parser = command("build-dataset", "Build leakage-audited horizon rows")
    build_parser.add_argument("--data-run-id")

    train_parser = command("train", "Develop candidates and lock the final model")
    train_parser.add_argument("--data-run-id")
    train_parser.add_argument("--study-run-id")

    power_parser = command("power", "Run development-only power simulations")
    power_parser.add_argument("--study-run-id")

    evaluate_parser = command("evaluate", "Open the holdout and run inference")
    evaluate_parser.add_argument("--study-run-id")

    report_parser = command("report", "Export aggregate results and German report")
    report_parser.add_argument("--study-run-id")
    report_parser.add_argument("--destination", default="reports/results")

    run_parser = command("run", "Execute the complete study")
    run_parser.add_argument(
        "--no-collect",
        action="store_true",
        help="Reuse processed/latest.json instead of calling public APIs",
    )
    run_parser.add_argument("--data-run-id")
    run_parser.add_argument("--study-run-id")
    run_parser.add_argument("--destination", default="reports/results")
    return parser


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict(orient="records")
    if isinstance(value, Path):
        return str(value)
    return value


def _print_result(value: Any) -> None:
    print(
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config)

    if args.command == "collect":
        _print_result(collect_data(config, run_id=args.run_id))
    elif args.command == "build-dataset":
        _print_result(build_dataset(config, data_run_id=args.data_run_id))
    elif args.command == "train":
        _print_result(
            train_study(
                config,
                data_run_id=args.data_run_id,
                study_run_id=args.study_run_id,
            )
        )
    elif args.command == "power":
        _print_result(run_power_analysis(config, study_run_id=args.study_run_id))
    elif args.command == "evaluate":
        _print_result(evaluate_study(config, study_run_id=args.study_run_id))
    elif args.command == "report":
        exported = export_result_tables(config, destination=args.destination)
        plots = generate_plots(config, export_directory=args.destination)
        report = generate_report(config)
        _print_result({"exported": exported, "plots": plots, "report": report})
    elif args.command == "run":
        result = run_study(
            config,
            collect=not args.no_collect,
            data_run_id=args.data_run_id,
            study_run_id=args.study_run_id,
        )
        exported = export_result_tables(config, destination=args.destination)
        plots = generate_plots(config, export_directory=args.destination)
        report = generate_report(config)
        _print_result(
            {
                "evaluation": result,
                "exported": exported,
                "plots": plots,
                "report": report,
            }
        )
    else:  # pragma: no cover - argparse guarantees a known command
        raise AssertionError(f"Unhandled command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
