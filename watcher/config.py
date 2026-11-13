import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Config:
    max_cents: dict[str, int] = field(default_factory=dict)
    muted: set[str] = field(default_factory=set)
    until: date | None = None  # ignore games after this date


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return Config(
        max_cents={k: round(float(v) * 100) for k, v in data.get("max", {}).items()},
        muted=set(data.get("muted", [])),
        until=data.get("until"),  # TOML bare date parses to datetime.date
    )
