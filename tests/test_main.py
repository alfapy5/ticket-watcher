import json
from datetime import date
from pathlib import Path

from watcher.__main__ import run
from watcher.config import Config
from watcher.models import Game, Listing
from watcher.sources import SourceError

TODAY = date(2026, 11, 13)
G = Game("hockey-2026-11-20", "hockey", date(2026, 11, 20), "Michigan State", "https://www.maizetix.com/games/766")


def L(price, key):
    return Listing(G.id, "maizetix", price, f"https://www.maizetix.com/tickets/{key}", key)


class Box:
    def __init__(self):
        self.sent = []

    def __call__(self, title, body, url):
        self.sent.append((title, body, url))


def go(tmp_path, listings_or_exc, config=Config(), sched=None):
    def fetch(games):
        if isinstance(listings_or_exc, Exception):
            raise listings_or_exc
        return listings_or_exc
    box = Box()
    run(tmp_path / "state.json", config, sched or (lambda: [G]), {"maizetix": fetch}, box, TODAY)
    return box.sent


def test_alert_sent_and_state_saved(tmp_path: Path):
    assert go(tmp_path, [L(3000, "a")]) == []  # first run silent
    sent = go(tmp_path, [L(2500, "b"), L(3000, "a")])
    assert sent == [("Hockey vs Michigan State · 20 nov", "$25.00 en maizetix (antes $30.00)", "https://www.maizetix.com/tickets/b")]
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["games"][G.id]["mins"] == {"maizetix": 2500}


def test_under_max_text(tmp_path: Path):
    sent = go(tmp_path, [L(2000, "a")], Config(max_cents={G.id: 2500}))
    assert sent[0][1] == "$20.00 en maizetix (tu máximo $25.00)"


def test_source_down_alert_once(tmp_path: Path):
    go(tmp_path, [L(3000, "a")])
    assert len(go(tmp_path, SourceError("boom"))) == 1
    assert go(tmp_path, SourceError("boom")) == []
    back = go(tmp_path, [L(3000, "a")])
    assert len(back) == 1 and "vuelve" in back[0][0]


def test_schedule_failure_counts_as_source_down(tmp_path: Path):
    def bad():
        raise SourceError("down")
    sent = go(tmp_path, [], sched=bad)
    assert len(sent) == 1 and "maizetix" in sent[0][0]


def test_first_listing_text(tmp_path: Path):
    go(tmp_path, [])
    sent = go(tmp_path, [L(5000, "a")])
    assert sent[0][1] == "$50.00 en maizetix (antes no había entradas)"


def test_notify_failure_saves_state_and_retries(tmp_path: Path):
    go(tmp_path, [L(3000, "a")])

    def boom(title, body, url):
        raise RuntimeError("ntfy down")
    run(tmp_path / "state.json", Config(), lambda: [G], {"maizetix": lambda g: [L(2500, "b")]}, boom, TODAY)
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["games"][G.id] == {"mins": {"maizetix": 3000}, "alerted": []}  # game rolled back
    assert len(go(tmp_path, [L(2500, "b")])) == 1


def test_games_after_until_ignored(tmp_path: Path):
    seen = []

    def fetch(games):
        seen.extend(games)
        return [L(1000, "a")]
    run(tmp_path / "state.json", Config(until=date(2026, 11, 19)), lambda: [G], {"maizetix": fetch}, Box(), TODAY)
    assert seen == []  # G is Nov 20: not fetched, not stored
    assert json.loads((tmp_path / "state.json").read_text())["games"] == {}
