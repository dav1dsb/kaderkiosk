"""sportschau.de Bundesliga-RSS: Feed abrufen, parsen, relevante Einträge ins Schema überführen.

Der Feed ist ein allgemeiner News-Feed (größtenteils Spielberichte). Übernommen werden
Einträge, die sich per Stichwort einer der vier Kader-Kategorien zuordnen lassen, sowie
Spielberichte (URL enthält "spielbericht-") als Kategorie "ergebnis" – je ein Eintrag pro
beteiligtem Verein, die Vereine stammen aus der URL (spielbericht-<heim>-<gast>-<nr>.html).

Aufruf aus dem Repo-Root:  python -m scraper.sources.sportschau_rss
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

FEED_URL = "https://www.sportschau.de/fussball/bundesliga/index~rss2.xml"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "sources" / "sportschau.json"
USER_AGENT = "KaderKiosk/0.1 (+https://github.com/dav1dsb/kaderkiosk)"

# Bundesliga-Saison 2026/27. Aliase als Regex, \b-begrenzt; mehrdeutige Namen wie "Borussia" bewusst nicht.
VEREINE = {
    "FC Bayern München": r"FC Bayern|Bayern(?:-\w+)?",
    "Borussia Dortmund": r"Dortmund(?:er)?|BVB",
    "RB Leipzig": r"Leipzig(?:er)?|RB",
    "VfB Stuttgart": r"Stuttgart(?:er)?|VfB",
    "TSG Hoffenheim": r"Hoffenheim(?:er)?|TSG",
    "Bayer 04 Leverkusen": r"Leverkusen(?:er)?|Bayer|Werkself",
    "SC Freiburg": r"Freiburg(?:er)?",
    "Eintracht Frankfurt": r"Frankfurt(?:er)?|Eintracht",
    "FC Augsburg": r"Augsburg(?:er)?",
    "1. FSV Mainz 05": r"Mainz(?:er)?",
    "1. FC Union Berlin": r"Union(?: Berlin)?",
    "Borussia Mönchengladbach": r"(?:Mönchen)?[Gg]ladbach(?:er)?",
    "Hamburger SV": r"Hamburger SV|HSV",
    "1. FC Köln": r"Köln(?:er)?",
    "SV Werder Bremen": r"Werder|Bremen|Bremer",
    "FC Schalke 04": r"Schalke|Königsblauen?",
    "SV 07 Elversberg": r"Elversberg",
    "SC Paderborn 07": r"Paderborn(?:er)?",
}
VEREIN_PATTERNS = {name: re.compile(rf"\b(?:{alias})\b") for name, alias in VEREINE.items()}

# (kategorie, status, pattern, auch_in_beschreibung)
# Trainer-/PK-/Aufstellungs-Wörter tauchen in Spielberichten beiläufig auf ("Entlassung von Trainer X",
# "sieben Neue in der Startelf") und zählen daher nur in der Überschrift. Verletzungen und Sperren
# sind auch im Teaser ein starkes Signal.
# Neben klaren Fällen auch weiche Formulierungen, wie sie vor allem in Länderspielpausen vorkommen
# ("muss passen", "vorzeitig abgereist", "Einsatz offen", "droht auszufallen", "Blessur"). Bewusst nicht:
# "Sorgen um"/"bangt um" (meist Klassenerhalt oder Form), "abwarten", "geschont" (Rotation statt Verletzung).
REGELN = [
    ("verletzung", "fällt aus",
     r"Kreuzband\w*|Saisonaus|fällt\s+(?:\w+\s+)?aus|Ausfall"
     r"|muss\s+(?:[\w-]+\s+){0,3}passen|verletzt\s+(?:absagen|abreisen|passen)"
     r"|(?:reist|reiste)\s+(?:[\w-]+\s+)?vorzeitig\s+(?:[\w-]+\s+){0,4}ab\b|vorzeitig\s+abgereist"
     r"|fehlt\s+(?:\w+\s+)?(?:verletzt|angeschlagen|krank)|nicht\s+(?:mehr\s+)?rechtzeitig\s+fit|operiert|\bOP\b", True),
    ("verletzung", "fraglich",
     r"fraglich|angeschlagen|Einsatz\s+wackelt"
     r"|Fragezeichen\s+(?:hinter|beim?)\s+(?:dem\s+|seinem\s+|ihrem\s+)?Einsatz"
     r"|Einsatz\w*\s+(?:(?:von|des|der)\s+[\w-]+\s+)?(?:ist\s+|bleibt\s+|steht\s+)?(?:offen|ungewiss|unklar|in Gefahr|auf der Kippe)"
     r"|droht\s+(?:\w+\s+){0,2}(?:auszufallen|zu fehlen|zu verpassen|Ausfall)|Wettlauf gegen die Zeit"
     r"|individuell\w*\s+Training|kürzertreten|Belastungssteuerung|\bMRT\b"
     r"|(?:weitere|genauere|eingehende)\w*\s+Untersuchung\w*|wird\s+(?:\w+\s+)?untersucht", True),
    ("verletzung", "zurück",
     r"Comeback|zurück im (?:Mannschafts)?[Tt]raining|wieder fit"
     r"|Rückkehr\s+ins\s+(?:Mannschafts)?[Tt]raining|wieder\s+(?:im|ins)\s+(?:Mannschafts)?[Tt]raining"
     r"|steigt\s+(?:wieder\s+)?ins\s+(?:Mannschafts)?[Tt]raining\s+ein|Lauftraining|\bReha\b|wieder\s+einsatzbereit"
     r"|nach\s+(?:[\w-]+\s+)?(?:Verletzung\w*|Blessur|Zwangspause)\s+zurück", True),
    ("verletzung", "verletzt",
     r"verletz\w*|Verletzung\w*|Muskelfaserriss|Bänderriss|Zerrung|Knöchel|Oberschenkel"
     r"|Blessur|muskuläre\w*\s+Probleme|Muskelprobleme|Muskelverhärtung|Beschwerden|Schmerzen|Prellung|Stauchung"
     r"|Bänderdehnung|Faserriss|Pferdekuss|Gehirnerschütterung|Wade|Sprunggelenk|Adduktoren|Leiste\b"
     r"|Knie(?:verletzung|probleme|beschwerden|operation)?\b|humpelt\w*|musste\s+(?:\w+\s+){0,2}ausgewechselt\s+werden"
     r"|zurück\s+zu\s+(?:seinem|ihrem)\s+(?:Klub|Verein)", True),
    ("sperre", "gesperrt", r"gesperrt|Sperre", True),
    ("sperre", "Platzverweis", r"Platzverweis|Rote[n]? Karte|Gelb-Rot\w*", True),
    ("pressekonferenz", "Pressekonferenz", r"Pressekonferenz|\bPK\b", False),
    ("pressekonferenz", "Trainerwechsel", r"neuer Trainer|Trainerwechsel|entlassen|Entlassung|freigestellt|Nachfolger", False),
    ("pressekonferenz", "Trainer-News", r"Trainer\w*|Coach", False),
    ("aufstellung", "voraussichtlich", r"Aufstellung|Startelf|Kader", False),
]
REGELN = [(k, s, re.compile(p), d) for k, s, p, d in REGELN]

SPIELBERICHT_MARKER = "spielbericht-"
# URL-Slugs der Vereine in Spielbericht-Links. Slugs enthalten selbst Bindestriche, daher kein split("-").
VEREIN_SLUGS = {
    "FC Bayern München": ["fc-bayern-muenchen", "bayern-muenchen", "fc-bayern", "bayern"],
    "Borussia Dortmund": ["borussia-dortmund", "dortmund", "bvb"],
    "RB Leipzig": ["rb-leipzig", "leipzig"],
    "VfB Stuttgart": ["vfb-stuttgart", "stuttgart"],
    "TSG Hoffenheim": ["tsg-1899-hoffenheim", "tsg-hoffenheim", "hoffenheim"],
    "Bayer 04 Leverkusen": ["bayer-04-leverkusen", "bayer-leverkusen", "leverkusen"],
    "SC Freiburg": ["sc-freiburg", "freiburg"],
    "Eintracht Frankfurt": ["eintracht-frankfurt", "frankfurt"],
    "FC Augsburg": ["fc-augsburg", "augsburg"],
    "1. FSV Mainz 05": ["1-fsv-mainz-05", "fsv-mainz-05", "mainz-05", "mainz"],
    "1. FC Union Berlin": ["1-fc-union-berlin", "fc-union-berlin", "union-berlin"],
    "Borussia Mönchengladbach": ["borussia-moenchengladbach", "moenchengladbach", "gladbach"],
    "Hamburger SV": ["hamburger-sv", "hsv"],
    "1. FC Köln": ["1-fc-koeln", "fc-koeln", "koeln"],
    "SV Werder Bremen": ["sv-werder-bremen", "werder-bremen", "werder"],
    "FC Schalke 04": ["fc-schalke-04", "schalke-04", "schalke"],
    "SV 07 Elversberg": ["sv-07-elversberg", "sv-elversberg", "elversberg"],
    "SC Paderborn 07": ["sc-paderborn-07", "sc-paderborn", "paderborn"],
}
SLUG_ZU_VEREIN = {slug: name for name, slugs in VEREIN_SLUGS.items() for slug in slugs}
_SLUG_ALT = "|".join(sorted(map(re.escape, SLUG_ZU_VEREIN), key=len, reverse=True))
SPIELBERICHT_URL = re.compile(rf"{SPIELBERICHT_MARKER}(?P<heim>{_SLUG_ALT})-(?P<gast>{_SLUG_ALT})-\d+\.html$")
# Feste Vereins-Übersichtsseiten, Audiostreams und Sendungen in voller Länge – nie übernehmen.
AUSGESCHLOSSEN = re.compile(r"klub-index|index-sp-\d+\.html|audio|re-live")


def fetch_feed(url: str = FEED_URL) -> bytes:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()
    return response.content


def parse_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iterfind("./channel/item"):
        items.append({
            "titel": (item.findtext("title") or "").strip(),
            "teaser": (item.findtext("description") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
        })
    return items


def classify(titel: str, teaser: str) -> tuple[str, str, re.Match, str] | None:
    """Erste passende Regel gewinnt; Überschrift vor Teaser. Liefert (kategorie, status, treffer, text)."""
    for kategorie, status, pattern, auch_teaser in REGELN:
        for text in (titel, teaser) if auch_teaser else (titel,):
            if match := pattern.search(text):
                return kategorie, status, match, text
    return None


def vereine_in(text: str) -> list[str]:
    treffer = [(m.start(), name) for name, p in VEREIN_PATTERNS.items() if (m := p.search(text))]
    return [name for _, name in sorted(treffer)]


def find_verein(titel: str, teaser: str, match: re.Match | None = None, text: str = "") -> str:
    """Eindeutiger Verein im Satz des Stichworts, sonst im ganzen Eintrag, sonst leer statt geraten."""
    kandidaten_listen = [vereine_in(f"{titel}. {teaser}")]
    if match:
        satz_start = text.rfind(". ", 0, match.start()) + 1
        satz_ende = text.find(". ", match.end())
        kandidaten_listen.insert(0, vereine_in(text[satz_start: satz_ende if satz_ende != -1 else len(text)]))
    for kandidaten in kandidaten_listen:
        if len(set(kandidaten)) == 1:
            return kandidaten[0]
    return ""


def to_iso(pub_date: str) -> str:
    try:
        return parsedate_to_datetime(pub_date).isoformat()
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def vereine_aus_spielbericht_url(url: str) -> list[str]:
    """[heim, gast] aus spielbericht-<heim>-<gast>-<nr>.html; leer, wenn ein Slug unbekannt ist."""
    if match := SPIELBERICHT_URL.search(url):
        return [SLUG_ZU_VEREIN[match["heim"]], SLUG_ZU_VEREIN[match["gast"]]]
    return []


def to_entries(item: dict) -> list[dict]:
    """Ein Eintrag pro Feed-Item, bei Spielberichten einer pro beteiligtem Verein."""
    if AUSGESCHLOSSEN.search(item["link"]):
        return []
    if result := classify(item["titel"], item["teaser"]):
        kategorie, status, match, text = result
        vereine = [find_verein(item["titel"], item["teaser"], match, text)]
    elif SPIELBERICHT_MARKER in item["link"]:
        kategorie, status = "ergebnis", "Spielbericht"
        vereine = vereine_aus_spielbericht_url(item["link"])
        if not vereine:
            print(f"Warnung: Vereine nicht aus Spielbericht-URL lesbar: {item['link']}", file=sys.stderr)
            vereine = [find_verein(item["titel"], item["teaser"])]
    else:
        return []
    return [{
        "verein": verein,
        "spieler": "",  # RSS liefert keine strukturierten Spielernamen
        "kategorie": kategorie,
        "status": status,
        "beschreibung": f"{item['titel']} – {item['teaser']}" if item["teaser"] else item["titel"],
        "quelle": item["link"],
        "erfasst_am": to_iso(item["pub_date"]),
    } for verein in vereine]


def scrape() -> list[dict]:
    items = parse_items(fetch_feed())
    entries = [e for item in items for e in to_entries(item)]
    return sorted(entries, key=lambda e: datetime.fromisoformat(e["erfasst_am"]), reverse=True)


def write_entries(entries: list[dict], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    entries = scrape()
    write_entries(entries)
    print(f"{len(entries)} Einträge nach {OUTPUT_PATH} geschrieben")
