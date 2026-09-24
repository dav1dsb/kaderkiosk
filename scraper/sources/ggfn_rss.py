"""getfootballnewsgermany.com (GGFN): Feed abrufen, parsen, relevante Einträge ins Schema überführen.

Englischsprachiger Blog über den deutschen Fußball, auch 2. Bundesliga und Nationalmannschaft. Übernommen
werden Einträge, die sich per englischem Stichwort einer Kategorie zuordnen lassen und einen der 18
Bundesliga-Vereine betreffen. Zusätzlich zu den vier Kader-Kategorien gibt es hier "transfer" für
Wechsel, Wechselgerüchte und Vertragsverlängerungen.

Betriebsregeln (siehe CLAUDE.md): nur der Hauptfeed /feed/ – Kategorie-Feeds und URLs mit Parametern
sperrt die robots.txt; nur Überschrift, Teaser, Link und Datum übernehmen, nie den Artikeltext
(content:encoded) oder Artikelseiten.

Aufruf aus dem Repo-Root:  python -m scraper.sources.ggfn_rss
"""

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

FEED_URL = "https://www.getfootballnewsgermany.com/feed/"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "sources" / "ggfn.json"
USER_AGENT = "KaderKiosk/0.1 (+https://github.com/dav1dsb/kaderkiosk)"

# Bundesliga-Saison 2026/27, Namen wie in sportschau_rss.VEREINE. Aliase englisch, wie GGFN sie in
# Überschriften und Tags verwendet; mehrdeutige Kurzformen wie "Union" oder "Eintracht" bewusst nicht.
VEREINE = {
    "FC Bayern München": r"(?:FC )?Bayern(?: Munich)?",
    "Borussia Dortmund": r"(?:Borussia )?Dortmund|BVB",
    "RB Leipzig": r"(?:RB )?Leipzig",
    "VfB Stuttgart": r"(?:VfB )?Stuttgart|VfB",
    "TSG Hoffenheim": r"(?:TSG )?Hoffenheim",
    "Bayer 04 Leverkusen": r"(?:Bayer (?:04 )?)?Leverkusen|Werkself",
    "SC Freiburg": r"(?:SC )?Freiburg",
    "Eintracht Frankfurt": r"(?:Eintracht )?Frankfurt",
    "FC Augsburg": r"(?:FC )?Augsburg",
    "1. FSV Mainz 05": r"(?:(?:1\. )?FSV )?Mainz(?: 05)?",
    "1. FC Union Berlin": r"(?:1\. )?(?:FC )?Union Berlin|FC Union",
    "Borussia Mönchengladbach": r"(?:Borussia )?(?:Mönchen|Moenchen)?[Gg]ladbach",
    "Hamburger SV": r"Hamburger SV|Hamburg|HSV",
    "1. FC Köln": r"(?:1\. )?(?:FC )?(?:Köln|Koeln|Cologne)",
    "SV Werder Bremen": r"(?:SV )?Werder(?: Bremen)?|Bremen",
    "FC Schalke 04": r"(?:FC )?Schalke(?: 04)?",
    "SV 07 Elversberg": r"(?:SV (?:07 )?)?Elversberg",
    "SC Paderborn 07": r"(?:SC )?Paderborn(?: 07)?",
}
VEREIN_PATTERNS = {name: re.compile(rf"\b(?:{alias})\b") for name, alias in VEREINE.items()}

# (kategorie, status, pattern, auch_in_teaser)
# Wie bei sportschau_rss: Trainer-, Aufstellungs- und Transferwörter tauchen in Teasern beiläufig auf und
# zählen nur in der Überschrift; Verletzungen und Sperren sind auch im Teaser ein starkes Signal.
# Sperren stehen vor Verletzungen, damit "will miss ... through suspension" nicht als Verletzung zählt.
# Neben klaren Fällen auch weiche Formulierungen, wie sie vor allem in Länderspielpausen vorkommen
# ("picked up a knock", "assessed ahead of", "withdrawn from the squad"). Bewusst nicht: bloßes "doubt"
# ("no doubt"), bloßes "knock" ("knocked out of the cup"), "suffered/sustained" ohne Verletzungswort
# ("suffered a defeat", "sustained pressure"), bloßes "setback".
REGELN = [
    ("sperre", "gesperrt", r"suspen(?:ded|sion)|banned for|(?:match|game)[- ]ban", True),
    ("sperre", "Platzverweis", r"red card|sent off|sending[- ]off", True),
    ("verletzung", "fällt aus",
     r"ruled out|sidelined|season-ending|out for (?:the )?(?:season|\w+ (?:weeks|months))|cruciate|\bACL\b|surgery"
     r"|withdrawn from (?:the )?(?:\w+ )*?squad|withdraws? from|pull(?:s|ed)? out of"
     r"|(?:leaves?|left|departs?|departed) (?:the )?(?:\w+ ){0,2}(?:camp|squad)|sent (?:back )?home"
     r"|(?:will|set to|expected to) miss", True),
    ("verletzung", "fraglich",
     r"(?:in |a )?doubt for|doubt over|\bdoubtful\b|fitness (?:concern|worry|doubt|race|issue)s?|race against time|touch and go"
     r"|(?:picked up|picks up|pick up|sustained|suffered|nursing|carrying|shakes? off|shook off) (?:a |an )?(?:\w+ )?knock"
     r"|\ba (?:minor |slight |small )?knock\b|(?:will be |to be |being |was )?assessed (?:ahead of|before|after|by)"
     r"|fitness test|injury (?:concern|scare|doubt|worry|cloud)s?|precaution\w*|discomfort"
     r"|managing (?:his )?(?:workload|minutes)", True),
    ("verletzung", "zurück",
     r"return(?:s|ed)? to (?:full )?training|back in (?:full )?training|return from injury|injury return|fit again"
     r"|back to (?:full )?training|(?:nearing|nears|closing in on) (?:a |his )?return|available again"
     r"|comeback from injury|fit to (?:play|feature|start)", True),
    ("verletzung", "verletzt",
     r"injur\w*|hamstring|\bcalf\b|\bankle\b|(?:muscle|thigh|knee) (?:problem|issue|tear|strain)|fracture|concussion"
     r"|limp(?:ed|s)? off|forced off|came off (?:injured|with)|substituted (?:off )?(?:injured|with|due to)"
     r"|(?:suffered|sustained) (?:a |an )?(?:\w+ )?(?:strain|sprain|tear|fracture|problem)"
     r"|\bgroin\b|adductor|achilles|sprain\w*|\btorn\b|(?:muscle|ligament|meniscus) tear|bruis\w*"
     r"|illness|\bsick(?:ness)?\b|f[ae]lls? ill", True),
    ("transfer", "Vertrag", r"contract (?:extension|renewal|talks)|extends? (?:his )?(?:contract|deal)|renews? (?:his )?(?:contract|deal)|signs? (?:a )?new (?:deal|contract)", False),
    ("transfer", "Wechsel", r"completes? (?:his )?(?:move|transfer|switch)|seals? (?:a |his )?(?:move|transfer|switch)|\bsigns? for\b|\bsigned\b|joins? (?:on loan|on a (?:free|permanent))|loan (?:move|deal|spell)", False),
    ("transfer", "Gerücht", r"linked with|interest(?:ed)? in|\btargets?\b|\beye(?:s|ing)\b|monitor(?:s|ing)\b|\bbid\b|transfer|\bmove to\b|release clause", False),
    ("pressekonferenz", "Pressekonferenz", r"press conference|pre-match|post-match|presser", False),
    ("pressekonferenz", "Trainerwechsel", r"\bsacked\b|dismissed|new (?:head )?coach|appointed|successor|takes charge|parts? ways", False),
    ("pressekonferenz", "Trainer-News", r"\b(?:head )?coach\b|\bmanager\b|\bboss\b", False),
    ("aufstellung", "voraussichtlich", r"line-?up|starting (?:XI|eleven)|\bdropped\b|\bbenched\b|rotation", False),
]
REGELN = [(k, s, re.compile(p, re.IGNORECASE), t) for k, s, p, t in REGELN]


def fetch_feed(url: str = FEED_URL) -> bytes:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()
    return response.content


def clean_teaser(raw: str) -> str:
    """Erster Absatz, ohne HTML und Entities (WordPress kürzt teils mit "[…]")."""
    text = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
    return re.sub(r"\s+", " ", text.split("\n\n")[0]).strip()


def parse_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iterfind("./channel/item"):
        items.append({
            "titel": html.unescape(item.findtext("title") or "").strip(),
            "teaser": clean_teaser(item.findtext("description") or ""),
            "link": (item.findtext("link") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
            "tags": [c.text.strip() for c in item.iterfind("category") if c.text],
        })
    return items


def classify(titel: str, teaser: str) -> tuple[str, str] | None:
    """Erst alle Regeln gegen die Überschrift, dann die Teaser-Regeln gegen den Teaser; je Text gewinnt
    die erste passende Regel. Liefert (kategorie, status)."""
    for text, nur_teaser_regeln in ((titel, False), (teaser, True)):
        for kategorie, status, pattern, auch_teaser in REGELN:
            if (auch_teaser or not nur_teaser_regeln) and pattern.search(text):
                return kategorie, status
    return None


def vereine_in(text: str) -> list[str]:
    """Genannte Vereine in Reihenfolge ihres ersten Auftretens."""
    treffer = [(m.start(), name) for name, p in VEREIN_PATTERNS.items() if (m := p.search(text))]
    return [name for _, name in sorted(treffer)]


def find_verein(item: dict) -> str | None:
    """Verein aus Tags und Überschrift. Bei mehreren gewinnt der zuerst in der Überschrift genannte – in
    englischen Headlines steht der betroffene Verein vorn, der Gegner hinter "for"/"against"/"ahead of".
    Nennt die Überschrift keinen, grenzt der Teaser ein. None: kein Bundesliga-Verein betroffen (Eintrag
    verwerfen). "": mehrdeutig, leer statt geraten."""
    kandidaten = {name for tag in item["tags"] for name, p in VEREIN_PATTERNS.items() if p.fullmatch(tag)}
    kandidaten |= set(vereine_in(item["titel"]))
    if len(kandidaten) <= 1:
        return next(iter(kandidaten), None)
    for text in (item["titel"], item["teaser"]):
        if genannt := [name for name in vereine_in(text) if name in kandidaten]:
            return genannt[0]
    return ""


def to_iso(pub_date: str) -> str:
    try:
        return parsedate_to_datetime(pub_date).isoformat()
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_entry(item: dict) -> dict | None:
    if not (result := classify(item["titel"], item["teaser"])):
        return None
    if (verein := find_verein(item)) is None:
        return None
    kategorie, status = result
    return {
        "verein": verein,
        "spieler": "",  # RSS liefert keine strukturierten Spielernamen
        "kategorie": kategorie,
        "status": status,
        "beschreibung": f"{item['titel']} – {item['teaser']}" if item["teaser"] else item["titel"],
        "quelle": item["link"],
        "erfasst_am": to_iso(item["pub_date"]),
    }


def scrape() -> list[dict]:
    entries = [e for item in parse_items(fetch_feed()) if (e := to_entry(item))]
    return sorted(entries, key=lambda e: datetime.fromisoformat(e["erfasst_am"]), reverse=True)


def write_entries(entries: list[dict], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    entries = scrape()
    write_entries(entries)
    print(f"{len(entries)} Einträge nach {OUTPUT_PATH} geschrieben")
