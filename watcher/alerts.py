import copy
from dataclasses import dataclass
from datetime import date
from typing import Literal

from .config import Config
from .models import Game, Listing

MIN_DROP_CENTS = 100  # spec: alert only on drops of at least $1


@dataclass(frozen=True)
class Alert:
    game_id: str
    reason: Literal["new_min", "under_max"]
    listing: Listing
    prev_min_cents: int | None


def decide(state: dict, games: list[Game], fetched: dict[str, list[Listing]], config: Config, today: date) -> tuple[list[Alert], dict]:
    """fetched holds only sources that succeeded this run; a missing source keeps its last min."""
    state = copy.deepcopy(state) if state else {}
    all_games = state.setdefault("games", {})
    state.setdefault("sources", {})
    alerts: list[Alert] = []

    for game in games:
        if game.id in config.muted or game.date < today:
            continue
        first_seen = game.id not in all_games
        g = all_games.setdefault(game.id, {"mins": {}, "alerted": []})
        prev_min = min(g["mins"].values(), default=None)

        run: list[Listing] = []
        for source, listings in fetched.items():
            mine = [l for l in listings if l.game_id == game.id]
            run += mine
            if mine:
                g["mins"][source] = min(l.price_cents for l in mine)
            else:
                g["mins"].pop(source, None)
        if not run:
            continue

        cheapest = min(run, key=lambda l: l.price_cents)
        if cheapest.key in g["alerted"]:
            continue
        max_cents = config.max_cents.get(game.id)
        if max_cents is not None and cheapest.price_cents <= max_cents:
            alerts.append(Alert(game.id, "under_max", cheapest, prev_min))
        elif not first_seen and (prev_min is None or cheapest.price_cents <= prev_min - MIN_DROP_CENTS):
            alerts.append(Alert(game.id, "new_min", cheapest, prev_min))
        else:
            continue
        g["alerted"].append(cheapest.key)

    for gid in list(all_games):
        if date.fromisoformat(gid.split("-", 1)[1]) < today:
            del all_games[gid]
    return alerts, state
