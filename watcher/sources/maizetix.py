import html
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from ..models import Game, Listing, listing_key
from . import SourceError

BASE = "https://www.maizetix.com"
UA = {"User-Agent": "ticket-watcher (personal price alerts)"}
DETROIT = ZoneInfo("America/Detroit")
VENUES = {"Michigan Stadium": "football", "Crisler Center": "basketball", "Yost Ice Arena": "hockey"}
JSONLD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ROW = re.compile(r"<tr\b.*?</tr>", re.S)
PRICE = re.compile(r"<td>\s*\$([\d,]+(?:\.\d\d)?)\s*</td>")
LISTED = re.compile(r"(\d+)\s+listed\b")
FROZEN = "All buying and selling for this game are now paused"
TICKET = re.compile(r"maizetix\.com/tickets/([A-Za-z0-9]+)")


def parse_schedule(page: str) -> list[Game]:
    games = []
    try:
        for block in JSONLD.findall(page):
            data = json.loads(block)
            for ev in data.get("mainEntity", {}).get("itemListElement", []):
                sport = VENUES.get(ev.get("location", {}).get("name"))
                if not sport or not ev["url"].startswith(BASE + "/games/"):
                    continue  # ponytail: unknown venue skipped; add to VENUES if Maizetix lists one
                day = datetime.fromisoformat(ev["startDate"].replace("Z", "+00:00")).astimezone(DETROIT).date()
                opponent = html.unescape(ev["name"]).split(" vs ", 1)[-1]
                games.append(Game(f"{sport}-{day.isoformat()}", sport, day, opponent, ev["url"]))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise SourceError(f"maizetix: schedule JSON-LD changed: {e!r}") from e
    if not games:
        raise SourceError("maizetix: no games found in /games (page changed?)")
    return games


def parse_game(page: str, game: Game) -> list[Listing]:
    """Raises SourceError unless the parsed rows match the page's own "N listed" counter,
    so a template change can't silently look like "no tickets"."""
    out = []
    if FROZEN in page:  # sales closed 1.5 h before the game: nothing buyable
        return out
    for row in ROW.findall(page):
        price, ticket = PRICE.search(row), TICKET.search(row)
        if price and ticket:
            cents = round(float(price.group(1).replace(",", "")) * 100)
            tid = ticket.group(1)
            out.append(Listing(game.id, "maizetix", cents, f"{BASE}/tickets/{tid}", listing_key("maizetix", tid)))
    m = LISTED.search(re.sub(r"<[^>]+>", " ", page))
    if not m or int(m.group(1)) != len(out):
        raise SourceError(f"maizetix: {game.url} parsed {len(out)} rows, page says {m and m.group(1)} listed")
    return out


def _get(url: str) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=15)
    except requests.RequestException as e:
        raise SourceError(f"maizetix: {e}") from e
    if r.status_code != 200:
        raise SourceError(f"maizetix: HTTP {r.status_code} on {url}")
    return r.text


def fetch_schedule() -> list[Game]:
    return parse_schedule(_get(f"{BASE}/games"))


def fetch_listings(games: list[Game]) -> list[Listing]:
    out = []
    for g in games:
        out += parse_game(_get(g.url), g)
        time.sleep(1)  # be polite: ~30 pages per run
    return out
