import argparse
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from .alerts import Alert, decide
from .config import Config, load_config
from .models import Game, Listing
from .sources import SourceError
from .state import load_state, save_state

SPORTS = {"football": "Fútbol americano", "basketball": "Basket", "hockey": "Hockey"}
MONTHS = "ene feb mar abr may jun jul ago sep oct nov dic".split()

Notify = Callable[[str, str, str | None], None]


def money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def alert_text(a: Alert, game: Game, config: Config) -> tuple[str, str, str]:
    title = f"{SPORTS[game.sport]} vs {game.opponent} · {game.date.day} {MONTHS[game.date.month - 1]}"
    if a.reason == "under_max":
        tail = f"tu máximo {money(config.max_cents[game.id])}"
    else:
        tail = "antes no había entradas" if a.prev_min_cents is None else f"antes {money(a.prev_min_cents)}"
    return title, f"{money(a.listing.price_cents)} en {a.listing.source} ({tail})", a.listing.url


def run(
    state_path: Path,
    config: Config,
    schedule: Callable[[], list[Game]],
    fetchers: dict[str, Callable[[list[Game]], list[Listing]]],
    notify: Notify,
    today: date,
) -> None:
    state = load_state(state_path)
    status = state.setdefault("sources", {})
    ok: dict[str, bool] = {}
    fetched: dict[str, list[Listing]] = {}

    try:
        games = [g for g in schedule() if today <= g.date and (config.until is None or g.date <= config.until)]
    except SourceError as e:
        print(e, file=sys.stderr)
        games = []
        ok["maizetix"] = False  # schedule comes from Maizetix

    for name, fetch in fetchers.items():
        if ok.get(name) is False:
            continue
        try:
            fetched[name] = fetch(games)
            ok[name] = True
        except SourceError as e:
            print(e, file=sys.stderr)
            ok[name] = False

    before = state
    alerts, state = decide(state, games, fetched, config, today)

    for name, now_ok in ok.items():
        was_ok = state["sources"].get(name, {}).get("ok", True)
        try:
            if was_ok and not now_ok:
                notify(f"⚠ {name} no responde", "El vigilante no puede leer esta web. Te aviso cuando vuelva.", None)
            elif not was_ok and now_ok:
                notify(f"✓ {name} vuelve a funcionar", "El vigilante vuelve a leer esta web.", None)
        except Exception as e:  # keep old status so the next run retries this notice
            print(f"notify failed for {name} status: {e}", file=sys.stderr)
            continue
        state["sources"][name] = {"ok": now_ok}

    by_id = {g.id: g for g in games}
    for a in alerts:
        try:
            notify(*alert_text(a, by_id[a.game_id], config))
        except Exception as e:  # roll this game back so the next run re-detects and resends
            print(f"notify failed for {a.game_id}: {e}", file=sys.stderr)
            if a.game_id in before.get("games", {}):
                state["games"][a.game_id] = before["games"][a.game_id]
            else:
                state["games"].pop(a.game_id, None)
    save_state(state_path, state)


def main() -> None:
    from .notify import send
    from .sources import maizetix

    p = argparse.ArgumentParser(prog="watcher")
    p.add_argument("--state", type=Path, default=Path("state.json"))
    p.add_argument("--config", type=Path, default=Path("config.toml"))
    p.add_argument("--dry-run", action="store_true", help="print alerts, don't send or save")
    args = p.parse_args()

    if args.dry_run:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console default can't print ⚠/✓

        def notify(title, body, url):
            print(f"[aviso] {title} | {body} | {url}")
        state_path = args.state.with_suffix(".dry.json")  # real state untouched
        if args.state.exists():
            shutil.copy(args.state, state_path)
    else:
        topic = os.environ["NTFY_TOPIC"]
        def notify(title, body, url):
            send(topic, title, body, url)
        state_path = args.state

    today = datetime.now(ZoneInfo("America/Detroit")).date()  # Actions runs in UTC
    run(state_path, load_config(args.config), maizetix.fetch_schedule, {"maizetix": maizetix.fetch_listings}, notify, today)


if __name__ == "__main__":
    main()
