"""Führt die Ausgaben aller Quellen (data/sources/*.json) zu data/news.json zusammen.

Ruft die Scraper nicht selbst auf – die laufen vorher einzeln (siehe .github/workflows/scrape.yml).
Eine kaputte oder unlesbare Quelldatei wird mit Warnung übersprungen, damit eine ausgefallene Quelle
nicht die Einträge der anderen verdrängt.

Aufruf aus dem Repo-Root:  python -m scraper.main
"""

import json
import sys
from pathlib import Path

from scraper.dedupe import dedupe, zeitpunkt

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCES_DIR = DATA_DIR / "sources"
OUTPUT_PATH = DATA_DIR / "news.json"
FELDER = ("verein", "spieler", "kategorie", "status", "beschreibung", "quelle", "erfasst_am")


def gueltig(entry: object) -> bool:
    if not (isinstance(entry, dict) and all(isinstance(entry.get(f), str) for f in FELDER)):
        return False
    try:
        zeitpunkt(entry)
    except ValueError:
        return False
    return bool(entry["quelle"])


def read_sources(sources_dir: Path = SOURCES_DIR) -> list[dict]:
    entries = []
    for path in sorted(sources_dir.glob("*.json")):
        try:
            daten = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warnung: {path.name} übersprungen ({e})", file=sys.stderr)
            continue
        if not isinstance(daten, list):
            print(f"Warnung: {path.name} übersprungen (keine Liste)", file=sys.stderr)
            continue
        ok = [e for e in daten if gueltig(e)]
        if len(ok) < len(daten):
            print(f"Warnung: {path.name}: {len(daten) - len(ok)} ungültige Einträge übersprungen", file=sys.stderr)
        entries += ok
    return entries


def merge(entries: list[dict]) -> list[dict]:
    return sorted(dedupe(entries), key=zeitpunkt, reverse=True)


def write_news(entries: list[dict], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    gelesen = read_sources()
    news = merge(gelesen)
    write_news(news)
    print(f"{len(news)} Einträge nach {OUTPUT_PATH} geschrieben ({len(gelesen) - len(news)} Duplikate entfernt)")
