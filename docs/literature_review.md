# Forschungsstand: probabilistische Prognosen auf Polymarket

Stand der Recherche: 10. September 2026. Diese Übersicht unterscheidet
Prognosequalität, Kalibration und handelbare Profitabilität. Das sind drei
verschiedene Fragen: Eine gut kalibrierte Wahrscheinlichkeit kann trotzdem
wenig Trennschärfe besitzen, und ein statistisch besserer Forecast kann nach
Spread, Gebühren, Slippage und Latenz unprofitabel sein.

## 1. Theoretische Grundlage

Ein binärer Marktpreis wird häufig als implizite Wahrscheinlichkeit
interpretiert. Für ein Ergebnis \(Y\in\{0,1\}\) und eine Prognose
\(p\in[0,1]\) ist

\[
BS(p,Y)=(p-Y)^2
\]

der Brier Score [@brier1950]. Er ist *strictly proper*: Im Erwartungswert wird
er durch die ehrliche subjektive Wahrscheinlichkeit minimiert. Die
Murphy-Zerlegung trennt Unsicherheit, Resolution und Reliabilität
[@murphy1973]. Für die Forschungsfrage ist deshalb die gepaarte
Brier-Differenz zur zeitgleichen Marktprognose aussagekräftiger als Accuracy
oder eine Trefferquote nach Schwellenwertbildung.

Kalibration beantwortet, ob Ereignisse mit Prognose 0,7 ungefähr in 70 % der
Fälle eintreten. Sie beweist allein keine Überlegenheit gegenüber dem Markt.
Die vorliegende Studie berichtet zusätzlich Log Loss, Kalibrationsintercept
und -steigung, Reliability-Kurven und Sharpness.

## 2. Vergleichbare abgeschlossene Projekte

### OpenMarket

[OpenMarket](https://arxiv.org/abs/2607.26245) ist die methodisch nächste
Referenz für einen vollständigen Walk-forward-Vergleich. Die Arbeit verwendet
559 chronologische Expanding-Window-Fenster, passt Modell und Platt-
Kalibration ausschließlich auf vergangenen Daten an und veröffentlicht
Manifeste mit Quell- und Ingest-Zeitpunkten. Das negative Resultat ist
wissenschaftlich wichtig: Für kurzfristige BTC-Märkte war das Modell mit
einem Brier Score von ungefähr 0,165 schlechter als der Markt mit ungefähr
0,163; auch die simulierte Rendite war negativ. Übernommen werden die
zeitgerechte Modellauswahl, Artefaktmanifeste und die Bereitschaft, ein
Nullresultat zu berichten. Nicht übernommen wird die Beschränkung auf nur
eine Krypto-Marktfamilie.

### EventFactorBench

[EventFactorBench](https://github.com/bihraint-oss/event-factor-bench)
untersucht logisch zusammenhängende BTC-/ETH-Schwellenmärkte mit
chronologischen Entwicklungs-, Validierungs- und Holdout-Splits. Besonders
relevant sind eventbasierte Bootstrap-Einheiten und Kohärenzbedingungen:
mehrere Verträge desselben realen Ereignisses sind keine unabhängigen
Beobachtungen. Das Projekt zeigt zugleich eine Grenze: Ein kurzer
Beobachtungszeitraum und veränderliche terminale Gamma-Labels ersetzen keine
chain-verifizierte Auflösung.

### ForecastBench

[ForecastBench](https://github.com/forecastingresearch/forecastbench)
entwickelt eine dynamische, kontaminationsärmere Infrastruktur für
zeitgestempelte KI-Prognosen [@forecastbench2025]. Die erste Fragenbank
enthielt 915 Polymarket-Fragen. Für diese Arbeit sind insbesondere
matched-time Baselines, Proper Scores und die Trennung zwischen
Entwicklungs- und späteren Fragen relevant. Ein retrospektiver Test eines
Foundation Models kann durch memorisierte Ereignisse verzerrt sein; deshalb
werden hier keine externen LLM-Antworten als konfirmatorisches Primärmodell
verwendet.

### Polymarket-v1

[Polymarket-v1](https://huggingface.co/datasets/TimeSeventeen/Polymarket-v1)
stellt chain-abgeleitete V1-Fills und CTF-Lebenszyklusdaten von November 2022
bis April 2026 als Parquet bereit [@polymarketv1_2026]. Der Datensatz ist eine
wichtige Referenz für Auflösungsprovenienz und Maker-/Taker-Analyse. Er
enthält jedoch kein vollständiges historisches Limit-Orderbuch, endet mit der
V2-Migration und ist für den kompakten Standardlauf dieser Arbeit unnötig
groß. Der implementierte Collector nutzt deshalb offizielle APIs und kann
später durch eine gepinnte Polymarket-v1-Quelle ergänzt werden.

### Domain-spezifische Kalibration

„[Decomposing Crowd Wisdom](https://arxiv.org/abs/2602.19520)“
[@decomposing2026] analysiert hunderte Millionen Trades auf Kalshi und
Polymarket. Die Kalibration hängt systematisch von Domäne, Horizont und
Tradegröße ab. Besonders politische Märkte zeigen eine Kompression in
Richtung 50 %. Das motiviert Kategorien, Zeit bis zum Ereignis und
Marktrekalibration als Merkmale beziehungsweise Ablationen. Es rechtfertigt
aber keine nachträgliche Auswahl jener Kategorie, in der das eigene Modell
am besten aussieht.

### Markt-Mikrostruktur und Ausführung

„[The Anatomy of a Decentralized Prediction
Market](https://arxiv.org/abs/2604.24366)“ [@anatomy2026] zeigt, dass
WebSocket-inferierte Handelsrichtung und chain-basierte Wahrheit erheblich
abweichen können. Arbeiten wie
[honest-backtest](https://github.com/JohanAlvarado/honest-backtest) berichten
zudem, dass positive Papier-Edges nach Queue-, Gebühren- und
Ausführungskorrekturen verschwinden können. Daher testet dieses Projekt
explizit *Forecast Skill*, nicht Handelsprofitabilität. Volumen- und
Preispfadmerkmale werden verwendet; nicht vorhandene historische
Orderbuchtiefe wird nicht erfunden.

### Outcome-RL

„Outcome-based Reinforcement Learning to Predict the Future“
[@outcomerl2025] evaluiert ein Modell an 1.265 Polymarket-Fragen und berichtet
einen schwächeren Brier Score als die matched-time Marktbaseline. Die Arbeit
liefert ein zweites wichtiges Negativbeispiel: Ein komplexeres Trainingsziel
garantiert keine bessere probabilistische Prognose.

## 3. Datenquellen

Die [offizielle API-Dokumentation](https://docs.polymarket.com/api-reference/introduction)
trennt:

1. **Gamma API** für Ereignis- und Marktmetadaten,
2. **CLOB API** für Preishistorie und aktuellen Orderbuchzustand,
3. **Data API** für Markt-/Accountaktivität und
4. **Polygon/CTF-Ereignisse** als autoritative Settlement-Schicht.

Der Collector speichert Rohantwort, Abrufzeit, Parameter und Prüfsumme. Er
verwendet `umaResolutionStatus=resolved`, prüft genau zwei Outcomes, ordnet
den YES-Token über die indexgleichen Arrays `outcomes` und `clobTokenIds` zu
und verwirft 50/50- oder widersprüchliche Auflösungen. Ein terminales
`outcomePrices`-Feld ist allein kein zulässiges Feature.

Für sehr große Replikationen sind Polymarket-v1, Goldsky Turbo oder eine
eigene Polygon-Indizierung sinnvoll. Öffentliche Lesbarkeit ist jedoch keine
pauschale Datenlizenz. Große Rohdaten und Walletdaten werden deshalb nicht
redistribuiert; die Studie versioniert nur kleine Testfixtures,
Quellenmanifeste und aggregierte Resultate.

## 4. Methodische Konsequenzen für diese Studie

- Die Prognoseeinheit ist ein Vertrag an einem vorab festgelegten Horizont;
  die Inferenz- und Split-Einheit ist das zugrunde liegende Ereignis.
- Trainingsdaten dürfen nur Labels enthalten, die zum damaligen Fold-Cutoff
  bereits bekannt waren.
- Marktpreise werden am gleichen Cutoff wie das Modell gemessen.
- Das Primärmodell wird allein auf Entwicklungsfolds ausgewählt und danach
  gesperrt.
- Der Primärtest vergleicht die gepaarte Brier-Verbesserung sowohl mit dem
  Markt als auch mit einer vergangenen Basisrate.
- Zeitliche und eventbezogene Abhängigkeit wird durch Event-Mittelung und
  Wochen-Block-Bootstrap berücksichtigt.
- Ein kleiner p-Wert ersetzt weder Effektgröße noch Konfidenzintervall noch
  Poweranalyse.
- Ein Nullresultat ist eine gültige Antwort. Aus einem nicht signifikanten
  Resultat folgt nicht, dass beide Systeme identisch sind.

## 5. Offene Grenzen

Eine retrospektive Walk-forward-Studie simuliert die damalige
Informationslage, ist aber keine echte prospektive Registrierung. API-
Historien können Lücken oder nachträglich veränderte Metadaten enthalten.
Preishistorien sind Stichproben, kein vollständiger Trade-Tape. Aussagen
gelten daher für die dokumentierte Kohorte, Horizonte und Datenqualität und
nicht automatisch für alle zukünftigen Märkte oder handelbare Strategien.
