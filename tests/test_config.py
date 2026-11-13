from pathlib import Path

from watcher.config import load_config
from watcher.models import listing_key


def test_load_config(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text('muted = ["hockey-2026-11-13"]\n\n[max]\n"hockey-2026-11-21" = 25\n"basketball-2026-11-15" = 12.5\n', encoding="utf-8")
    c = load_config(p)
    assert c.max_cents == {"hockey-2026-11-21": 2500, "basketball-2026-11-15": 1250}
    assert c.muted == {"hockey-2026-11-13"}


def test_missing_file_is_empty_config(tmp_path: Path):
    c = load_config(tmp_path / "nope.toml")
    assert c.max_cents == {} and c.muted == set()


def test_listing_key_stable_and_short():
    a = listing_key("maizetix", "63b84c0e6")
    assert a == listing_key("maizetix", "63b84c0e6")
    assert len(a) == 16
    assert a != listing_key("seatgeek", "63b84c0e6")


def test_until_date(tmp_path: Path):
    from datetime import date
    p = tmp_path / "config.toml"
    p.write_text('until = 2026-12-20\n', encoding="utf-8")
    assert load_config(p).until == date(2026, 12, 20)
    assert load_config(tmp_path / "nope.toml").until is None
