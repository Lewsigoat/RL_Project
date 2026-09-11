# Präregistriertes Analyseprotokoll

## Geltendes Protokoll 2.0: erweiterter 80/20-Lauf

Version: 2.0
Festgelegt: 11. September 2026, vor Erhebung der erweiterten V2-Daten und vor
Training des neuen Modells
Primärkonfiguration: `configs/study.yaml`

Das Protokoll 2.0 ersetzt für den neuen Lauf die Split- und Modellregeln des
Vorgängers. Die bereits veröffentlichten Resultate aus Version 1.3 bleiben
als Entwicklungswissen erhalten. Weil sich die neue historische Testperiode
mit früher inspizierten Ereignissen überschneiden kann, ist der 80/20-Lauf
ein stärkerer retrospektiver Benchmark, aber kein vollständig neuer
konfirmatorischer Nachweis. Eine nach Modellsperre erhobene prospektive
Kohorte bleibt die definitive Bestätigung.

### Forschungsfrage und Primärziel

Kann ein skalierbares Modell mit ausschließlich am Cutoff verfügbaren
Vertrags-, Preis- und Handelsflussdaten den Ausgang späterer binärer
Polymarket-Verträge besser vorhersagen als sowohl der rohe zeitgleiche
Marktpreis als auch eine ausschließlich auf früheren Trainingsdaten
angepasste Marktkalibration?

Primär sind Verträge sieben Tage vor dem festgelegten Ereignisanker. Die
gepaarte, innerhalb logischer Eventgruppen gemittelte
Brier-Verbesserung lautet

\[
\Delta_b=E_g[BS(p_b,Y)-BS(p_M,Y)].
\]

Ein positiver Wert spricht für das Modell. Die Gesamtbehauptung erfordert:

1. einseitig \(p<0{,}05\) gegen den rohen Markt,
2. einseitig \(p<0{,}05\) gegen den past-only kalibrierten Markt,
3. positive einseitige 95%-Untergrenzen beider Effekte,
4. keine wesentliche Verschlechterung von Log Loss oder Kalibration und
5. robuste Richtung in V1-, V2-, Standard- und NegRisk-Sensitivitäten.

Die minimale praktisch relevante Brier-Verbesserung bleibt 0,005. Ein
niedrigerer Testverlust allein ist kein Erfolgsnachweis.

### Corpus und Abdeckung

Der Datenkorpus soll nahezu vollständig sein, nicht jeder Vertrag muss
modellierbar sein:

- V1: gepinnte CC-BY-4.0-Schichten `daily_aligned` und
  `daily_aligned_multi` ab 21. November 2022 bis zur V2-Migration.
- V2: vollständige Gamma-Keyset-Inventarisierung bis zum Daten-Cutoff,
  kanonische Gewinner-/Auflösungsdaten und verfügbare Exchange-Fills.
- Alle bekannten Verträge bleiben im Coverage-Ledger, auch wenn sie keinen
  frischen 1-/7-/30-Tage-Preis besitzen.
- 50/50-, void-, widersprüchliche oder nicht eindeutig aufgelöste Verträge
  werden als Ausschluss protokolliert, nicht still entfernt.
- Vollständige historische Limit-Orderbücher sind nicht Teil des
  Vollständigkeitsanspruchs, da off-chain Resting Orders und Cancels nicht
  aus der Blockchain rekonstruiert werden können.

Zielwerte sind mindestens 95 % Metadaten- und 95 % Labelabdeckung relativ
zum inventarisierten Universum. Preis-/Trade-Abdeckung wird separat
ausgewiesen und ist eine Eigenschaft der Marktaktivität, kein
Collector-Erfolgskriterium.

### Strikter äußerer 80/20-Split

1. Gamma-Event-ID, NegRisk-Parent, logische Familie und
   Frage-Fingerprint werden vor dem Split zu unteilbaren Gruppen verbunden.
2. Gruppen werden nach ihrem ersten Prognose-Cutoff und danach stabil nach
   Gruppen-ID sortiert.
3. Exakt die ersten \(G-\lceil0{,}20G\rceil\) Gruppen bilden Entwicklung und
   Training; exakt die letzten \(\lceil0{,}20G\rceil\) Gruppen bilden den
   Test.
4. Unterschiedliche Gruppengrößen dürfen das Zeilenverhältnis von 80/20
   abweichen lassen; maßgeblich ist das Gruppenverhältnis.
5. Die Mindestzahl von 30 beobachteten Testwochen ist nur ein
   Evidenz-/Power-Gate. Sie darf den Split nicht verschieben.
6. Kein Testscore und keine Testprognose wird während Modellauswahl,
   Kalibration, Ensembling oder Featureauswahl gelesen.

Innerhalb der ersten 80 % werden fünf purged Expanding-Window-Folds
verwendet. Jeder innere Trainingsfold muss mindestens 50 Eventgruppen
enthalten. Trainingslabels müssen mindestens 30 Tage vor dem ersten
Validierungscutoff aufgelöst sein. Imputer, Skalierer, Texttransformation,
Kalibratoren, Hyperparameter und Ensemblegewichte werden pro Fold neu
angepasst.

### Features und Modelle

Zulässig sind nur am Cutoff bekannte Werte: letzter Referenztokenpreis,
Preisänderungen über 1/3/7/14/30 Tage, Volatilität, Range, Tradeanzahl,
as-of Notional, Aktivitäts- und Imbalance-Maße, Staleness-/Missingness-Flags,
Vertragsalter, Kalenderregime, Kategorie, Exchange-Version und
Quellenindikatoren. Terminales Gamma-Volumen, terminale Liquidität,
Gewinnerfelder und post-cutoff Metadaten bleiben verboten.

Kandidaten sind:

- rohe und Platt-/isotonisch kalibrierte Marktbaselines,
- ein past-only Markt–Basisraten-Blend,
- regularisierte Markt-Logit-Offsetmodelle,
- gradientengeboostete Residualmodelle,
- ein separat bewerteter stabiler Text-Embedding-Kandidat und
- ein Ensemble nur bei mindestens 0,001 OOF-Brier-Gewinn gegenüber dem
  besten Einzelresidual.

Die gesperrte Pipeline wird auf allen labelverfügbaren Zeilen der ersten
80 % neu angepasst und genau einmal auf den letzten 20 % ausgewertet.

### Inferenz, Power und Bericht

Der Primärendpunkt ist eventgewichteter Brier Score. Sekundär werden Log
Loss, Kalibrationsintercept/-steigung, Reliability, Sharpness,
vertraggewichtete Effekte, andere Horizonte, Kategorien, Liquidität,
Quelle und NegRisk berichtet. Zeitliche Abhängigkeit wird mit einem
Wochenblock-Bootstrap behandelt; sekundäre Hypothesen werden mit Holm
korrigiert.

Power- und Typ-I-Fehler-Simulationen verwenden ausschließlich innere
Out-of-fold-Residuals und werden vor dem äußeren Test ausgeführt. Falls die
letzten 20 % weniger als 30 beobachtete Wochen oder weniger als 90 %
simulierte Power bei der Mindestwirkung liefern, wird das Resultat als
unterpowert gekennzeichnet; der Split bleibt trotzdem unverändert.

## Archiviertes Protokoll 1.3

Das folgende Protokoll regelt ausschließlich den bereits abgeschlossenen
Vorgängerlauf `study-reproduction-20260910` und darf nicht zur Interpretation
des neuen 80/20-Laufs verwendet werden.

Version: 1.3
Protokoll eingefroren: 10. September 2026, vor dem Ergebnislauf

Amendment 1.1 (vor Modelltraining und ohne Einsicht in Modellresultate):
Die Gamma-API begrenzt Offset-Paginierung. Um statt eines einzelnen kurzen
Zeitfensters mindestens 30 zeitliche Blöcke abzudecken, wird die
konfigurierte Obergrenze gleichmäßig auf Kalendermonate verteilt und je Monat
über den stabilen Keyset-Endpunkt nach `volumeNum` absteigend gezogen. Diese
bewusste Liquiditätsselektion verbessert historische Preisabdeckung, begrenzt
die Zielpopulation aber auf die volumenstärkeren verfügbaren Verträge je
Monat. Grund, Zeitpunkt und Auswirkung werden im Bericht ausgewiesen.

Amendment 1.2 (vor Modelltraining und ohne Einsicht in Modellresultate):
Der Holdout beginnt beim früheren der beiden Zeitpunkte „letzte 20 % der
Eventgruppen“ und „frühester Cutoff, der rückwärts mindestens 30 tatsächlich
beobachtete Prognosewochen umfasst“. Damit kann
stark wachsendes Marktvolumen die letzten 20 % nicht künstlich auf wenige
Wochen verdichten. Die Eventzahl des Holdouts kann dadurch über 20 % liegen;
das Modell erhält entsprechend weniger Entwicklungsdaten.

Amendment 1.3 (vor Modelltraining und ohne Einsicht in Modellresultate):
Die V1-Schicht enthält keinen separaten realen Event-Start. Für diese Zeilen
ist der Ereignisanker deshalb der frühere Zeitpunkt aus `close_at` und
`resolved_at`. Das verhindert, dass ein Cutoff nach einer vorzeitigen
Auflösung liegt, und vermeidet eine künstliche Häufung an administrativen
Jahres-/Monatsenddaten. Diese rückblickend bekannte Auflösungszeit schwächt
die prospektive Interpretation; V2-Zeilen behalten die im Hauptprotokoll
definierte Event-Zeitpriorität. Beide Quellen werden zusätzlich getrennt
berichtet.
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

Für die gepinnte V1-Schicht ohne Event-Start gilt abweichend
`min(close_at, resolved_at)`.

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

1. Mindestens die letzten 20 % der Eventgruppen und mindestens 30
   tatsächlich beobachtete Prognosewochen bilden den unangetasteten
   konfirmatorischen Holdout; der frühere Startzeitpunkt gilt.
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
