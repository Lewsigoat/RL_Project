# Datenwörterbuch und Provenienz

## Speicherlayout

Der Standardpfad ist `data/`; alternativ kann `paths.data_uri` auf ein
`gs://`-Präfix zeigen. Jeder Abruf erzeugt eine unveränderliche Run-ID:

```text
data/
├── raw/<run_id>/
│   ├── gamma_pages.jsonl.gz
│   ├── clob_markets.jsonl.gz
│   └── price_histories.jsonl.gz
└── processed/<run_id>/
    ├── events.parquet
    ├── markets.parquet
    ├── price_points.parquet
    ├── resolutions.parquet
    ├── provenance.parquet
    ├── exclusions.parquet
    ├── study.duckdb
    └── manifest.json
```

`processed/latest.json` ist nur ein Pointer auf den letzten Run. Jede
Rohzeile enthält Request-URL, Parameter, UTC-Abrufzeit, HTTP-Status, SHA-256
und den unveränderten UTF-8-Responsebody. Das Manifest enthält zusätzlich
Konfigurationshash, Tabellenhashes und Zeilenzahlen.

Rohdaten, Walletdaten und große Parquets werden nicht in Git versioniert.
Kleine reale Testfixtures, Manifeste und aggregierte Resultate dürfen
versioniert werden, sofern Quelle und Lizenzhinweis erhalten bleiben.

## Tabelle `markets`

| Feld | Typ | Bedeutung | Modellzulässig |
|---|---|---|---|
| `market_id` | String | Gamma-Markt-ID | nur Schlüssel |
| `event_id` | String | Gamma-Event-ID; Fallback `condition_id` | Gruppierung |
| `condition_id` | Hex-String | CTF-Condition | nur Provenienz |
| `question_id` | Hex-String | Oracle-/Question-ID | nur Provenienz |
| `slug` | String | stabiler lesbarer Marktbezeichner | nein |
| `question` | String | binäre Marktfrage | ja, mit Leakage-Warnung |
| `description` | String | Auflösungsregeln/Beschreibung | ja, mit Leakage-Warnung |
| `category` | String | erster dokumentierter Tag | ja |
| `yes_token_id` | Dezimalstring | CLOB-Asset für YES | nur Join |
| `no_token_id` | Dezimalstring | CLOB-Asset für NO | nur Join |
| `created_at` | UTC Timestamp | Erstellzeit laut Gamma | ja |
| `event_time` | UTC Timestamp | priorisierter Ereignisanker | ja |
| `end_date` | UTC Timestamp | angekündigtes Enddatum | ja |
| `closed_time` | UTC Timestamp | tatsächliche Schließung/Auflösung | Split/Label, nicht Feature |
| `source_updated_at` | UTC Timestamp | letzter Gamma-Updatezeitpunkt | Audit, nicht Feature |
| `label` | Integer 0/1 | 1 = YES, 0 = NO | Zielvariable |
| `label_source` | String | `clob_winner_crosschecked_gamma` oder dokumentierter Fallback | Audit |
| `neg_risk` | Boolean | Teil eines NegRisk-Ereignisses | Robustheit/Gruppierung |
| `final_volume` | Float | terminaler Gamma-Wert | **nein**, Zukunftsinformation |
| `final_liquidity` | Float | terminaler Gamma-Wert | **nein**, Zukunftsinformation |
| `raw_sha256` | Hex-String | Hash des kanonischen Gamma-Objekts | Audit |

## Tabelle `price_points`

| Feld | Typ | Bedeutung |
|---|---|---|
| `market_id` | String | Join zu `markets` |
| `token_id` | Dezimalstring | YES-CLOB-Token |
| `timestamp` | UTC Timestamp | CLOB-Feld `t`, Unixsekunden |
| `price` | Float [0,1] | gesampelte implizite YES-Wahrscheinlichkeit |
| `source` | String | `clob_prices_history` |

Der CLOB-Endpunkt liefert eine gesampelte Historie, keinen vollständigen
Trade-Tape und kein historisches Orderbuch. Für jeden Horizont wird nur die
letzte Zeile mit `timestamp <= forecast_cutoff` verwendet. Eine zu alte
Beobachtung wird gemäß Protokoll ausgeschlossen.

## Tabelle `events`

Eine aggregierte Index-Tabelle mit `event_id`, `event_time`, `category`,
`market_count`, frühester Erstellung und spätester Schließung. Sie ist die
primäre Split- und Inferenzebene. Verträge innerhalb eines Events gelten
nicht als unabhängig.

## Tabelle `resolutions`

Separiert Ziel und Auflösungsprovenienz von den Merkmalen:
`market_id`, `condition_id`, `question_id`, `label`, `label_source`,
`closed_time`, `raw_sha256`.

Eine eindeutige CLOB-Winner-Markierung hat Vorrang. Das normalisierte Label
wird gegen terminale Gamma-Preise geprüft, sofern beide vorhanden sind.
Widersprüche, 50/50-Resultate oder mehrere Gewinner werden verworfen. Wo die
CLOB-Winner-Markierung noch nicht gesetzt ist, ist ein eindeutiges
Gamma-Terminalpaar `(1,0)` beziehungsweise `(0,1)` ein explizit markierter
Fallback und Gegenstand einer Robustheitsanalyse.

## Tabelle `provenance`

| Feld | Bedeutung |
|---|---|
| `artifact` | eindeutiger Request-/Artefaktname |
| `source_url` | Endpunkt ohne geheime Parameter |
| `retrieved_at` | UTC-Abrufzeit |
| `sha256` | Hash des exakten Responsebody |
| `byte_count` | Responsegröße |
| `parameters_json` | kanonische Queryparameter |
| `status_code` | HTTP-Status |
| `schema_version` | Version dieses Datenvertrags |

## Tabelle `exclusions`

Jede nicht verwendbare Zeile erhält `market_id`, maschinenlesbaren `reason`
und `detail`. Die Berichterstellung zählt diese Gründe. Ausschlüsse werden
nicht still verworfen.

## Abgeleitete Tabelle `cohort`

`build-dataset` erzeugt eine Zeile pro `market_id` und `horizon_days`:

- `forecast_cutoff`,
- `market_probability`,
- `price_age_hours`,
- vergangene Returns/Volatilität/Min/Max/Punktzahl,
- Vertragsalter und Zeit bis zum Event,
- Text und Kategorie,
- Ziel, Eventgruppe und Auflösungszeit.

Ein automatischer Audit prüft:

1. alle verwendeten Preise liegen am oder vor dem Cutoff,
2. Cutoff liegt nach Erstellung und vor Auflösung,
3. Ziel-/Terminalfelder fehlen in der Featureliste,
4. Eventgruppen kreuzen keine Splits und
5. jedes Trainingslabel war vor dem zugehörigen Validierungs-Cutoff bekannt.

## Zeiteinheiten

- Gamma: ISO-8601; naive historische Werte werden dokumentiert als UTC
  interpretiert.
- CLOB Price History: Unixsekunden.
- CLOB aktuelles Orderbuch/WebSocket: je nach Endpunkt Millisekunden; wird in
  dieser Studie nicht historisch verwendet.
- Polygon: Blockzeit in Unixsekunden; optionaler Erweiterungspfad.

Alle normalisierten Zeiten sind timezone-aware UTC.

## Lizenz und Datenschutz

Öffentliche API-Lesbarkeit ist keine pauschale Open-Data-Lizenz. Die Studie
publiziert deshalb keine Massendumps und keine Walletprofile. Quellen,
Abrufzeitpunkte und Hashes erlauben Berechtigten die Reproduktion. Vor
kommerzieller Nutzung oder Rohdatenweitergabe ist die jeweils aktuelle
Polymarket-/Drittanbieter-Lizenz zu prüfen.
