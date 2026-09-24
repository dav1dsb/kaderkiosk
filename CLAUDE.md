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
├── docs/                  # GitHub Pages Quelle (Branch main, Ordner /docs)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── logos/             # Vereinslogos (SVG) + QUELLEN.md mit Lizenzen
│   └── manifest.webmanifest, icon-*.png
└── .github/workflows/
    └── scrape.yml
```

## Architektur
Datenfluss: öffentliche Quellen → Scraping-Script → JSON im Repo → Dashboard.

| Komponente | Rolle |
| --- | --- |
| Datenquellen | öffentliche, login-lose Webseiten/Feeds |
| Taktgeber | GitHub Actions, Cron alle 15 Min, Commit nur bei geänderten Daten |
| Speicherung | pro Quelle `data/sources/<quelle>.json`; `main.py` führt sie zu `data/news.json` zusammen, von der Action aktualisiert |
| Dashboard | statische Website über GitHub Pages (`docs/`) |
| Benachrichtigungen | nicht Teil von V1 |

## Datenquellen
**Prinzip:** KaderKiosk ist ein Aggregator von Meldungen mit Quellenlink, keine strukturierte Kaderdatenbank. Übernommen werden nur Artikel bzw. Feed-Einträge (Überschrift, Teaser, Link), die der Anbieter öffentlich bereitstellt. Keine Quellen, die nicht-öffentliche/undokumentierte APIs nutzen oder wie eine Datenbank statt wie ein Artikel/Feed aufgebaut sind (Verletzungstabellen, Spieltagsübersichten o. Ä.).

**Vor jeder neuen Quelle** Nutzungsbedingungen und robots.txt prüfen – auf Verbote von Scraping/Aggregation/automatisierten Abrufen, Text-und-Data-Mining-Vorbehalte (§ 44b Abs. 3 UrhG), Datenbankschutz und Beschränkungen auf private Nutzung. Das Repo und das Dashboard sind öffentlich, übernommene Inhalte werden also öffentlich zugänglich gemacht. Spricht etwas dagegen: nicht bauen.

Aktive Quellen – jede deckt alle Vereine über eine einzige Struktur ab:

- **sportschau.de Bundesliga-RSS** – offiziell (ARD/WDR), kontinuierlich, auch unter der Woche: `fussball/bundesliga/index~rss2.xml`
  - Stichwort-Regeln (`REGELN` in `sportschau_rss.py`) erfassen neben klaren Fällen auch weiche Formulierungen, z. B. „muss passen“, „vorzeitig abgereist“, „Einsatz offen“, „Fragezeichen hinter dem Einsatz“, „droht auszufallen“, „individuelles Training“, „MRT“, „Blessur“, „muskuläre Probleme“. Bewusst nicht: „Sorgen um“/„bangt um“ (meist Klassenerhalt), „abwarten“, „geschont“ (Rotation)
  - Geprüft 23.09.2026: Die RSS-Seite (`/service/rssfeeds-sp-102.html`) bietet den Feed ausdrücklich zum Einbinden „als Nachrichten-Block in Ihrer Homepage“ an; robots.txt sperrt für normale Abrufe nur `/live-und-ergebnisse/widget/`. Graubereich: robots.txt enthält einen TDM-Vorbehalt nach § 44b Abs. 3 UrhG (Schwerpunkt KI-Training), der Urheberrechtshinweis (`/service/urheberrecht`) verlangt für Vervielfältigung über den Privatgebrauch hinaus eine Genehmigung. Ansprechpartner für eine Bestätigung: fragen@sportschau.de
  - Betriebsregeln: nur übernehmen, was der Feed liefert (Überschrift, Teaser, Link, Datum) – nie Artikelseiten abrufen oder Artikeltext speichern; jeder Eintrag mit Link auf den Originalartikel; im Dashboard sichtbar als „sportschau.de“ gekennzeichnet
- **getfootballnewsgermany.com RSS** – kontinuierlicher Bundesliga-Blog (englisch), Cross-Check und einzige Quelle für die Kategorie `transfer`: `/feed/`
  - Stichwort-Regeln (`REGELN` in `ggfn_rss.py`) erfassen neben klaren Fällen auch weiche Formulierungen, z. B. „picked up a knock“, „assessed ahead of“, „doubtful“, „fitness concern“, „fitness test“, „withdrawn from the squad“, „leaves camp“, „limped off“, „falls ill“. Bewusst nicht: bloßes „doubt“ („no doubt“), bloßes „knock“ („knocked out“), „suffered/sustained“ ohne Verletzungswort („suffered a defeat“)
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

### Zusammenführen und Duplikate
`python -m scraper.main` liest alle `data/sources/*.json`, entfernt Duplikate (`scraper/dedupe.py`) und schreibt `data/news.json`, sortiert nach `erfasst_am`, neueste zuerst. Duplikat-Schlüssel: `quelle` (URL, normalisiert: Schema/Host klein, ohne Fragment und abschließenden Schrägstrich) + `verein`; pro Schlüssel bleibt der früheste Eintrag. Dieselbe Nachricht aus verschiedenen Quellen (andere URL) gilt nicht als Duplikat. Unlesbare Quelldateien und ungültige Einträge werden mit Warnung übersprungen.

## Tech-Stack & Repo-Setup
- Sprache: Python (requests/BeautifulSoup, läuft problemlos in GitHub Actions)
- GitHub Actions: Workflow in `.github/workflows/scrape.yml`, Cron alle 15 Minuten plus `workflow_dispatch` zum manuellen Auslösen. Begründung für 15 Minuten: Das Repo ist public, Actions-Minuten kosten also nichts – kürzer lohnt trotzdem nicht, weil die Artikel-Feeds nicht minütlich aktualisieren; 15 Minuten halten die Daten aktuell, ohne die Quellen unnötig oft abzufragen
- Ablauf: beide Scraper nacheinander, jeweils mit `continue-on-error` – fällt ein Feed aus, führt `main.py` trotzdem mit dem letzten Stand dieser Quelle aus dem Repo zusammen. Committet und gepusht wird als `github-actions[bot]` nur, wenn sich `data/news.json` oder `data/sources/` tatsächlich geändert haben
- Repo: **public** – GitHub Pages läuft auf dem kostenlosen Plan nur bei public Repos, zusätzlich unbegrenzte, kostenlose Actions-Minuten
- Secrets: aktuell keine nötig (nur öffentliches Scraping); relevant erst ab einem Push-Kanal in V2, dann über Repo → Settings → Secrets and variables → Actions

## Frontend-Konzept
- **Farbe**: kein einzelner App-Akzent – jeder Verein trägt seine reale Vereinsfarbe als Kennzeichnung seines Abschnitts. Kategorien in gedeckten, funktionalen Statusfarben statt eines grellen Akzents: Verletzung Ziegelrot `#B34A3C`, Sperre Ocker `#B8863B`, Aufstellung Blaugrau `#3B6E8F`, Pressekonferenz Neutralgrau `#8A8474`, Ergebnis Moosgrün `#5C8259`, Transfer Pflaumenlila `#7A5D74`. Grundton warmes Papierweiß `#F6F3EC`, Text Dunkelanthrazit `#1C1A17`.
- **Typografie**: League Gothic (condensed, Scoreboard-Herkunft) für Vereinsnamen/Überschriften, Source Serif 4 für Fließtext. Kategorie-Labels normal groß-/kleingeschrieben, keine ALL-CAPS.
- **Layout**: primär nach Verein gruppiert statt als flacher chronologischer Feed. Flache Zeilen statt einheitlicher abgerundeter Karten, getrennt durch dünne Linien – eher Ergebnisliste als Dashboard-Kacheln.
- **Umsetzung** (`docs/`, reines HTML/CSS/JS ohne Build): Kopf mit Datum, Kurzbeschreibung und Doppellinie; Filter-Chips mit Anzahl, auf dem Handy umbrechend statt seitlich scrollend (leere Kategorien deaktiviert, Auswahl in `#kategorie=…`); Sprungleiste mit Wappen und Kürzel; Vereinsabschnitte mit zweifarbigem Trikotstreifen (Haupt-/Nebenfarbe, Tabelle `VEREINE` in `app.js`) und einem Kopfband in 9 % der Vereinsfarbe, neueste Meldung zuerst; Kategorie als Farbquadrat vor dem Label; Quelle und Zeitpunkt als Fußzeile jeder Meldung; Vereine ohne Meldungen als kompakte Zeile am Ende.
- **Kein abgeschnittener Text**: Teaser werden vollständig gezeigt (keine Zeilenbegrenzung), lange Wörter brechen um (`overflow-wrap`, `hyphens: auto`), nichts scrollt seitlich. Geprüft bei 375 und 390 px Breite in allen Zuständen (volle Liste, gefiltert, leere Kategorie, keine Daten, Ladefehler, Sonderfälle wie überlange Wörter).
- **Vereinslogos**: klein (32 px im Vereinskopf, 20 px in der Sprungleiste), nur zur Wiedererkennung. Quelle ausschließlich Wikimedia Commons, unverändert in `docs/logos/<kürzel>.svg`; Lizenz, Urheber und Commons-Link je Datei in `docs/logos/QUELLEN.md`. 12 gemeinfrei, 1. FC Köln CC BY-SA 4.0 (Namensnennung im Seitenfuß). Alle Logos sind Marken der Vereine – der Seitenfuß stellt klar, dass sie nur der Zuordnung dienen. Ohne frei lizenziertes aktuelles Logo auf Commons: RB Leipzig, SC Freiburg, Eintracht Frankfurt, FC Augsburg, Bayer 04 Leverkusen (dort nur das Logo des Gesamtvereins TSV Bayer 04) – für diese zeigt das Dashboard das Vereinskürzel in den Vereinsfarben. Keine nicht-freien Logos aus anderen Quellen (z. B. Fair-Use-Dateien der englischen Wikipedia) übernehmen.
- **Daten zur Laufzeit**: Pages veröffentlicht nur `docs/`, deshalb lädt `app.js` auf `*.github.io` direkt `https://raw.githubusercontent.com/dav1dsb/kaderkiosk/main/data/news.json` (CORS offen, bis zu 5 Minuten gecacht) – neue Daten brauchen kein Redeploy. Lokal (Server im Repo-Root, Seite unter `/docs/`) wird zuerst `../data/news.json` versucht; `?data=<url>` überschreibt beides zum Testen. Feed-Texte kommen nur per `textContent` ins DOM, Quellenlinks nur mit `http(s)`.
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
