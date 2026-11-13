import json
from pathlib import Path


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"games": {}, "sources": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
