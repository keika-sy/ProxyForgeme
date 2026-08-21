import json

from proxyforge import cli


def test_run_pipeline_offline(tmp_path, monkeypatch):
    async def fake_fetch_all(timeout=30.0):
        from proxyforge.models import Proxy

        return [
            Proxy(ip="1.1.1.1", port=80, protocol="http"),
            Proxy(ip="1.1.1.1", port=80, protocol="socks5"),  # dupe
            Proxy(ip="2.2.2.2", port=1080, protocol="socks5"),
        ]

    async def fake_check(proxies, real_ip, timeout=3.0, concurrency=150):
        for p in proxies:
            p.anonymity = "elite"
            p.latency_ms = 100
        return proxies[:1]  # the rest die

    async def fake_enrich(proxies):
        for p in proxies:
            p.country = "ID"

    async def fake_measure(proxies, max_n=500, timeout=8.0):
        for p in proxies:
            p.speed_kbps = 500.0

    monkeypatch.setattr(cli, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(cli, "check", fake_check)
    monkeypatch.setattr(cli, "detect_real_ip", _async_return("3.3.3.3"))
    monkeypatch.setattr(cli, "enrich", fake_enrich)
    monkeypatch.setattr(cli, "measure", fake_measure)

    rc = cli.main(
        [
            "run",
            "--out-dir",
            str(tmp_path / "results"),
            "--data-file",
            str(tmp_path / "data" / "history.json"),
            "--docs-dir",
            str(tmp_path / "docs"),
            "--readme",
            str(tmp_path / "README.md"),
        ]
    )
    assert rc == 0
    out = tmp_path / "results"
    assert (out / "all.txt").read_text().splitlines() == ["1.1.1.1:80"]
    assert (out / "socks5.txt").exists()
    data = json.loads((out / "all.json").read_text())
    assert data[0]["country"] == "ID"
    assert data[0]["score"] == 55.0  # new proxy 50 + success bonus 5
    assert (tmp_path / "docs" / "index.html").exists()
    assert (tmp_path / "data" / "history.json").exists()


def _async_return(value):
    import asyncio

    async def fn(*args, **kwargs):
        return value

    return fn
