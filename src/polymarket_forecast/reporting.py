"""Generate plots and the German research report from persisted results."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.storage import ResearchStorage

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _latest_run(storage: ResearchStorage) -> str:
    pointer = storage.read_json("latest.json")
    if not isinstance(pointer, dict) or not pointer.get("study_run_id"):
        raise ValueError("No completed evaluation is available")
    return str(pointer["study_run_id"])


def _save_figure(
    figure: plt.Figure,
    storage: ResearchStorage,
    relative: str,
    export_directory: Path,
) -> Path:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    payload = buffer.getvalue()
    storage.write_bytes(relative, payload)
    export_directory.mkdir(parents=True, exist_ok=True)
    destination = export_directory / Path(relative).name
    destination.write_bytes(payload)
    return destination


def generate_plots(
    config: ProjectConfig,
    *,
    export_directory: str | Path = "reports/results",
) -> list[Path]:
    storage = ResearchStorage(config.paths.reports_uri)
    run_id = _latest_run(storage)
    destination = Path(export_directory)
    paths: list[Path] = []

    metrics = storage.read_parquet(f"{run_id}/system_metrics.parquet").sort_values(
        "event_weighted_brier"
    )
    if not metrics.empty:
        figure, axis = plt.subplots(figsize=(9, 4.8))
        axis.barh(metrics["system"], metrics["event_weighted_brier"])
        axis.invert_yaxis()
        axis.set_title("Eventgewichteter Brier Score im 7-Tage-Holdout")
        axis.set_xlabel("Mittlerer Brier Score (kleiner ist besser)")
        axis.set_ylabel("Prognosesystem")
        axis.grid(axis="x", alpha=0.25)
        figure.text(
            0.01,
            -0.02,
            "Quelle: Polymarket Gamma/CLOB · konfirmatorischer Holdout · "
            "Mittelung zuerst je Event",
            fontsize=8,
        )
        paths.append(
            _save_figure(
                figure,
                storage,
                f"{run_id}/brier_comparison.png",
                destination,
            )
        )

    reliability = storage.read_parquet(f"{run_id}/reliability.parquet")
    reliability = reliability.loc[
        reliability["system"].isin(["model", "market", "category_climatology"])
        & (reliability["count"] > 0)
    ]
    if not reliability.empty:
        figure, axis = plt.subplots(figsize=(6.8, 6))
        for system, group in reliability.groupby("system"):
            axis.plot(
                group["mean_probability"],
                group["observed_rate"],
                marker="o",
                label=str(system),
            )
        axis.plot([0, 1], [0, 1], linestyle="--", color="black", label="ideal")
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.set_title("Reliability im 7-Tage-Holdout")
        axis.set_xlabel("Mittlere vorhergesagte YES-Wahrscheinlichkeit")
        axis.set_ylabel("Beobachteter YES-Anteil")
        axis.legend(title="System")
        axis.grid(alpha=0.25)
        figure.text(
            0.01,
            -0.02,
            "Quelle: Polymarket Gamma/CLOB · feste Wahrscheinlichkeitsbins · "
            "leere Bins ausgelassen",
            fontsize=8,
        )
        paths.append(
            _save_figure(
                figure,
                storage,
                f"{run_id}/reliability.png",
                destination,
            )
        )

    power = storage.read_parquet(f"{run_id}/power_simulation.parquet")
    power = power.loc[power["scenario"].isin(["half_mpe", "minimum_practical_effect", "double_mpe"])]
    if not power.empty:
        figure, axis = plt.subplots(figsize=(8.5, 5))
        for scenario, group in power.groupby("scenario"):
            axis.plot(
                group["sample_weeks"],
                group["joint_rejection_rate"],
                marker="o",
                label=str(scenario),
            )
        axis.axhline(
            config.inference.target_power,
            color="black",
            linestyle="--",
            label=f"Zielpower {config.inference.target_power:.0%}",
        )
        axis.set_ylim(0, 1)
        axis.set_title("Simulierte Power der konjunktiven Primärentscheidung")
        axis.set_xlabel("Anzahl resampelter Kalenderwochen")
        axis.set_ylabel("Wahrscheinlichkeit, beide Nullhypothesen zu verwerfen")
        axis.legend(title="Wahrer Brier-Effekt")
        axis.grid(alpha=0.25)
        figure.text(
            0.01,
            -0.02,
            "Quelle: Entwicklungsfolds · 4-Wochen-Blockresampling · "
            f"{config.inference.power_repetitions:,} Simulationen",
            fontsize=8,
        )
        paths.append(
            _save_figure(
                figure,
                storage,
                f"{run_id}/power_curve.png",
                destination,
            )
        )
    return paths


def _format_number(value: Any, digits: int = 4) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "nicht verfügbar"
    if not np.isfinite(numeric):
        return "nicht verfügbar"
    return f"{numeric:.{digits}f}".replace(".", ",")


def _format_p(value: Any) -> str:
    numeric = float(value)
    if numeric < 0.0001:
        return "< 0,0001"
    return _format_number(numeric, 4)


def _decision_text(primary: dict[str, Any]) -> str:
    if bool(primary["superior_to_both"]):
        if bool(primary["practically_superior_to_both"]):
            return (
                "Das gesperrte Modell ist im vorab definierten Primärtest statistisch "
                "und praktisch relevant besser als beide Baselines."
            )
        return (
            "Das gesperrte Modell ist im Primärtest statistisch besser als beide "
            "Baselines; die vorab definierte praktische Mindestverbesserung wird "
            "jedoch nicht für beide Vergleiche abgesichert."
        )
    return (
        "Die konjunktive Nullhypothese wird nicht verworfen. Unter diesem Design "
        "gibt es keine ausreichende Evidenz, dass das gesperrte Modell sowohl den "
        "Markt als auch die historische Basisrate übertrifft."
    )


def generate_report(
    config: ProjectConfig,
    *,
    report_path: str | Path = "reports/final_report_de.md",
    readme_path: str | Path = "README.md",
) -> Path:
    report_storage = ResearchStorage(config.paths.reports_uri)
    artifact_storage = ResearchStorage(config.paths.artifacts_uri)
    data_storage = ResearchStorage(config.paths.data_uri)
    run_id = _latest_run(report_storage)
    summary = report_storage.read_json(f"{run_id}/evaluation_summary.json")
    primary = report_storage.read_json(f"{run_id}/primary_test.json")
    metrics = report_storage.read_parquet(f"{run_id}/system_metrics.parquet")
    blocks = report_storage.read_parquet(f"{run_id}/block_robustness.parquet")
    slices = report_storage.read_parquet(f"{run_id}/slice_metrics.parquet")
    sensitivity = report_storage.read_parquet(f"{run_id}/sensitivity.parquet")
    ablations = report_storage.read_parquet(f"{run_id}/ablation_metrics.parquet")
    power = report_storage.read_parquet(f"{run_id}/power_simulation.parquet")
    secondary = report_storage.read_parquet(f"{run_id}/secondary_horizons.parquet")
    training = artifact_storage.read_json(f"runs/{run_id}/training_summary.json")
    scoreboard = artifact_storage.read_parquet(
        f"runs/{run_id}/development_scoreboard.parquet"
    )
    data_run_id = str(summary["data_run_id"])
    build = data_storage.read_json(f"processed/{data_run_id}/build_summary.json")
    data_manifest = data_storage.read_json(f"processed/{data_run_id}/manifest.json")

    metric_by_system = metrics.set_index("system")
    model = metric_by_system.loc["model"]
    market = metric_by_system.loc["market"]
    climate = metric_by_system.loc["category_climatology"]
    market_test = primary["market"]
    climate_test = primary["climatology"]
    minimum_power = summary.get("required_weeks_for_target_power")
    power_text = (
        f"Die Simulation schätzt mindestens {minimum_power} Kalenderwochen für "
        f"{config.inference.target_power:.0%} Power bei Δ = "
        f"{config.inference.minimum_practical_effect:.3f}."
        if minimum_power is not None
        else (
            "Die simulierte Power erreicht im untersuchten Wochenraster nicht "
            f"{config.inference.target_power:.0%} bei der Mindestwirkung."
        )
    )
    effective_weeks = int(summary["effective_weeks"])
    week_warning = (
        f"Die {effective_weeks} effektiven Holdout-Wochen liegen unter der "
        f"präregistrierten Zielgröße von {config.inference.minimum_effective_weeks}; "
        "die Inferenz ist daher als vorläufig zu behandeln."
        if effective_weeks < config.inference.minimum_effective_weeks
        else (
            f"Mit {effective_weeks} effektiven Holdout-Wochen ist die "
            "präregistrierte Mindestzahl zeitlicher Einheiten erreicht."
        )
    )

    secondary_lines = []
    for row in secondary.itertuples(index=False):
        if row.status == "ok":
            secondary_lines.append(
                f"- {int(row.horizon_days)} Tage: Modell `{row.selected_model}`, "
                f"{int(row.event_groups)} Events, globaler Holm-korrigierter "
                f"p-Wert {_format_p(getattr(row, 'holm_adjusted_global_p', np.nan))}."
            )
        else:
            secondary_lines.append(
                f"- {int(row.horizon_days)} Tage: nicht belastbar auswertbar "
                f"({getattr(row, 'detail', 'unzureichende Daten')})."
            )
    if not secondary_lines:
        secondary_lines = ["- Keine sekundäre Horizon-Auswertung war verfügbar."]

    best_development = scoreboard.iloc[0]
    source_counts = data_manifest["source_counts"]
    conclusion = _decision_text(primary)
    report = rf"""# Vorhersage binärer Polymarket-Verträge

## Abstract

Diese Arbeit prüft, ob ein datengetriebenes Modell den Ausgang binärer
Polymarket-Verträge sieben Tage vor dem zugrunde liegenden Ereignis besser
prognostiziert als der zeitgleiche Marktpreis und eine ausschließlich aus der
Vergangenheit geschätzte Basisrate. Die Studie verwendet einen
ereignisgruppierten, chronologischen Walk-forward-Entwurf, sperrt die
Modellauswahl vor dem Holdout und bewertet Wahrscheinlichkeiten primär mit dem
Brier Score. Im konfirmatorischen Holdout liegen
{int(summary['holdout_rows'])} Verträge aus
{int(summary['holdout_event_groups'])} Eventgruppen und {effective_weeks}
Kalenderwochen vor. Gewählt wurde `{summary['selected_model']}`.

Der eventgewichtete Brier Score beträgt
{_format_number(model['event_weighted_brier'])} für das Modell,
{_format_number(market['event_weighted_brier'])} für den Markt und
{_format_number(climate['event_weighted_brier'])} für die Kategorie-Basisrate.
{conclusion} Diese Aussage betrifft Forecast Skill, nicht handelbare Rendite.

## 1. Motivation und Forschungsfrage

Prognosemärkte aggregieren verteilte Information, können aber durch geringe
Liquidität, Herdenverhalten, emotionale Reaktionen, Plattformregeln und
regulatorische Zugangsbarrieren verzerrt werden. Die zentrale Frage lautet:

> Verbessert ein ausschließlich mit damals verfügbaren Daten trainiertes Modell
> die probabilistische Vorhersage späterer binärer Vertragsausgänge gegenüber
> sinnvollen, zeitgleichen Baselines?

„Zukunft vorhersagen“ wird hier eng und überprüfbar definiert: geringerer
Out-of-sample-Verlust auf späteren, während der Modellauswahl unangetasteten
Events. Eine wirtschaftliche Handelsstrategie ist nicht Gegenstand des
Primärtests.

## 2. Mathematischer Hintergrund

Für Ergebnis \(Y\\in\\{{0,1\\}}\) und Prognose \(p\\in[0,1]\) gilt

\\[
BS(p,Y)=(p-Y)^2.
\\]

Der Brier Score ist ein *proper scoring rule*: Im Erwartungswert wird eine
ehrliche Wahrscheinlichkeit belohnt. Analysis tritt in der logistischen
Abbildung

\\[
\\operatorname{{logit}}(p)=\\log\\frac{{p}}{{1-p}}
\\]

und in der Optimierung differenzierbarer Verlustfunktionen auf. Integralideen
erscheinen als Erwartungswerte über die unbekannte Ergebnisverteilung;
empirisch werden sie durch Mittelwerte und Resampling approximiert.

Der Vergleichseffekt ist

\\[
\\Delta_b=E_g[\\,BS(p_b,Y)-BS(p_M,Y)\\,],
\\]

wobei zuerst innerhalb zusammengehöriger Verträge und dann gleichgewichtet
über Events \(g\) gemittelt wird. Positive Werte sprechen für das Modell.

## 3. Forschungsstand

Der detaillierte Review steht in
[`docs/literature_review.md`](../docs/literature_review.md). OpenMarket,
ForecastBench, EventFactorBench und Outcome-RL zeigen gemeinsam, dass
zeitliche Splits, matched-time Marktbaselines und veröffentlichte
Nullresultate unverzichtbar sind. Polymarket-v1 und Mikrostrukturarbeiten
zeigen, dass API-Snapshots, Fills und Orderbücher nicht gleichgesetzt werden
dürfen. Domain-spezifische Kalibrationsstudien motivieren Kategorie- und
Horizontanalysen, aber keine nachträgliche Auswahl günstiger Subgruppen.

## 4. Daten und Speicherung

Der Collector hat {int(source_counts['gamma_rows'])} Gamma-Zeilen abgerufen,
{int(source_counts['normalized_markets'])} binäre Märkte normalisiert und
{int(source_counts['price_points'])} CLOB-Preispunkte gespeichert.
{int(source_counts['exclusions'])} Ausschlussprotokolle wurden erzeugt.
Nach Horizont- und Zeitprüfung enthält die Gesamtkohorte
{int(build['cohort_rows'])} Markt-Horizont-Zeilen; davon
{int(build['primary_rows'])} am 7-Tage-Horizont.

Rohantworten wurden unter Run-ID `{data_run_id}` mit URL, Parametern,
UTC-Abrufzeit und SHA-256 gespeichert. Normalisierte Parquets und eine
DuckDB-Datei trennen `markets`, `events`, `price_points`, `resolutions`,
`provenance` und `exclusions`. Große Rohdaten sind nicht Teil von Git. Das
vollständige Schema und die Leakage-Klassifikation stehen in
[`docs/data_dictionary.md`](../docs/data_dictionary.md).

Wichtig: terminales Volumen, terminale Liquidität und Gewinnerfelder sind
keine Modellmerkmale. Preise müssen am oder vor dem individuellen Cutoff
liegen und höchstens {config.study.max_price_staleness_hours} Stunden alt
sein.

## 5. Hypothesen

Für Markt \(P\) und Kategorie-Climatology \(C\) wurden vorab definiert:

\\[
H_{{0P}}:\\Delta_P\\le0,\\quad H_{{0C}}:\\Delta_C\\le0.
\\]

Das Signifikanzniveau ist \(\\alpha=0{str(config.inference.alpha).replace('.', ',')}\).
Die globale Behauptung verlangt die Verwerfung beider Nullhypothesen; ihr
p-Wert ist daher \(\\max(p_P,p_C)\). Die minimale praktisch relevante
Brier-Verbesserung ist
{str(config.inference.minimum_practical_effect).replace('.', ',')}.
`P0 < 0,05` wäre keine korrekte Schreibweise: \(H_0\) bezeichnet die
Nullhypothese, \(\\alpha\) den Schwellenwert und \(p\) den berechneten
p-Wert.

## 6. Modelle und Experiment

Die Entwicklung verglich regularisierte Text-/Metadaten-Logistik,
Gradient Boosting, ein Markt-Residualmodell mit festem Markt-Logit-Offset und
ein validierungsgewichtetes Ensemble. Die Entwicklungssieger-Konfiguration
`{best_development['candidate']}` erzielte einen eventgewichteten
Validierungs-Brier von
{_format_number(best_development['event_weighted_brier'])}. Für die finale
Anpassung standen {int(training['final_train_rows'])} Zeilen zur Verfügung;
erst danach wurde der Holdout ausgewertet.

Der Split ist eventgruppiert. Für jeden Validierungsfold durften nur Labels
verwendet werden, die mindestens {config.study.embargo_days} Tage vor dem
ersten Validierungscutoff bereits aufgelöst waren. Vorverarbeitung,
Textvektorisierung, Imputation und Kalibration wurden pro Fold neu angepasst.

## 7. Primärresultat

Modell gegen Markt:

- mittlere Brier-Verbesserung:
  {_format_number(market_test['mean_brier_improvement'])}
- einseitiger p-Wert: {_format_p(market_test['p_value_one_sided'])}
- einseitige 95%-Untergrenze:
  {_format_number(market_test['lower_bound_one_sided_95'])}
- Brier Skill Score: {_format_number(market_test['brier_skill_score'])}

Modell gegen Kategorie-Basisrate:

- mittlere Brier-Verbesserung:
  {_format_number(climate_test['mean_brier_improvement'])}
- einseitiger p-Wert: {_format_p(climate_test['p_value_one_sided'])}
- einseitige 95%-Untergrenze:
  {_format_number(climate_test['lower_bound_one_sided_95'])}
- Brier Skill Score: {_format_number(climate_test['brier_skill_score'])}

Der globale Intersection-Union-p-Wert beträgt
{_format_p(primary['global_intersection_union_p'])}. {conclusion}

![Eventgewichtete Brier Scores](results/brier_comparison.png)

![Reliability](results/reliability.png)

## 8. Power, Robustheit und Sekundäranalysen

{power_text} {week_warning}

![Powerkurve](results/power_curve.png)

Die Blocklängen-Sensitivität wurde für
{', '.join(str(int(value)) for value in blocks['block_length_weeks'])}
Wochen berechnet. Weitere vorab benannte Prüfungen umfassen nur
CLOB-Winner-Labels, den Ausschluss von NegRisk-Verträgen, das Entfernen der
größten Eventgruppe, Vertragsgewichtung und Modellablationen. Die
maschinenlesbaren Resultate liegen in [`reports/results`](results/).

Sekundäre Horizonte:

{chr(10).join(secondary_lines)}

Subgruppenresultate in `slice_metrics.csv` sind deskriptiv. Sie dürfen nicht
als neue konfirmatorische Hypothesen interpretiert werden.

## 9. Limitationen

1. Die Studie ist ein retrospektiver, zeitgerechter Backtest und keine
   vollständig prospektive Vorhersagekampagne.
2. Die CLOB-Preishistorie ist gesampelt und enthält kein vollständiges
   historisches Orderbuch.
3. Gamma-Metadaten können nachträglich aktualisiert worden sein. Der
   textfreie Robustheitstest reduziert, beseitigt aber nicht jede
   Quellenunsicherheit.
4. Verträge desselben Gamma-Events werden gruppiert; weiter entfernte
   logische Abhängigkeiten können verbleiben.
5. Ein Brier-Vorteil garantiert nach Spread, Gebühren, Slippage und Latenz
   keinen Handelsgewinn.
6. Ein Foundation-Model wurde bewusst nicht als konfirmatorische Komponente
   eingesetzt, um schwer prüfbare Trainingsdatenkontamination zu vermeiden.
7. API-Lücken und strenge Frischekriterien reduzieren die effektive
   Stichprobe. Power und Konfidenzintervalle sind deshalb entscheidender als
   die bloße Vertragsanzahl.

## 10. Schlussfolgerung

{conclusion}

Die fachlich zulässige Aussage ist auf die dokumentierte Population, den
7-Tage-Horizont, den Daten-Cutoff und den gesperrten Modellprozess begrenzt.
Ein nicht signifikantes Resultat beweist nicht \(H_0\); es zeigt fehlende
Evidenz unter der erreichten Power. Der stärkste nächste Test wäre eine
zweite, vorab timestamped prospektive Kohorte ohne erneute Modellauswahl.

## 11. Reproduzierbarkeit

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install -e . --no-deps

# Gesamter Online-Lauf
.venv/bin/polymarket-study run --config configs/study.yaml

# Oder getrennte, auditierbare Schritte
.venv/bin/polymarket-study collect
.venv/bin/polymarket-study build-dataset
.venv/bin/polymarket-study train
.venv/bin/polymarket-study evaluate
.venv/bin/polymarket-study report

# Qualitätsgates
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
```

Konfiguration: `{config.sha256}`  
Daten-Run: `{data_run_id}`  
Studien-Run: `{run_id}`
"""
    report_destination = Path(report_path)
    report_destination.parent.mkdir(parents=True, exist_ok=True)
    report_destination.write_text(report, encoding="utf-8")

    readme = f"""# Polymarket Forecast Study

Reproduzierbare Untersuchung binärer Polymarket-Verträge mit zeitgerechter
Out-of-sample-Validierung.

## Ergebnis

{conclusion}

- Gesperrtes Modell: `{summary['selected_model']}`
- Holdout: {int(summary['holdout_rows'])} Verträge aus
  {int(summary['holdout_event_groups'])} Events
- Modell-Brier: {_format_number(model['event_weighted_brier'])}
- Markt-Brier: {_format_number(market['event_weighted_brier'])}
- Kategorie-Basisrate-Brier: {_format_number(climate['event_weighted_brier'])}
- Globaler Primär-p-Wert: {_format_p(primary['global_intersection_union_p'])}

Der [vollständige deutsche Bericht](reports/final_report_de.md) erklärt
Methodik, Resultate, Power und Grenzen. Das Design wurde vor dem Ergebnislauf
in [`docs/preregistration.md`](docs/preregistration.md) festgelegt.

## Schnellstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install -e . --no-deps
.venv/bin/polymarket-study run --config configs/study.yaml
```

Ein bestehender Daten-Run kann ohne erneuten API-Abruf reproduziert werden:

```bash
.venv/bin/polymarket-study run --no-collect
```

Qualitätsgates:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
```

## Projektstruktur

- `src/polymarket_forecast/`: Collection, Kohorte, Modelle, Inferenz und CLI
- `configs/study.yaml`: eingefrorene Primärkonfiguration
- `docs/`: Forschungsstand, Präregistrierung und Datenwörterbuch
- `reports/final_report_de.md`: vollständige Arbeit
- `reports/results/`: aggregierte, versionierbare Ergebnisartefakte
- `tests/fixtures/`: kleine gepinnte reale Offline-Fixture

Große Rohdaten und Modellartefakte werden reproduzierbar unter `data/` und
`artifacts/` erzeugt, aber nicht in Git eingecheckt.
"""
    Path(readme_path).write_text(readme, encoding="utf-8")
    return report_destination
