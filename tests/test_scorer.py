import json

from proxyforge import scorer
from proxyforge.models import Proxy, utcnow


def _entry(score=50.0, days_ago=0.0, success=1, fail=0):
    from datetime import timedelta

    return {
        "score": score,
        "last_seen": (utcnow() - timedelta(days=days_ago)).isoformat(),
        "success": success,
        "fail": fail,
        "protocol": "http",
    }


def test_apply_score_success_no_decay():
    entry = _entry(score=50.0)
    assert scorer.apply_score(entry, success=True) == 55.0


def test_apply_score_fail_clamped_zero():
    entry = _entry(score=5.0)
    assert scorer.apply_score(entry, success=False) == 0.0


def test_apply_score_success_clamped_hundred():
    entry = _entry(score=99.0)
    assert scorer.apply_score(entry, success=True) == 100.0


def test_apply_score_daily_decay():
    entry = _entry(score=100.0, days_ago=1.0)
    expected = round(100.0 * 0.95 + 5.0, 1)
    assert scorer.apply_score(entry, success=True) == expected


def test_update_creates_and_prunes(tmp_path):
    path = tmp_path / "history.json"
    old_key_proxy = Proxy(ip="9.9.9.9", port=80, protocol="http")
    stale = {"version": 1, "proxies": {"9.9.9.9:80": _entry(days_ago=8.0)}}
    path.write_text(json.dumps(stale))

    alive = [Proxy(ip="1.1.1.1", port=80, protocol="http")]
    dead = [old_key_proxy, Proxy(ip="2.2.2.2", port=80, protocol="http")]
    scorer.update(alive, alive + dead, path)

    history = json.loads(path.read_text())
    assert "9.9.9.9:80" not in history["proxies"]  # pruned: unseen >7 days
    assert history["proxies"]["1.1.1.1:80"]["success"] == 1
    assert history["proxies"]["2.2.2.2:80"]["fail"] == 1


def test_load_corrupt_backs_up(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{not json")
    state = scorer.load(path)
    assert state["proxies"] == {}
    assert path.with_suffix(".json.bak").exists()


def test_attach_scores(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"version": 1, "proxies": {"1.1.1.1:80": _entry(score=77.0)}}))
    p = Proxy(ip="1.1.1.1", port=80, protocol="http")
    scorer.attach_scores([p], path)
    assert p.score == 77.0
