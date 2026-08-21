from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import Proxy, parse_ts, utcnow

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
NEW_SCORE = 50.0
SUCCESS_BONUS = 5.0
FAIL_PENALTY = 15.0
DAILY_DECAY = 0.95
PRUNE_DAYS = 7.0


def load(path: Path) -> dict:
    """Load history state; corrupt file is backed up and replaced with fresh state."""
    if not path.exists():
        return {"version": SCHEMA_VERSION, "proxies": {}}
    try:
        data = json.loads(path.read_text())
        assert isinstance(data.get("proxies"), dict)
        return data
    except Exception:  # noqa: BLE001
        backup = path.with_suffix(".json.bak")
        log.warning("history corrupt, backing up to %s and starting fresh", backup)
        path.replace(backup)
        return {"version": SCHEMA_VERSION, "proxies": {}}


def save(history: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    history["updated"] = utcnow().isoformat()
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def apply_score(entry: dict, *, success: bool, now=None) -> float:
    """Decay stored score by DAILY_DECAY per day since last_seen, then apply delta."""
    now = now or utcnow()
    days = max((now - parse_ts(entry["last_seen"])).total_seconds() / 86400, 0.0)
    score = float(entry.get("score", NEW_SCORE)) * (DAILY_DECAY ** days)
    score += SUCCESS_BONUS if success else -FAIL_PENALTY
    return round(min(max(score, 0.0), 100.0), 1)


def update(alive: list[Proxy], tested: list[Proxy], path: Path) -> None:
    """Merge run results into history. `tested` includes every checked proxy."""
    history = load(path)
    entries = history["proxies"]
    now = utcnow()
    alive_keys = {p.key for p in alive}

    for p in tested:
        entry = entries.get(p.key) or {
            "score": NEW_SCORE,
            "last_seen": p.last_seen,
            "success": 0,
            "fail": 0,
            "protocol": p.protocol,
        }
        success = p.key in alive_keys
        entry["score"] = apply_score(entry, success=success, now=now)
        entry["protocol"] = p.protocol
        if success:
            entry["last_seen"] = p.last_seen
            entry["success"] += 1
        else:
            entry["fail"] += 1
        entries[p.key] = entry

    cutoff = now.timestamp() - PRUNE_DAYS * 86400
    pruned = [k for k, e in entries.items() if parse_ts(e["last_seen"]).timestamp() < cutoff]
    for k in pruned:
        del entries[k]

    save(history, path)
    log.info("scorer: %d entries (%d pruned)", len(entries), len(pruned))


def attach_scores(proxies: list[Proxy], path: Path) -> None:
    """Copy stored scores onto the current proxy objects."""
    entries = load(path)["proxies"]
    for p in proxies:
        entry = entries.get(p.key)
        if entry:
            p.score = float(entry.get("score", NEW_SCORE))
