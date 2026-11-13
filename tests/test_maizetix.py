from datetime import date
from pathlib import Path

import pytest

from watcher.models import Game, listing_key
from watcher.sources import SourceError
from watcher.sources.maizetix import parse_game, parse_schedule

FIX = Path(__file__).parent / "fixtures"


def test_parse_schedule_fixture():
    games = parse_schedule((FIX / "maizetix_games.html").read_text(encoding="utf-8"))
    assert len(games) == 28
    by_url = {g.url: g for g in games}
    g = by_url["https://www.maizetix.com/games/765"]
    assert g == Game("hockey-2026-11-14", "hockey", date(2026, 11, 14), "Penn State", g.url)
    assert by_url["https://www.maizetix.com/games/797"].sport == "basketball"
    assert by_url["https://www.maizetix.com/games/797"].opponent == "William & Mary"
    assert by_url["https://www.maizetix.com/games/734"].id == "football-2026-11-21"


def test_parse_schedule_without_jsonld_raises():
    with pytest.raises(SourceError):
        parse_schedule("<html>maintenance</html>")


def test_parse_game_fixture():
    game = Game("hockey-2026-11-14", "hockey", date(2026, 11, 14), "Penn State", "https://www.maizetix.com/games/765")
    listings = parse_game((FIX / "maizetix_game.html").read_text(encoding="utf-8"), game)
    assert len(listings) == 16
    cheapest = min(listings, key=lambda l: l.price_cents)
    assert cheapest.price_cents == 6800
    assert cheapest.url == "https://www.maizetix.com/tickets/63b84c0e6"
    assert cheapest.key == listing_key("maizetix", "63b84c0e6")
    assert {l.source for l in listings} == {"maizetix"}
    assert 6899 in {l.price_cents for l in listings}


G765 = Game("hockey-2026-11-14", "hockey", date(2026, 11, 14), "Penn State", "https://www.maizetix.com/games/765")


def test_parse_game_empty_fixture():
    assert parse_game((FIX / "maizetix_game_empty.html").read_text(encoding="utf-8"), G765) == []


def test_parse_game_shape_change_raises():
    page = (FIX / "maizetix_game.html").read_text(encoding="utf-8").replace("<td>$", '<td class="p">$')
    with pytest.raises(SourceError):
        parse_game(page, G765)


def test_parse_game_interstitial_raises():
    with pytest.raises(SourceError):
        parse_game("<html>Please wait...</html>", G765)


def _ld(ev):
    import json
    return '<script type="application/ld+json">' + json.dumps({"mainEntity": {"itemListElement": [ev]}}) + "</script>"


EV = {"name": "Michigan vs Iowa", "startDate": "2026-11-21T00:30:00Z", "location": {"name": "Crisler Center"}, "url": "https://www.maizetix.com/games/1"}


def test_parse_schedule_utc_converted_to_detroit():
    assert parse_schedule(_ld(EV))[0].id == "basketball-2026-11-20"


def test_parse_schedule_bad_event_raises():
    with pytest.raises(SourceError):
        parse_schedule(_ld({k: v for k, v in EV.items() if k != "startDate"}))


def test_parse_schedule_foreign_url_skipped():
    with pytest.raises(SourceError):  # only event is foreign -> no games
        parse_schedule(_ld({**EV, "url": "https://evil.example/games/1"}))


def test_parse_game_frozen_is_empty():
    # Maizetix freezes sales 1.5 h before the game; counter still says "1 listed"
    assert parse_game((FIX / "maizetix_game_paused.html").read_text(encoding="utf-8"), G765) == []
