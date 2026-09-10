# Präregistriertes Analyseprotokoll

Version: 1.1
Protokoll eingefroren: 10. September 2026, vor dem Ergebnislauf

Amendment 1.1 (vor Modelltraining und ohne Einsicht in Modellresultate):
Die Gamma-API begrenzt Offset-Paginierung. Um statt eines einzelnen kurzen
Zeitfensters mindestens 30 zeitliche Blöcke abzudecken, wird die
konfigurierte Obergrenze gleichmäßig auf Kalendermonate verteilt und je Monat
über den stabilen Keyset-Endpunkt nach `volumeNum` absteigend gezogen. Diese
bewusste Liquiditätsselektion verbessert historische Preisabdeckung, begrenzt
die Zielpopulation aber auf die volumenstärkeren verfügbaren Verträge je
Monat. Grund, Zeitpunkt und Auswirkung werden im Bericht ausgewiesen.
Primärkonfiguration: `configs/study.yaml`

Dieses Dokument legt die konfirmatorische Analyse fest. Spätere technisch
notwendige Abweichungen werden im Ergebnisbericht mit Begründung und
Auswirkung protokolliert. Ergebnisse werden weder zur Wahl des Primärmodells
noch zum Ändern der Primärhypothese verwendet.

## 1. Forschungsfrage und Zielgröße

Kann ein ausschließlich aus damals verfügbaren Informationen trainiertes
Modell den binären Ausgang zukünftiger Polymarket-Verträge probabilistisch
besser vorhersagen als

1. die zeitgleiche vom Markt implizierte Wahrscheinlichkeit und
2. eine aus früher aufgelösten Verträgen geschätzte Basisrate?

Das Ziel ist Prognosequalität, nicht Handelsprofitabilität. Gebühren, Spread,
Slippage, Latenz und Queue-Position sind nicht vollständig modelliert.

Für Vertrag \(c\), Eventgruppe \(g\), Ergebnis \(Y_c\in\{0,1\}\), Modell
\(M\), Baseline \(b\) und Brier Score \(S(p,y)=(p-y)^2\) ist die gepaarte
Verbesserung

\[
d_{c,b}=S(p_{b,c},Y_c)-S(p_{M,c},Y_c).
\]

Positive Werte sind besser für das Modell. Zuerst wird innerhalb jeder
Eventgruppe gemittelt; Eventgruppen erhalten im Primärschätzer gleiches
Gewicht:

\[
\Delta_b = \operatorname{mean}_g\left(
  \operatorname{mean}_{c\in g}d_{c,b}
\right).
\]

## 2. Population und Beobachtungseinheit

Eingeschlossen werden Polymarket-Verträge, die:

- genau die Outcomes `Yes` und `No` besitzen,
- laut Gamma als aufgelöst gekennzeichnet sind,
- einen identifizierbaren YES-CLOB-Token besitzen,
- eine eindeutige binäre Auflösung haben,
- zum Prognosezeitpunkt bereits handelbar waren,
- eine Preisbeobachtung strikt vor dem Prognosezeitpunkt besitzen und
- zwischen dem konfigurierten Studienbeginn und Daten-Cutoff liegen.

Der maximale Abrufumfang beträgt 2.500 Gamma-Märkte. Bei 32
Kalendermonats-Strata werden bis zu 79 nach terminalem Volumen absteigend
sortierte Kandidaten je Monat abgerufen. Terminales Volumen definiert hier
nur die retrospektive Stichprobenpopulation; es ist kein Modellmerkmal.

Ausgeschlossen werden:

- 50/50-, ungültige, stornierte oder widersprüchlich gelabelte Märkte,
- Märkte ohne Event-/Zeitreferenz,
- Preise außerhalb \([0,1]\),
- Verträge, die erst nach dem Prognosezeitpunkt erstellt wurden,
- Preisbeobachtungen nach dem Prognosezeitpunkt,
- Märkte mit einer letzten verfügbaren Preisbeobachtung, die am
  Primärhorizont mehr als sechs Stunden alt ist,
- exakte Duplikate sowie technisch nicht validierbare Datensätze.

Ein Vertrag-Horizont-Paar liefert genau eine Prognose. Verträge desselben
Gamma-Events teilen eine Eventgruppe. Wo Event-IDs fehlen, wird die
`conditionId` als konservative Einzelgruppe verwendet. NegRisk-Verträge
desselben Events bleiben in derselben Gruppe.

## 3. Zeitdefinition und Horizonte

Der Ereignisanker wird in dieser Priorität gewählt:

1. `gameStartTime`,
2. `events[0].startTime`,
3. `events[0].eventDate` (00:00 UTC),
4. `endDate`.

Eine Beobachtung ist nur gültig, wenn ihr Prognose-Cutoff sowohl nach
`createdAt` als auch strikt vor `closedTime` liegt. Damit kann eine
nachträgliche vorzeitige Auflösung nicht als Feature einfließen.

- **Primär:** sieben Tage vor dem Ereignisanker.
- **Sekundär:** 30 Tage und ein Tag vor dem Ereignisanker.

Aus der CLOB-Historie wird die letzte Beobachtung mit
`price_timestamp <= forecast_cutoff` ausgewählt. Trajektorienmerkmale werden
nur aus noch älteren Punkten berechnet.

## 4. Informationsmenge und Leakage-Regeln

Zulässig sind am Cutoff bekannte:

- YES-Marktpreis und vergangene Preisänderungen,
- damaliges beziehungsweise bis dahin beobachtbares Volumen, soweit die
  Quelle einen zeitgerechten Wert liefert,
- Vertragsalter und Zeit bis zum Event,
- Frage, Beschreibung und stabile Kategorie-/Eventinformationen.

Nicht zulässig sind:

- `outcomePrices`, Gewinnerflags oder Auflösungsfelder als Merkmale,
- terminale Best-Bid/Best-Ask- oder Liquiditätsfelder aus einem späteren
  Gamma-Snapshot,
- Preise nach dem Cutoff,
- Labels, die beim Training des jeweiligen Folds noch nicht aufgelöst waren,
- Vorverarbeitung oder Hyperparameterwahl auf Holdout-Daten.

Da historische Gamma-Snapshots nicht für jeden Cutoff verfügbar sind,
werden veränderliche terminale Liquiditäts-/Volumenfelder standardmäßig
nicht als konfirmatorische Features genutzt. Vertragstext und Eventzuordnung
werden als potenziell nachträglich veränderlich markiert; eine
Robustheitsanalyse entfernt alle Textmerkmale.

## 5. Daten-Splits

Eventgruppen werden nach ihrem frühesten Prognose-Cutoff sortiert.

1. Die letzten 20 % der Eventgruppen bilden den unangetasteten
   konfirmatorischen Holdout.
2. Die ersten 80 % bilden die Entwicklungskohorte.
3. Innerhalb der Entwicklungskohorte werden drei chronologische,
   expandierende Validierungsfolds verwendet.
4. Eine Eventgruppe darf nie mehrere Splits berühren.
5. Für jeden Fold werden nur Trainingszeilen zugelassen, deren
   `closed_time` vor dem frühesten Validierungs-Cutoff liegt.
6. Zusätzlich gilt ein 30-Tage-Embargo zwischen Trainingsauflösung und
   Validierungs-Cutoff.

Ist die resultierende konfirmatorische Kohorte zu klein für verlässliche
Inferenz, wird das als unzureichende Evidenz berichtet und nicht durch
nachträgliches Lockern der Regeln verdeckt.

## 6. Baselines und Kandidaten

### Baselines

- **Markt:** letzter zeitgerechter YES-Preis am Cutoff.
- **Globale Climatology:** Laplace-geglättete YES-Rate ausschließlich aus
  zu diesem Zeitpunkt aufgelösten Trainingsdaten.
- **Kategorie-Climatology:** partiell zur globalen Rate geschrumpfte
  historische Kategorie-Rate.
- **Rekalibrierter Markt:** logistische Kalibration des Marktpreises auf
  vergangenen Trainingsdaten.

### Kandidaten

1. regularisierte logistische Regression mit TF-IDF-Text,
   Markt-/Trajektorien- und Zeitmerkmalen,
2. Histogram Gradient Boosting auf strukturierten Merkmalen,
3. Markt-Residualmodell, das eine regularisierte Korrektur zum Logit des
   Marktpreises lernt,
4. Validierungsgewichtetes Ensemble aus den vorstehenden Kandidaten.

Alle Imputer, Encoder, Vektorisierer, Kalibratoren und Hyperparameter werden
innerhalb des jeweiligen Entwicklungsfolds fitten. Das Modell mit dem
niedrigsten eventgewichteten mittleren Validierungs-Brier-Score wird vor der
Holdout-Auswertung gesperrt. Bei Gleichstand gewinnt das einfachere Modell in
der oben genannten Reihenfolge.

Vordefinierte Ablationen: nur Markt, ohne Text, ohne Preisverlauf, ohne
Kategorie und ohne zeitliche Metadaten.

## 7. Hypothesen und Entscheidungsregel

Für Marktbaseline \(P\) und Climatology \(C\):

\[
H_{0P}:\Delta_P\le0,\quad H_{1P}:\Delta_P>0
\]

\[
H_{0C}:\Delta_C\le0,\quad H_{1C}:\Delta_C>0.
\]

Das Signifikanzniveau ist vorab \(\alpha=0{,}05\). Die globale Behauptung
„besser als beide Baselines“ ist eine Intersection-Union-Entscheidung:

\[
p_\mathrm{global}=\max(p_P,p_C).
\]

Sie wird nur erhoben, wenn beide einseitigen p-Werte kleiner als 0,05 und
beide einseitigen 95%-Untergrenzen größer als null sind. Es ist daher keine
Bonferroni-Korrektur für diese konjunktive Primärbehauptung nötig.

Eine Brier-Verbesserung von 0,005 wird als minimale praktisch relevante
Effektgröße (MPE) definiert. „Statistisch besser“ verlangt eine Untergrenze
über null; „praktisch relevant besser“ verlangt zusätzlich eine
Untergrenze über 0,005.

Die Schreibweise `P0 < 0,05` wird nicht verwendet:

- \(H_0\) bezeichnet die Nullhypothese,
- \(\alpha=0{,}05\) die vorab festgelegte Fehlerwahrscheinlichkeit und
- \(p\) den nach der Analyse berechneten p-Wert.

Ein p-Wert ist nicht die Wahrscheinlichkeit, dass \(H_0\) wahr ist.

## 8. Inferenz

Die primäre Unsicherheit wird mit einem deterministischen
Moving-Block-Bootstrap geschätzt:

- zuerst Mittelung je Eventgruppe,
- Zuordnung der Eventgruppen nach Prognose-Cutoff zu UTC-Kalenderwochen,
- gemeinsame Resamples beider Baseline-Differenzen,
- Blocklänge vier Wochen,
- 9.999 Bootstrap-Replikate, Seed aus der Konfiguration,
- einseitige 95%-Untergrenzen und zweiseitige 95%-Intervalle.

Zweiseitige sekundäre Tests über andere Horizonte, Log Loss und benannte
Subgruppen werden mit Holm kontrolliert. Berichtet werden absolute
Brier-Differenz, Brier Skill Score, Log-Loss-Differenz, Kalibration,
Eventanzahl, Vertragsanzahl, Wochenanzahl, fehlende Forecasts und
Fallback-Anteil.

Robustheit:

- Blocklängen 2, 8 und 13 Wochen,
- vertrag- statt eventgewichtete Schätzung,
- nur Standard- beziehungsweise ohne NegRisk-Events,
- ohne Text,
- alternative Preis-Stalenzen,
- Entfernung der größten Eventgruppe,
- 1- und 30-Tage-Horizont.

## 9. Power und Stoppregel

Nur Entwicklungsdaten werden zur Powerplanung verwendet. Nullzentrierte
event-/wochenweise Differenzvektoren werden in Blöcken resampelt und mit
Effekten von 0, 0,0025, 0,005 und 0,01 verschoben. Die Simulation verwendet
die exakt geplante konjunktive Testregel, mindestens 5.000 Wiederholungen je
Szenario und prüft auch Randnullen \((0,\delta)\) und \((\delta,0)\).

Ziel sind mindestens 90 % Power bei einer wahren Verbesserung von 0,005
gegen beide Baselines und mindestens 30 effektive Wochenblöcke. Die
historische Kohorte wird nicht nach Erreichen eines signifikanten Ergebnisses
gestoppt; es werden alle vor dem Daten-Cutoff verfügbaren, regelkonformen
Verträge des konfigurierten Abrufumfangs ausgewertet.

## 10. Sekundäre Metriken

- Log Loss mit vorab festgelegtem Clipping auf
  \([10^{-6},1-10^{-6}]\),
- Kalibration-in-the-large,
- logistische Kalibrationssteigung und -intercept,
- Reliability-Diagramm mit festen Bins,
- Sharpness,
- Murphy-Zerlegung,
- deskriptive Kategorie- und Horizontanalysen.

Accuracy, AUC und simulierte Rendite sind keine primären Endpunkte.

## 11. Aussagegrenzen

Ein positives Ergebnis belegt nur geringeren 7-Tage-Brier-Verlust in der
dokumentierten Population und Periode. Es beweist weder universelle
Zukunftsvorhersage noch Kausalität oder Handelsprofitabilität. Ein negatives
Ergebnis bedeutet „unter diesem Design keine ausreichende Evidenz“, nicht
„Vorhersage ist grundsätzlich unmöglich“. Eine spätere prospektive,
timestamped Replikation bleibt der stärkste externe Test.
