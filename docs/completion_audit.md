# Abschlussaudit

Auditdatum: 10. September 2026
Finaler Studien-Run: `study-reproduction-20260910`
Daten-Run: `real-20260910-v2`
Konfigurationshash:
`5dea8ded67b29751daf4a7ca3f186c0dc320e8e6449b9ed94a10127469ede823`

Dieser Audit prüft die ursprünglichen Deliverables gegen aktuelle,
reproduzierbare Evidenz. Ein positives Marktresultat war kein
Erfolgskriterium; gefordert war eine fachlich korrekte Antwort.

## 1. Recherche ähnlicher Projekte

Status: erfüllt.

Evidenz:

- [`literature_review.md`](literature_review.md) vergleicht OpenMarket,
  EventFactorBench, ForecastBench, Polymarket-v1, Kalibrations- und
  Mikrostrukturstudien.
- [`../references.bib`](../references.bib) enthält zitierbare Primärquellen.
- Negative Vergleichsresultate und die Trennung von Forecast Skill,
  Kalibration und Handelsprofitabilität sind ausdrücklich dokumentiert.

## 2. Datensammlung und Speicherung

Status: erfüllt.

Evidenz:

- 2.500 monatlich stratifizierte Gamma-Kandidaten, 1.321 normalisierte binäre
  Märkte und 21.037 CLOB-Preispunkte wurden real abgerufen.
- 849 gepinnte tägliche Polymarket-v1-Parquets mit insgesamt
  13.162.453.866 Byte wurden unter Revision
  `5aa1b9d52316a8b2e789e81c8ae42c7ed532e8aa` verifiziert.
- `data/raw/...` enthält exakte Responses beziehungsweise Quelldateien samt
  URL, Zeit, Status und SHA-256; `data/processed/...` enthält Parquet,
  DuckDB, Manifeste und Ausschlussprotokolle.
- [`data_dictionary.md`](data_dictionary.md) beschreibt Tabellen,
  Zeiteinheiten, Labelquellen, Lizenz und Leakage-Klassifikation.
- [`storage.py`](../src/polymarket_forecast/data/storage.py) unterstützt lokal
  und optional `gs://`; Zugangsdaten werden nicht versioniert.
- Große Rohdaten sind absichtlich Git-ignored. Die gepinnte kleine
  [`real_cohort.parquet`](../tests/fixtures/real_cohort.parquet)-Fixture
  erlaubt Offline-Tests.

## 3. Statistische Analyse und Hypothesen

Status: erfüllt.

Evidenz:

- [`preregistration.md`](preregistration.md) definiert Population,
  Ausschlüsse, Horizonte, Informationsmenge, `H0`, `α = 0,05`,
  Mindestwirkung, Primärtest und Amendments vor Modelltraining.
- Brier Score, Log Loss, Kalibrationsintercept/-steigung, Reliability,
  Sharpness und Murphy-Zerlegung sind implementiert und getestet.
- Die globale Entscheidung ist ein Intersection-Union-Test gegen Markt und
  Kategorie-Basisrate; sekundäre Horizonte werden mit Holm korrigiert.
- Events werden vor dem Split gruppiert; ein Wochenblock-Bootstrap behandelt
  zeitliche Abhängigkeit.

## 4. Experimente, Simulationen und Modelle

Status: erfüllt.

Evidenz:

- 6.015 reale Markt-Horizont-Zeilen wurden erzeugt, davon 1.046 für den
  Primärhorizont und 831 Eventgruppen.
- Drei purged, expandierende Entwicklungsfolds wählten vor dem Holdout ein
  Ensemble aus Textlogistik, strukturiertem Boosting und
  Markt-Residualmodellen.
- Das finale Training nutzte 155 zeitgerecht verfügbare Zeilen; der Holdout
  enthielt 889 Verträge, 675 Eventgruppen und 30 beobachtete Wochen.
- 5.000 Power-/Typ-I-Fehler-Simulationen je Szenario und 9.999
  Bootstrap-Wiederholungen je Primär-/Robustheitstest wurden ausgeführt.
- Vordefinierte Ablationen, alternative Blocklängen, Quellen-/NegRisk-
  Sensitivitäten sowie 1-/30-Tage-Horizonte sind in
  [`../reports/results`](../reports/results/) gespeichert.

## 5. Resultatanalyse

Status: erfüllt; Primärbehauptung nicht bestätigt.

Evidenz:

- Modell-Brier: `0,109657`.
- Markt-Brier: `0,118516`.
- Kategorie-Basisrate-Brier: `0,257787`.
- Eventgewichtete Verbesserung gegen Markt: `0,008859`.
- Einseitiger Markt-p-Wert: `0,0530`.
- Einseitige 95%-Untergrenze: `0,002049`, unter der praktischen
  Mindestwirkung `0,005`.
- Verbesserung gegen Kategorie-Basisrate: `0,148130`, `p = 0,0001`.
- Globaler Intersection-Union-p-Wert: `0,0530`.

Folgerung: Das Modell ist deskriptiv besser und schlägt die Basisrate
deutlich, aber eine Überlegenheit gegenüber Markt *und* Basisrate ist bei
`α = 0,05` nicht nachgewiesen. Diese nicht signifikante Entscheidung wird im
[`final_report_de.md`](../reports/final_report_de.md) ohne Aufrundung oder
nachträgliche Hypothesenänderung erläutert.

## 6. Reproduzierbarkeit und Qualitätsgates

Status: erfüllt.

Evidenz:

- Ein unabhängiger zweiter Trainings-/Evaluationslauf reproduzierte
  Primärtest, Holdout-Prognosen, Modellauswahl, Scores, Power,
  Splitzuweisungen und Sekundäranalysen exakt; siehe
  [`reproducibility.json`](../reports/results/reproducibility.json).
- `ruff check .`: bestanden.
- `mypy src`: bestanden, 20 Module ohne Fehler.
- `pytest --cov=polymarket_forecast`: 18 Tests bestanden, 76 %
  Gesamt-Coverage.
- Die Tests decken reale API-Normalisierung, gepinnte reale
  End-to-end-Fixture, Leakage-Invarianten, Event-Splits, Modelle,
  Bootstrap, Power, Speicherung und Offline-Pipeline ab.
- `git diff --check`: bestanden.
- Die Suche nach `TODO`, `FIXME`, `PLACEHOLDER` und `TBD` in Code,
  Konfiguration und Dokumentation ergab keine Treffer.

## 7. Lieferartefakte

Status: vollständig.

- Ausführbare CLI und Make-Targets für `collect`, `build-dataset`, `train`,
  `power`, `evaluate`, `report` und `run`.
- Gepinnte Abhängigkeiten in [`requirements.lock`](../requirements.lock).
- CI-Gates in [`ci.yml`](../.github/workflows/ci.yml).
- Deutsche Forschungsarbeit, drei beschriftete Plots sowie JSON-/CSV-
  Resultate.
- Interaktives Ergebnis-Canvas mit Primärentscheidung, Robustheit und Power.

Es verbleibt kein erforderliches Implementierungsdeliverable. Eine spätere
prospektive Replikation wäre neue Evidenz, keine fehlende Komponente dieser
retrospektiven Studie.
