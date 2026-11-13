# Ticket Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push-notify the user when a cheaper resale ticket appears for a Michigan men's home game (basketball, hockey, football), across SeatGeek, StubHub, Vivid Seats and Maizetix.

**Architecture:** One Python package `watcher`. Each source returns `Listing`s for known games; a pure function `decide()` compares them with the stored per-source minimums and returns alerts plus the new state. GitHub Actions runs it on cron and commits `state.json` back to the public repo; a Windows scheduled task runs Maizetix locally when the cloud session is down.

**Tech Stack:** Python 3.12, `requests`, `playwright` (Maizetix and any HTML source that needs a browser), `pytest`, stdlib `tomllib`/`json`/`hashlib`, ntfy.sh, GitHub Actions, Windows Task Scheduler.

**Spec:** `docs/design.md`

## Global Constraints

- Always 1 ticket. Men's home games only: basketball, hockey, football.
- Prices are compared all-in (fees included), stored as integer cents.
- New-minimum alert only when the price drops at least $1 (100 cents) below the lowest price currently on sale.
- First observation of a game is silent, except for max-price alerts the user set explicitly.
- Never alert twice for the same listing key.
- Never bypass CAPTCHAs or anti-bot protection. A source that blocks is dropped, not worked around.
- Never store the UMich password. Maizetix cookies live only in a GitHub Secret (`MAIZETIX_COOKIES`) and in the local browser profile.
- Public `state.json` holds only per-source minimum cents and SHA-256-hashed listing keys. No seller data, no Maizetix listing details.
- Cron: public sources every 15 min, Maizetix in the cloud every 30 min.
- Secrets: `NTFY_TOPIC`, `SEATGEEK_CLIENT_ID`, `MAIZETIX_COOKIES`.
- **The user does every git commit.** Steps marked "Checkpoint" mean: stop, tell the user what's ready to commit.

## Review Focus

1. **A source fails or is skipped this run** (blocked, timeout, Maizetix not in this cron). Expected: its last known minimum is kept, so the next successful run doesn't fire a fake "drop". Covered by the per-source state in Task 2: `test_missing_source_keeps_old_min`.
2. **The cheapest listing sells, and a pricier one becomes the minimum.** Expected: no alert, and the reference minimum rises. Test: `test_min_rises_silently`.
3. **The same cheap listing is still up on the next run.** Expected: no repeat alert. Test: `test_no_repeat_alert`.
4. **A source keeps failing.** Expected: one ntfy alert when it starts failing and one when it recovers, not one per run. Test in Task 4: `test_source_down_alert_once`.
5. **The game is in the past.** Expected: it's dropped from state and never alerted. Test: `test_past_games_pruned`.

---

### Task 0: Source recon (spike, throwaway)

Findings decide Tasks 5–7. No production code.

**Files:**
- Create: `docs/sources.md`

- [ ] **Step 1: SeatGeek.** The user gets a `client_id` at seatgeek.com/account/develop; Claude does not create accounts. Call `GET https://api.seatgeek.com/2/events?performers.slug=michigan-wolverines-football&venue.city=Ann+Arbor&client_id=…` and the same for `-basketball` and `-hockey`. Record whether `stats.lowest_price` is all-in or base price, and whether events carry a stable `id`, `datetime_local` and `url`.
- [ ] **Step 2: StubHub and Vivid Seats.** Fetch one Michigan home-game page with plain `requests`, then with Playwright headless. Record: blocked (403, CAPTCHA, empty challenge page) → **source dropped**; readable → where the cheapest all-in price and listing id live (JSON in page, XHR endpoint).
- [ ] **Step 3: Maizetix.** With the user logged in in a Playwright persistent profile (`.maizetix-profile/`, gitignored), record: the events listing URL, how listings and prices appear (HTML or XHR JSON), whether prices include fees, which cookies make up the session, and what an expired session looks like (redirect to `weblogin.umich.edu`).
- [ ] **Step 4: Write `docs/sources.md`** with one section per source: status (keep or drop), request, fields, expired or blocked signature.
- [ ] **Checkpoint.** Show the user the findings, and which sources are dropped.

### Task 1: Models and config

**Files:**
- Create: `watcher/__init__.py`, `watcher/models.py`, `watcher/config.py`, `config.toml`, `pyproject.toml`, `.gitignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Game(id: str, sport: str, date: date, opponent: str)`, where `id = f"{sport}-{date.isoformat()}"` and `sport` is in `{"football","basketball","hockey"}`
  - `@dataclass(frozen=True) Listing(game_id: str, source: str, price_cents: int, url: str, key: str)`
  - `listing_key(source: str, raw_id: str) -> str`: SHA-256 hex of `f"{source}:{raw_id}"`, first 16 chars
  - `@dataclass Config(max_cents: dict[str, int], muted: set[str])`
  - `load_config(path: Path) -> Config`

`config.toml` format, editable from a phone:
```toml
# Partidos a ignorar
muted = []

# Precio máximo en dólares por partido (opcional). id = deporte-AAAA-MM-DD
[max]
"hockey-2026-11-21" = 25
```

- [ ] **Step 1: Write the failing tests.** `test_load_config` (`$25` → `2500` cents, muted set), `test_missing_file_is_empty_config`, `test_listing_key_stable_and_short` (same input gives the same 16-char key; different source gives a different key).
- [ ] **Step 2:** Run `pytest tests/test_config.py -v`. Expected: FAIL (import error).
- [ ] **Step 3:** Implement with `tomllib`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Checkpoint.**

### Task 2: Alert decision (core logic)

**Files:**
- Create: `watcher/alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: `Game`, `Listing`, `Config` (Task 1)
- Produces:
  - State shape (plain dict, JSON-serializable): `{"games": {game_id: {"mins": {source: cents}, "alerted": [key, ...]}}, "sources": {source: {"ok": bool}}}`
  - `@dataclass Alert(game_id: str, reason: Literal["new_min","under_max"], listing: Listing, prev_min_cents: int | None)`
  - `decide(state: dict, games: list[Game], fetched: dict[str, list[Listing]], config: Config, today: date) -> tuple[list[Alert], dict]`, where `fetched` holds only the sources that **succeeded** this run

Algorithm (not determined by the signature):
```
for each game (not muted, date >= today):
  g = state game entry (create if missing; first_seen = it was missing)
  prev_min = min(g.mins.values()) or None
  for each fetched source: g.mins[source] = min price of its listings for this game (remove the key if none)
  cheapest = cheapest listing this run across fetched sources
  if cheapest and not first_seen and prev_min is not None
     and cheapest.price <= prev_min - 100 and cheapest.key not in alerted -> Alert new_min
  for listing in this run with price <= config.max_cents[game] and key not in alerted -> Alert under_max (cheapest only)
  add alerted keys
drop games with date < today
```

- [ ] **Step 1: Write the failing tests** (each builds state, games and fetched by hand):
  - `test_first_run_silent`: new game with a $20 listing → no alerts; `mins == {"seatgeek": 2000}`
  - `test_new_min_alert`: prev mins `{seatgeek: 3000}`, new listing 2800 → one `new_min` alert, `prev_min_cents == 3000`
  - `test_drop_under_1_dollar_ignored`: 3000 → 2950 → no alert
  - `test_no_repeat_alert`: same key already in `alerted` → no alert
  - `test_min_rises_silently`: 2000 → 3500 → no alert, mins updated to 3500
  - `test_missing_source_keeps_old_min`: mins `{seatgeek: 3000, maizetix: 1500}`, fetched only seatgeek at 2900 → no alert (prev overall min is 1500), maizetix stays 1500
  - `test_under_max_alert_even_first_run`: max 2500, first-seen listing 2400 → one `under_max`
  - `test_muted_game_ignored`
  - `test_past_games_pruned`
- [ ] **Step 2:** Run `pytest tests/test_alerts.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `decide` as above. Pure function, no I/O, returns a new state dict.
- [ ] **Step 4:** Run the tests. Expected: 9 PASS.
- [ ] **Checkpoint.**

### Task 3: Schedule (home games)

**Files:**
- Create: `watcher/sources/__init__.py`, `watcher/sources/seatgeek.py`
- Test: `tests/test_seatgeek.py`, fixture `tests/fixtures/seatgeek_events.json` (a real response saved in Task 0, trimmed)

**Interfaces:**
- Produces:
  - `class SourceError(Exception)` and `class SessionExpired(SourceError)` in `watcher/sources/__init__.py`
  - `parse_events(payload: dict, sport: str) -> list[tuple[Game, Listing | None]]`: keeps only events in Ann Arbor; skips women's teams
  - `fetch_seatgeek(client_id: str) -> tuple[list[Game], list[Listing]]`: three calls (football, basketball, hockey slugs); raises `SourceError` on non-200 or timeout (10 s)
- SeatGeek doubles as the schedule. Its listing per game = event-level lowest price, with `key = listing_key("seatgeek", f"{event_id}:{price_cents}")`. The URL is the event URL. If Task 0 found the price is base, not all-in, store it as-is and add `# ponytail: base price, fees not included` at the parse site.

- [ ] **Step 1: Write the failing tests.** `test_parse_events_fixture` (expected game ids and cents from the fixture), `test_event_without_price_has_no_listing`, `test_non_ann_arbor_dropped`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Checkpoint.**

### Task 4: Notify, state I/O, entry point

**Files:**
- Create: `watcher/notify.py`, `watcher/state.py`, `watcher/__main__.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - `send(topic: str, title: str, body: str, url: str | None) -> None`: `POST https://ntfy.sh/{topic}` with headers `Title` and `Click`; raises on non-2xx
  - `load_state(path) -> dict` (missing file → empty shape), `save_state(path, state) -> None` (sorted keys, indent 1)
  - CLI: `python -m watcher --sources public|maizetix [--state state.json] [--dry-run]`
  - `run(sources: str, state_path: Path, config: Config, fetchers: dict[str, Callable[[list[Game]], list[Listing]]], notify: Callable, today: date) -> None`: the testable core of `__main__`

Behavior:
- Schedule always comes from SeatGeek. If SeatGeek fails, the run alerts "SeatGeek caído" (through source-status logic) and exits 0 without changing mins.
- Each fetcher is wrapped: on `SourceError` it is left out of `fetched`. A source's `ok` flips true→false → one notification "⚠ {source} no responde"; false→true → "✓ {source} vuelve a funcionar".
- `SessionExpired` from Maizetix → "Sesión de Maizetix caducada: inicia sesión en el portátil" (once), and `state["sources"]["maizetix"]["ok"] = False`.
- Alert text: title `"{Sport} vs {opponent} · {date}"`, body `"${price} en {source} (antes ${prev})"` or `"${price} en {source} (tu máximo ${max})"`, click = listing URL.

- [ ] **Step 1: Write the failing tests** with fake fetchers and a list-collecting `notify`: `test_alert_sent_and_state_saved`, `test_source_down_alert_once` (fails twice → one notification, recovers → one), `test_session_expired_notifies_once`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Run `python -m watcher --sources public --dry-run` with a real `SEATGEEK_CLIENT_ID`. Expected: prints the game list and "no alerts" (first run silent).
- [ ] **Checkpoint.**

### Task 5: StubHub and Vivid Seats (only the ones Task 0 kept)

**Files:**
- Create: `watcher/sources/stubhub.py`, `watcher/sources/vividseats.py`
- Test: `tests/test_html_sources.py`, plus a saved page or JSON fixture per source

**Interfaces:**
- Produces: `parse_stubhub(payload, games: list[Game]) -> list[Listing]`, `fetch_stubhub(games) -> list[Listing]` (same pair for vividseats). Match an event to a game by sport and local date. Raise `SourceError` on a block signature recorded in `docs/sources.md`.

- [ ] **Step 1:** Write a fixture-based parse test per source: expected cheapest all-in cents and key.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement. Register in the `public` fetchers dict.
- [ ] **Step 4:** Run the tests. Expected: PASS. Then run `python -m watcher --sources public --dry-run`. Expected: listings from each kept source.
- [ ] **Checkpoint.**

### Task 6: Maizetix (cloud and laptop)

**Files:**
- Create: `watcher/sources/maizetix.py`, `scripts/maizetix_login.py`
- Test: `tests/test_maizetix.py` + fixture

**Interfaces:**
- Produces:
  - `parse_maizetix(payload, games) -> list[Listing]`
  - `fetch_maizetix(games, cookies: list[dict] | None = None, profile_dir: Path | None = None) -> list[Listing]`: cloud passes `cookies` (from `MAIZETIX_COOKIES` JSON); laptop passes `profile_dir`. Raises `SessionExpired` on the expired signature from Task 0.
  - `scripts/maizetix_login.py`: opens a headed Playwright persistent context at `.maizetix-profile/`, waits until the user has logged in (including Duo) and closes the window, then pipes the session cookies (JSON) into `gh secret set MAIZETIX_COOKIES`. Never prints the cookies.

- [ ] **Step 1: Write the failing tests.** `test_parse_maizetix_fixture`, `test_expired_signature_raises` (fixture with a weblogin redirect).
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** The user runs `python scripts/maizetix_login.py`, then `python -m watcher --sources maizetix --dry-run`. Expected: Maizetix listings, no alerts.
- [ ] **Checkpoint.**

### Task 7: GitHub Actions

**Files:**
- Create: `.github/workflows/watch.yml`, `requirements.txt`

Decisions:
- Two schedules in one workflow: `*/15 * * * *` → `--sources public`; `*/30 * * * *` → `--sources maizetix` (skipped if `state.json` says maizetix `ok: false`, so a dead session doesn't hammer UMich).
- `concurrency: { group: watch, cancel-in-progress: false }` so state commits don't race.
- After the run: `git add state.json`, commit as `github-actions[bot]` with message `state`, then push. **This bot commit is the only automated commit, and it touches only `state.json`.** The user approved a public repo with state persistence; confirm with the user once before enabling it.
- `permissions: contents: write`. Python 3.12, `pip install -r requirements.txt`, `playwright install chromium --with-deps` only on the maizetix job.

- [ ] **Step 1:** Write the workflow.
- [ ] **Step 2:** The user creates the public GitHub repo and adds the three secrets. Claude does not create the repo or set secrets without an explicit yes.
- [ ] **Step 3:** Trigger with `workflow_dispatch`. Expected: green run; `state.json` committed with games and mins; no notification (first run).
- [ ] **Checkpoint.**

### Task 8: Laptop fallback (Windows)

**Files:**
- Create: `scripts/laptop_run.py`, `scripts/install_task.ps1`

**Interfaces:**
- `laptop_run.py`: reads `https://raw.githubusercontent.com/<user>/<repo>/main/state.json`. If `sources.maizetix.ok` is true, it exits silently (the cloud has it). Otherwise it runs `run("maizetix", Path.home()/".ticket-watcher/state.json", …)` with `profile_dir=.maizetix-profile`. Repo URL comes from the `TW_REPO` env var.
- `install_task.ps1`: registers the scheduled task `TicketWatcherMaizetix` with triggers at logon, on workstation unlock, and every 15 min, running `pythonw scripts\laptop_run.py`.

- [ ] **Step 1:** Write a test in `tests/test_laptop.py`: `test_skips_when_cloud_ok` (fake fetch of the remote state).
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement both files.
- [ ] **Step 4:** Run the test. Expected: PASS. Then run `powershell -File scripts\install_task.ps1`. Expected: `Get-ScheduledTask TicketWatcherMaizetix` shows `Ready`.
- [ ] **Step 5:** The user installs ntfy on their phone and subscribes to the topic. Lower a max price in `config.toml` below a current price to force one real `under_max` alert end to end. Expected: notification arrives on the phone, and tapping it opens the listing. Restore `config.toml`.
- [ ] **Checkpoint.**
