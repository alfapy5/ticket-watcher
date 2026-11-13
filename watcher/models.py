import hashlib
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Game:
    id: str  # f"{sport}-{date.isoformat()}"
    sport: str  # football | basketball | hockey
    date: date
    opponent: str
    url: str


@dataclass(frozen=True)
class Listing:
    game_id: str
    source: str
    price_cents: int  # all-in, fees included
    url: str
    key: str  # hashed, safe to store publicly


def listing_key(source: str, raw_id: str) -> str:
    return hashlib.sha256(f"{source}:{raw_id}".encode()).hexdigest()[:16]
