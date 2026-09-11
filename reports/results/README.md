# Versionierte Ergebnisartefakte

Studien-Run: `study-20260910-v13`
Daten-Run: `real-20260910-v2`
Konfigurationshash:
`5dea8ded67b29751daf4a7ca3f186c0dc320e8e6449b9ed94a10127469ede823`

Diese Dateien enthalten ausschließlich aggregierte Resultate und Plots,
keine großen Rohdaten oder Walletinformationen.

- `evaluation_summary.json`: kompakte Primärentscheidung.
- `primary_test.json`: Effektgrößen, Intervalle und p-Werte beider
  Primärvergleiche.
- `system_metrics.csv`: Proper Scores und Kalibrationsdiagnostik je System.
- `block_robustness.csv`: Wochenblock-Sensitivität.
- `sensitivity.csv`: vordefinierte Kohorten-/Gewichtungsprüfungen.
- `ablation_metrics.csv`: Entfernung einzelner Merkmalsgruppen.
- `power_simulation.csv`: Typ-I-Fehler- und Power-Szenarien.
- `secondary_horizons.csv`: Holm-korrigierte 1-/30-Tage-Ergebnisse.
- `slice_metrics.csv`: rein deskriptive Kategorie- und Quellen-Slices.
- `brier_comparison.png`, `reliability.png`, `power_curve.png`: Abbildungen
  des deutschen Berichts.
- `manifest.json`: Run-, Konfigurations- und Exportprovenienz.
- `reproducibility.json`: exakter Vergleich des Primär- und unabhängigen
  Reproduktionslaufs.
- `trading/`: post-hoc Excess-Return-Simulation nach Spread und Gebühr.
  Nicht Teil des präregistrierten Brier-Tests.

Die fachliche Interpretation steht in
[`../final_report_de.md`](../final_report_de.md). Der Primärtest ist nicht
signifikant: globaler Intersection-Union-p-Wert `0.0530`. Die
Handels-Simulation steht in
[`../excess_return_simulation.md`](../excess_return_simulation.md).
