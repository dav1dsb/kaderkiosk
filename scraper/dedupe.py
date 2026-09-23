"""Duplikat-Erkennung für zusammengeführte Einträge.

Schlüssel: quelle (Artikel-URL) + verein. Ein Spielbericht mit zwei Vereinen bleibt so zwei Einträge,
derselbe Artikel für denselben Verein aber nur einer. Meldungen verschiedener Quellen über dasselbe Ereignis
haben unterschiedliche URLs und gelten nicht als Duplikat.
"""

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """Schema und Host klein, ohne Fragment und abschließenden Schrägstrich – Query bleibt erhalten."""
    teile = urlsplit(url.strip())
    return urlunsplit((teile.scheme.lower(), teile.netloc.lower(), teile.path.rstrip("/"), teile.query, ""))


def zeitpunkt(entry: dict) -> datetime:
    dt = datetime.fromisoformat(entry["erfasst_am"])
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def dedupe(entries: list[dict]) -> list[dict]:
    """Pro Schlüssel bleibt der früheste Eintrag (erste Meldung); bei Gleichstand der zuerst gelesene."""
    behalten: dict[tuple[str, str], dict] = {}
    for entry in entries:
        key = (normalize_url(entry["quelle"]), entry["verein"])
        if key not in behalten or zeitpunkt(entry) < zeitpunkt(behalten[key]):
            behalten[key] = entry
    return list(behalten.values())
