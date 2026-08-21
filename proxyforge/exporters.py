from __future__ import annotations

import csv
import json
import logging
from collections import Counter
from pathlib import Path

from .models import Proxy, dumps_json

log = logging.getLogger(__name__)

README_START = "<!-- PROXYFORGE:START -->"
README_END = "<!-- PROXYFORGE:END -->"
RANKED_SIZE = 100

LATENCY_BINS = (("0-500", 500), ("500-1000", 1000), ("1000-2000", 2000), ("2000+", None))


def _write_lines(path: Path, proxies: list[Proxy]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(p.key for p in proxies) + ("\n" if proxies else ""))


def write_txt(proxies: list[Proxy], out_dir: Path) -> None:
    _write_lines(out_dir / "all.txt", proxies)
    for protocol in ("http", "socks4", "socks5"):
        _write_lines(out_dir / f"{protocol}.txt", [p for p in proxies if p.protocol == protocol])
    by_country = sorted({p.country for p in proxies if p.country})
    for cc in by_country:
        _write_lines(out_dir / "countries" / f"{cc}.txt", [p for p in proxies if p.country == cc])


def write_ranked(proxies: list[Proxy], out_dir: Path, size: int = RANKED_SIZE) -> None:
    ranked = rank(proxies)[:size]
    _write_lines(out_dir / "ranked" / "top100.txt", ranked)


def rank(proxies: list[Proxy]) -> list[Proxy]:
    return sorted(proxies, key=lambda p: (-p.score, p.latency_ms if p.latency_ms is not None else 10**9))


def write_json_csv(proxies: list[Proxy], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "all.json").write_text(dumps_json([p.to_dict() for p in proxies]))
    with (out_dir / "all.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(Proxy.__dataclass_fields__))
        writer.writeheader()
        for p in proxies:
            writer.writerow(p.to_dict())


def build_dashboard_data(proxies: list[Proxy]) -> dict:
    protocols = Counter(p.protocol for p in proxies)
    countries = Counter(p.country for p in proxies if p.country)
    latencies = [p.latency_ms for p in proxies if p.latency_ms is not None]
    hist_counts = []
    low_bound = 0
    for _, high in LATENCY_BINS:
        hist_counts.append(sum(1 for ms in latencies if ms > low_bound and (high is None or ms <= high)))
        low_bound = high if high else low_bound
    return {
        "generated": max((p.last_seen for p in proxies), default=""),
        "totals": {"all": len(proxies), **{k: protocols.get(k, 0) for k in ("http", "socks4", "socks5")}},
        "countries": [{"cc": cc, "count": n} for cc, n in countries.most_common(15)],
        "top20": [p.to_dict() for p in rank(proxies)[:20]],
        "latency_hist": {"bins": [b for b, _ in LATENCY_BINS], "counts": hist_counts},
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0d1117">
<title>ProxyForge Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 2rem; max-width: 1100px; margin-inline: auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; } .muted { color: #8b949e; font-size: .85rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; margin: 1.25rem 0 1.5rem; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: .9rem 1.1rem; }
.card b { display: block; font-size: 1.7rem; line-height: 1.2; margin-top: .15rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }
.panel { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 1rem; min-width: 0; }
.panel h2 { font-size: 1.05rem; margin: 0 0 .75rem; }
.chart-box { position: relative; height: 240px; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 0 -.25rem; padding: 0 .25rem; }
table { width: 100%; border-collapse: collapse; font-size: .88rem; }
th, td { text-align: left; padding: .45rem .55rem; border-bottom: 1px solid #21262d; white-space: nowrap; }
th { color: #8b949e; font-weight: 600; position: sticky; top: 0; background: #161b22; }
td.addr { font-family: ui-monospace, monospace; font-size: .82rem; }
.badge { display: inline-block; padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; text-transform: uppercase; letter-spacing: .03em; }
.badge.elite { background: #1a3520; color: #56d364; } .badge.anonymous { background: #27304a; color: #7ee787; } .badge.transparent { background: #4a2b11; color: #f0883e; }
footer { margin-top: 2rem; text-align: center; }
@media (max-width: 640px) {
  body { padding: 1rem; }
  h1 { font-size: 1.25rem; }
  .cards { grid-template-columns: repeat(2, 1fr); gap: .6rem; }
  .card { padding: .7rem .9rem; } .card b { font-size: 1.4rem; }
  .grid { grid-template-columns: 1fr; gap: 1rem; }
  .chart-box { height: 200px; }
  th, td { padding: .4rem .45rem; font-size: .82rem; }
}
</style>
</head>
<body>
<h1>ProxyForge</h1>
<p class="muted">Last updated: <span id="generated"></span></p>
<div class="cards" id="cards"></div>
<div class="grid">
  <div class="panel"><h2>Protocols</h2><div class="chart-box"><canvas id="protocolChart"></canvas></div></div>
  <div class="panel"><h2>Countries</h2><div class="chart-box"><canvas id="countryChart"></canvas></div></div>
  <div class="panel"><h2>Latency (ms)</h2><div class="chart-box"><canvas id="latencyChart"></canvas></div></div>
</div>
<div class="panel">
  <h2>Top 20</h2>
  <div class="table-wrap">
  <table><thead><tr><th>Address</th><th>Protocol</th><th>Country</th><th>Anonymity</th><th>Latency</th><th>Score</th></tr></thead>
  <tbody id="top"></tbody></table>
  </div>
</div>
<footer class="muted">Auto-updated by GitHub Actions every 2 hours</footer>
<script src="data.js"></script>
<script>
const d = window.PROXYFORGE_DATA;
document.getElementById('generated').textContent = d.generated || 'n/a';
const cards = [['All', d.totals.all], ['HTTP', d.totals.http], ['SOCKS4', d.totals.socks4], ['SOCKS5', d.totals.socks5]];
document.getElementById('cards').innerHTML =
  cards.map(([k, v]) => `<div class="card">${k}<b>${v}</b></div>`).join('');
const gridColor = '#21262d';
const baseOpts = { responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { x: { grid: { color: gridColor }, ticks: { maxRotation: 0, autoSkipPadding: 8 } }, y: { grid: { color: gridColor }, beginAtZero: true } } };
new Chart(protocolChart, { type: 'bar', data: { labels: ['HTTP', 'SOCKS4', 'SOCKS5'],
  datasets: [{ data: [d.totals.http, d.totals.socks4, d.totals.socks5], backgroundColor: '#58a6ff', borderRadius: 4 }] }, options: baseOpts });
new Chart(countryChart, { type: 'bar', data: { labels: d.countries.map(c => c.cc),
  datasets: [{ data: d.countries.map(c => c.count), backgroundColor: '#3fb950', borderRadius: 4 }] },
  options: { ...baseOpts, scales: { ...baseOpts.scales, x: { ...baseOpts.scales.x, ticks: { maxRotation: 0, autoSkip: true } } } } });
new Chart(latencyChart, { type: 'bar', data: { labels: d.latency_hist.bins,
  datasets: [{ data: d.latency_hist.counts, backgroundColor: '#d29922', borderRadius: 4 }] }, options: baseOpts });
document.getElementById('top').innerHTML = d.top20.map(p =>
  `<tr><td class="addr">${p.ip}:${p.port}</td><td>${p.protocol}</td><td>${p.country || '?'}</td><td><span class="badge ${p.anonymity || ''}">${p.anonymity || '?'}</span></td><td>${p.latency_ms ?? '?'} ms</td><td>${p.score}</td></tr>`).join('');
</script>
</body>
</html>
"""


def write_dashboard(proxies: list[Proxy], docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(DASHBOARD_HTML)
    (docs_dir / "data.js").write_text(
        "window.PROXYFORGE_DATA = " + json.dumps(build_dashboard_data(proxies), ensure_ascii=False) + ";"
    )


def readme_section(proxies: list[Proxy]) -> str:
    protocols = Counter(p.protocol for p in proxies)
    countries = Counter(p.country for p in proxies if p.country)
    top_cc = ", ".join(f"{cc} ({n})" for cc, n in countries.most_common(10)) or "-"
    lines = [
        README_START,
        f"**{len(proxies)}** proxy aktif | "
        f"HTTP: **{protocols.get('http', 0)}** | SOCKS4: **{protocols.get('socks4', 0)}** | SOCKS5: **{protocols.get('socks5', 0)}**",
        "",
        "| Kategori | Link Raw |",
        "|---|---|",
        "| All | `results/all.txt` |",
        "| HTTP | `results/http.txt` |",
        "| SOCKS4 | `results/socks4.txt` |",
        "| SOCKS5 | `results/socks5.txt` |",
        "| Ranked Top 100 | `results/ranked/top100.txt` |",
        "| JSON | `results/all.json` |",
        "| CSV | `results/all.csv` |",
        "",
        f"Top negara: {top_cc}",
        "",
        "_Diupdate otomatis oleh GitHub Actions setiap 2 jam._",
        README_END,
    ]
    return "\n".join(lines)


def write_readme(proxies: list[Proxy], readme_path: Path) -> None:
    section = readme_section(proxies)
    if readme_path.exists():
        text = readme_path.read_text()
        if README_START in text and README_END in text:
            head, rest = text.split(README_START, 1)
            _, tail = rest.split(README_END, 1)
            text = head + section + tail
        else:
            text = text.rstrip() + "\n\n" + section + "\n"
    else:
        text = "# ProxyForge\n\n" + section + "\n"
    readme_path.write_text(text)


def export_all(proxies: list[Proxy], out_dir: Path, docs_dir: Path, readme_path: Path) -> None:
    write_txt(proxies, out_dir)
    write_ranked(proxies, out_dir)
    write_json_csv(proxies, out_dir)
    write_dashboard(proxies, docs_dir)
    write_readme(proxies, readme_path)
    log.info("export: %d proxies -> %s, %s, %s", len(proxies), out_dir, docs_dir, readme_path)
