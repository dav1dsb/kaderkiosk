# KaderKiosk

## Überblick
Ein kostenloser, automatisierter News-Aggregator für alle 18 Bundesliga-Teams: Meldungen mit Quellenlink zu Verletzungen, Sperren, voraussichtlichen Aufstellungen und Trainer-/Pressekonferenz-News, gesammelt an einem Ort. Kein Kickbase-Zugriff, kein Login mit echten Zugangsdaten, keine Priorisierung einzelner Spieler – reiner, personenunabhängiger Aggregator für die ganze Liga. Budget: 0 €, ausschließlich kostenlose Bausteine. Primärer Zugriff: mobil über den Browser, als Homescreen-Icon.

## Projektstruktur
```
kaderkiosk/
├── CLAUDE.md
├── scraper/
│   ├── sources/
│   │   ├── sportschau_rss.py
│   │   └── ggfn_rss.py
│   ├── dedupe.py
│   └── main.py
├── data/
│   ├── sources/           # eine Datei pro Quelle, von deren Scraper geschrieben
│   │   ├── sportschau.json
│   │   └── ggfn.json
│   └── news.json          # von main.py zusammengeführt
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
| Speicherung | pro Quelle `data/sources/<quelle>.json`; `main.py` führt sie zu `data/news.json` zusammen, von der Action aktualisiert |
| Dashboard | statische Website über GitHub Pages (`docs/`) |
| Benachrichtigungen | nicht Teil von V1 |

## Datenquellen
**Prinzip:** KaderKiosk ist ein Aggregator von Meldungen mit Quellenlink, keine strukturierte Kaderdatenbank. Übernommen werden nur Artikel bzw. Feed-Einträge (Überschrift, Teaser, Link), die der Anbieter öffentlich bereitstellt. Keine Quellen, die nicht-öffentliche/undokumentierte APIs nutzen oder wie eine Datenbank statt wie ein Artikel/Feed aufgebaut sind (Verletzungstabellen, Spieltagsübersichten o. Ä.).

**Vor jeder neuen Quelle** Nutzungsbedingungen und robots.txt prüfen – auf Verbote von Scraping/Aggregation/automatisierten Abrufen, Text-und-Data-Mining-Vorbehalte (§ 44b Abs. 3 UrhG), Datenbankschutz und Beschränkungen auf private Nutzung. Das Repo und das Dashboard sind öffentlich, übernommene Inhalte werden also öffentlich zugänglich gemacht. Spricht etwas dagegen: nicht bauen.

Aktive Quellen – jede deckt alle Vereine über eine einzige Struktur ab:

- **sportschau.de Bundesliga-RSS** – offiziell (ARD/WDR), kontinuierlich, auch unter der Woche: `fussball/bundesliga/index~rss2.xml`
  - Geprüft 23.09.2026: Die RSS-Seite (`/service/rssfeeds-sp-102.html`) bietet den Feed ausdrücklich zum Einbinden „als Nachrichten-Block in Ihrer Homepage“ an; robots.txt sperrt für normale Abrufe nur `/live-und-ergebnisse/widget/`. Graubereich: robots.txt enthält einen TDM-Vorbehalt nach § 44b Abs. 3 UrhG (Schwerpunkt KI-Training), der Urheberrechtshinweis (`/service/urheberrecht`) verlangt für Vervielfältigung über den Privatgebrauch hinaus eine Genehmigung. Ansprechpartner für eine Bestätigung: fragen@sportschau.de
  - Betriebsregeln: nur übernehmen, was der Feed liefert (Überschrift, Teaser, Link, Datum) – nie Artikelseiten abrufen oder Artikeltext speichern; jeder Eintrag mit Link auf den Originalartikel; im Dashboard sichtbar als „sportschau.de“ gekennzeichnet
- **getfootballnewsgermany.com RSS** – kontinuierlicher Bundesliga-Blog (englisch), Cross-Check und einzige Quelle für die Kategorie `transfer`: `/feed/`
  - Geprüft 23.09.2026: keine Nutzungsbedingungen vorhanden (nur About, Contact, Privacy Policy, Bildagentur-Disclaimer), kein Verbot von Scraping/Aggregation/automatisierten Abrufen, kein TDM-Vorbehalt, keine Beschränkung auf private Nutzung; Footer „All Rights Reserved“, RSS-Link öffentlich angeboten. robots.txt erlaubt `/feed/`, sperrt aber Kategorie-Feeds (`/category/*/*`) und URLs mit Query-Parametern (`/*?*`)
  - Betriebsregeln: nur der Hauptfeed `/feed/`, keine Kategorie-Feeds oder `?paged=`; nur Überschrift, Teaser (erster Absatz der `description`), Link, Datum – nie `content:encoded` (voller Artikeltext) oder Artikelseiten; jeder Eintrag mit Link auf den Originalartikel; im Dashboard sichtbar als „getfootballnewsgermany.com“ gekennzeichnet

Nach Prüfung ausgeschlossen (Stand 23.09.2026):

- **Flashscore** – Nutzungsbedingungen verbieten Scraping/Aggregation ohne ausdrückliche Zustimmung, automatisierte Anfragen, Reverse-Engineering und Datenbank-Extraktion; Daten kämen zudem nur über die undokumentierte interne Schnittstelle
- **bundesliga.com** – robots.txt und rechtliche Hinweise: ausdrücklicher Text-und-Data-Mining-Vorbehalt nach § 44b Abs. 3 UrhG, jeglicher Zugriff/Download durch automatisierte Programme oder Bots untersagt; Kopien nur für persönlichen, privaten, nicht kommerziellen Gebrauch
- **ligainsider.de** – Nutzung laut Nutzungsbedingungen ausschließlich zu privaten Zwecken
- **fußballverletzungen.com** – Domain verloren, leitet inzwischen auf eine fremde Glücksspielseite um

Außerdem bewusst ausgeschlossen: 18 einzelne Vereinsseiten, Goal.de-Einzelartikel pro Verein, Soccerway-Spielerhistorien (bräuchten eine komplette Spieler-ID-Zuordnung) – deren Aufwand wächst mit jedem zusätzlichen Verein.

### Datenschema pro Eintrag
```json
{"verein": "", "spieler": "", "kategorie": "verletzung|sperre|aufstellung|pressekonferenz|ergebnis|transfer", "status": "", "beschreibung": "", "quelle": "", "erfasst_am": "ISO-Datum"}
```

`erfasst_am` ist das Veröffentlichungsdatum des Artikels bzw. Feed-Eintrags – alle Quellen sind Artikel/Feeds (siehe Prinzip oben).

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
1. Eine Quelle (sportschau.de-RSS, strukturiertes XML) komplett durchziehen: abrufen → parsen → `data/sources/sportschau.json`
2. Weitere Quellen nach demselben Muster ergänzen, jeweils erst nach Prüfung von Nutzungsbedingungen und robots.txt
3. Dedupe-Logik (`dedupe.py`), sobald mehrere Quellen überlappen
4. GitHub-Actions-Workflow drumherum bauen (Cron, Checkout, Commit)
5. Dashboard nach dem Frontend-Konzept oben, mit echten Daten statt Platzhaltern

## Offene Punkte
- Push-Kanal noch offen (Telegram-Bot oder ntfy.sh) – erst in V2 relevant
- Kickbase-Anbindung bewusst ausgeklammert, bei Bedarf später nachrüstbar
