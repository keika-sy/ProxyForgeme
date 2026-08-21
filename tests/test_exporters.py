import json

from proxyforge.exporters import (
    build_dashboard_data,
    export_all,
    rank,
    readme_section,
    write_json_csv,
    write_ranked,
    write_txt,
)
from proxyforge.models import Proxy


def _proxy(ip, port=80, protocol="http", country="ID", latency=None, score=50.0):
    return Proxy(
        ip=ip,
        port=port,
        protocol=protocol,
        country=country,
        anonymity="elite",
        latency_ms=latency,
        speed_kbps=100.0,
        score=score,
    )


def test_rank_ordering():
    proxies = [_proxy("1.1.1.1", latency=500, score=60), _proxy("2.2.2.2", latency=100, score=60), _proxy("3.3.3.3", latency=50, score=40)]
    assert [p.ip for p in rank(proxies)] == ["2.2.2.2", "1.1.1.1", "3.3.3.3"]
    no_latency = _proxy("4.4.4.4", score=99)
    assert rank(proxies + [no_latency])[0].ip == "4.4.4.4"


def test_write_txt_files(tmp_path):
    proxies = [_proxy("1.1.1.1"), _proxy("2.2.2.2", protocol="socks5", country="US")]
    write_txt(proxies, tmp_path)
    assert (tmp_path / "all.txt").read_text().splitlines() == ["1.1.1.1:80", "2.2.2.2:80"]
    assert (tmp_path / "socks5.txt").read_text().splitlines() == ["2.2.2.2:80"]
    assert (tmp_path / "countries" / "ID.txt").exists()
    assert (tmp_path / "countries" / "US.txt").exists()


def test_write_ranked_top100(tmp_path):
    proxies = [_proxy(f"10.0.0.{i}", score=float(i)) for i in range(150)]
    write_ranked(proxies, tmp_path)
    lines = (tmp_path / "ranked" / "top100.txt").read_text().splitlines()
    assert len(lines) == 100
    assert lines[0] == "10.0.0.149:80"


def test_write_json_csv(tmp_path):
    proxies = [_proxy("1.1.1.1")]
    write_json_csv(proxies, tmp_path)
    data = json.loads((tmp_path / "all.json").read_text())
    assert data[0]["ip"] == "1.1.1.1"
    csv_text = (tmp_path / "all.csv").read_text()
    assert "ip,port,protocol" in csv_text


def test_readme_section_replaces_markers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\n<!-- PROXYFORGE:START -->old<!-- PROXYFORGE:END -->\n\nfooter\n")
    export_all([_proxy("1.1.1.1")], tmp_path / "results", tmp_path / "docs", readme)
    text = readme.read_text()
    assert text.count("<!-- PROXYFORGE:START -->") == 1
    assert "old" not in text
    assert "# Title" in text and "footer" in text
    assert (tmp_path / "docs" / "index.html").exists()
    js = (tmp_path / "docs" / "data.js").read_text()
    assert js.startswith("window.PROXYFORGE_DATA = ")
    assert json.loads(js[len("window.PROXYFORGE_DATA = ") : -1])["totals"]["all"] == 1


def test_dashboard_data_shape():
    proxies = [
        _proxy("1.1.1.1", latency=300),
        _proxy("2.2.2.2", latency=800, protocol="socks5"),
        _proxy("3.3.3.3", latency=1500, country=""),
    ]
    d = build_dashboard_data(proxies)
    assert d["totals"] == {"all": 3, "http": 2, "socks4": 0, "socks5": 1}
    assert d["latency_hist"]["counts"] == [1, 1, 1, 0]
    assert len(d["top20"]) == 3
