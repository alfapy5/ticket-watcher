from datetime import date

from watcher.alerts import decide
from watcher.config import Config
from watcher.models import Game, Listing

TODAY = date(2026, 11, 13)
G = Game("hockey-2026-11-20", "hockey", date(2026, 11, 20), "Wisconsin", "u")


def L(price, key="k1", source="maizetix"):
    return Listing(G.id, source, price, "url-" + key, key)


def state_with(mins, alerted=()):
    return {"games": {G.id: {"mins": dict(mins), "alerted": list(alerted)}}, "sources": {}}


def test_first_run_silent():
    alerts, s = decide({}, [G], {"maizetix": [L(2000)]}, Config(), TODAY)
    assert alerts == []
    assert s["games"][G.id]["mins"] == {"maizetix": 2000}


def test_new_min_alert():
    alerts, _ = decide(state_with({"maizetix": 3000}), [G], {"maizetix": [L(2800, "k2"), L(3000)]}, Config(), TODAY)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.reason == "new_min" and a.listing.price_cents == 2800 and a.prev_min_cents == 3000


def test_drop_under_1_dollar_ignored():
    alerts, _ = decide(state_with({"maizetix": 3000}), [G], {"maizetix": [L(2950, "k2")]}, Config(), TODAY)
    assert alerts == []


def test_no_repeat_alert():
    alerts, _ = decide(state_with({"maizetix": 3000}, ["k2"]), [G], {"maizetix": [L(2800, "k2")]}, Config(), TODAY)
    assert alerts == []


def test_min_rises_silently():
    alerts, s = decide(state_with({"maizetix": 2000}), [G], {"maizetix": [L(3500, "k2")]}, Config(), TODAY)
    assert alerts == []
    assert s["games"][G.id]["mins"] == {"maizetix": 3500}


def test_missing_source_keeps_old_min():
    st = state_with({"seatgeek": 3000, "maizetix": 1500})
    alerts, s = decide(st, [G], {"seatgeek": [L(2900, "k2", "seatgeek")]}, Config(), TODAY)
    assert alerts == []
    assert s["games"][G.id]["mins"] == {"seatgeek": 2900, "maizetix": 1500}


def test_source_with_no_listings_drops_its_min():
    alerts, s = decide(state_with({"maizetix": 1500}), [G], {"maizetix": []}, Config(), TODAY)
    assert alerts == [] and s["games"][G.id]["mins"] == {}


def test_under_max_alert_even_first_run():
    alerts, _ = decide({}, [G], {"maizetix": [L(2400)]}, Config(max_cents={G.id: 2500}), TODAY)
    assert [a.reason for a in alerts] == ["under_max"]


def test_new_min_and_under_max_same_listing_one_alert():
    alerts, _ = decide(state_with({"maizetix": 3000}), [G], {"maizetix": [L(2000, "k2")]}, Config(max_cents={G.id: 2500}), TODAY)
    assert len(alerts) == 1


def test_muted_game_ignored():
    alerts, s = decide(state_with({"maizetix": 3000}), [G], {"maizetix": [L(1000, "k2")]}, Config(muted={G.id}), TODAY)
    assert alerts == []


def test_past_games_pruned():
    old = {"games": {"hockey-2026-11-01": {"mins": {"maizetix": 1}, "alerted": []}}, "sources": {}}
    _, s = decide(old, [G], {"maizetix": [L(2000)]}, Config(), TODAY)
    assert "hockey-2026-11-01" not in s["games"]


def test_input_state_not_mutated():
    st = state_with({"maizetix": 3000})
    decide(st, [G], {"maizetix": [L(2000, "k2")]}, Config(), TODAY)
    assert st == state_with({"maizetix": 3000})


def test_first_listing_after_none_alerts():
    alerts, _ = decide(state_with({}), [G], {"maizetix": [L(5000)]}, Config(), TODAY)
    assert [(a.reason, a.prev_min_cents) for a in alerts] == [("new_min", None)]
