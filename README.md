# Polymarket Forecast Study

Reproduzierbare Untersuchung binärer Polymarket-Verträge mit zeitgerechter
Out-of-sample-Validierung.

## Ergebnis

Die konjunktive Nullhypothese wird nicht verworfen. Unter diesem Design gibt es keine ausreichende Evidenz, dass das gesperrte Modell sowohl den Markt als auch die historische Basisrate übertrifft.

- Gesperrtes Modell: `ensemble`
- Holdout: 889 Verträge aus
  675 Events
- Modell-Brier: 0,1097
- Markt-Brier: 0,1185
- Kategorie-Basisrate-Brier: 0,2578
- Globaler Primär-p-Wert: 0,0530

Der [vollständige deutsche Bericht](reports/final_report_de.md) erklärt
Methodik, Resultate, Power und Grenzen. Das Design wurde vor dem Ergebnislauf
in [`docs/preregistration.md`](docs/preregistration.md) festgelegt.
Ein unabhängiger zweiter Lauf reproduzierte alle entscheidungsrelevanten
Tabellen exakt; der Vergleich steht in
[`reports/results/reproducibility.json`](reports/results/reproducibility.json).

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
