# KaderKiosk

## Überblick
Ein kostenloser, automatisierter News-Aggregator für alle 18 Bundesliga-Teams: Verletzungen, Sperren, voraussichtliche Aufstellungen und Trainer-/Pressekonferenz-News, gesammelt an einem Ort. Kein Kickbase-Zugriff, kein Login mit echten Zugangsdaten, keine Priorisierung einzelner Spieler – reiner, personenunabhängiger Aggregator für die ganze Liga. Budget: 0 €, ausschließlich kostenlose Bausteine. Primärer Zugriff: mobil über den Browser, als Homescreen-Icon.

## Projektstruktur
```
kaderkiosk/
├── CLAUDE.md
├── scraper/
│   ├── sources/
│   │   ├── flashscore.py
│   │   ├── sportschau_rss.py
│   │   ├── bundesliga_com.py
│   │   ├── ggfn_rss.py
│   │   └── fussballverletzungen.py
│   ├── dedupe.py
│   └── main.py
├── data/
│   └── news.json
├── docs/                  # GitHub Pages Quelle
│   └── index.html
└── .github/workflows/
    └── scrape.yml
```

## Architektur
Datenfluss: öffentliche Quellen → Scraping-Script → JSON im Repo → Dashboard.

| Komponente | Rolle |
| --- | --- |
| Datenquellen | öffentliche, login-lose Webseiten/Feeds |
| Taktgeber | GitHub Actions, Cron alle 30 Min |
| Speicherung | `data/news.json`, von der Action aktualisiert |
| Dashboard | statische Website über GitHub Pages (`docs/`) |
| Benachrichtigungen | nicht Teil von V1 |

## Datenquellen
Fünf unabhängige, ligaweite Quellen – jede deckt alle Vereine über eine einzige Struktur ab, der Aufwand pro Quelle bleibt also konstant:

- **Flashscore-Spieltagsübersicht** – Verletzungen, Sperren, voraussichtliche Aufstellung, spieltagsweise
- **sportschau.de Bundesliga-RSS** – offiziell (ARD/WDR), kontinuierlich, auch unter der Woche: `fussball/bundesliga/index~rss2.xml`
- **bundesliga.com Pressekonferenz-Feed** – offizielle PK-Übersicht aller Vereine
- **getfootballnewsgermany.com RSS** – kontinuierlicher Bundesliga-Blog (englisch), Cross-Check: `/feed`
- **fußballverletzungen.com** – dedizierte Verletzungstabelle für die ganze Liga, Redundanz/Ausfallsicherung

Bewusst ausgeschlossen: 18 einzelne Vereinsseiten, Goal.de-Einzelartikel pro Verein, Soccerway-Spielerhistorien (bräuchten eine komplette Spieler-ID-Zuordnung) – deren Aufwand wächst mit jedem zusätzlichen Verein, während die fünf Quellen oben konstant bleiben.

### Datenschema pro Eintrag
```json
{"verein": "", "spieler": "", "kategorie": "verletzung|sperre|aufstellung|pressekonferenz", "status": "", "beschreibung": "", "quelle": "", "erfasst_am": "ISO-Datum"}
```

## Tech-Stack & Repo-Setup
- Sprache: Python (requests/BeautifulSoup, läuft problemlos in GitHub Actions)
- GitHub Actions: Workflow in `.github/workflows/scrape.yml`, Cron alle 30 Minuten
- Repo: **public** – GitHub Pages läuft auf dem kostenlosen Plan nur bei public Repos, zusätzlich unbegrenzte, kostenlose Actions-Minuten
- Secrets: aktuell keine nötig (nur öffentliches Scraping); relevant erst ab einem Push-Kanal in V2, dann über Repo → Settings → Secrets and variables → Actions

## Frontend-Konzept (Umsetzung erst nach der Datengrundlage)
- **Farbe**: kein einzelner App-Akzent – jeder Verein trägt seine reale Vereinsfarbe als Kennzeichnung seines Abschnitts. Kategorien in gedeckten, funktionalen Statusfarben statt eines grellen Akzents: Verletzung Ziegelrot `#B34A3C`, Sperre Ocker `#B8863B`, Aufstellung Blaugrau `#3B6E8F`, Pressekonferenz Neutralgrau `#8A8474`. Grundton warmes Papierweiß `#F6F3EC`, Text Dunkelanthrazit `#1C1A17`.
- **Typografie**: League Gothic (condensed, Scoreboard-Herkunft) für Vereinsnamen/Überschriften, Source Serif 4 für Fließtext. Kategorie-Labels normal groß-/kleingeschrieben, keine ALL-CAPS.
- **Layout**: primär nach Verein gruppiert statt als flacher chronologischer Feed. Flache Zeilen statt einheitlicher abgerundeter Karten, getrennt durch dünne Linien – eher Ergebnisliste als Dashboard-Kacheln.
- **Prinzipien**: Farbe erzählt (Verein, Status), dekoriert nicht. Dichte vor Weißraum – schnelles Scannen zählt mehr als ein "freundlicher" App-Eindruck. Keine Mittelpunkt-Meta-Strings, keine ALL-CAPS-Labels, keine einheitlichen Card-Schatten.

## Empfohlene Baureihenfolge
1. Eine Quelle (sportschau.de-RSS, strukturiertes XML) komplett durchziehen: abrufen → parsen → `data/news.json`
2. Die anderen vier Quellen nach demselben Muster ergänzen
3. Dedupe-Logik (`dedupe.py`), sobald mehrere Quellen überlappen
4. GitHub-Actions-Workflow drumherum bauen (Cron, Checkout, Commit)
5. Dashboard nach dem Frontend-Konzept oben, mit echten Daten statt Platzhaltern

## Offene Punkte
- Push-Kanal noch offen (Telegram-Bot oder ntfy.sh) – erst in V2 relevant
- Kickbase-Anbindung bewusst ausgeklammert, bei Bedarf später nachrüstbar
