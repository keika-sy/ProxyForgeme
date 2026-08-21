# ProxyForge — Design

Tanggal: 2026-08-21
Status: Disetujui (desain verbal)

## Ringkasan

ProxyForge = sistem otomatis pengumpulan, validasi, pengukuran, dan publikasi proxy gratis. Terinspirasi repo `anutmagang/Free-HighQuality-Proxy-Socks`, dengan fitur tambahan: speed test + ranking, uptime scoring antar-run, output multi-format (txt/json/csv), dashboard GitHub Pages, README statistik auto-update. Berjalan di GitHub Actions tiap 2 jam.

## Keputusan Penting

- Pendekatan: modular Python package (bukan monolith) + dashboard Pages.
- Runtime: GitHub Actions (cron 2 jam + manual dispatch). Tidak ada server.
- Bahasa: Python 3.11+, async via `httpx` (+ `aiohttp`/`python-socks` untuk SOCKS4/5).
- State uptime dipertahankan lewat file `data/history.json` yang di-commit antar run.

## Arsitektur

Pipeline satu arah:

```
fetch → dedupe → check → geo → speedtest(top N) → score update → export → commit
```

### Modul (`proxyforge/`)

| Modul | Tanggung jawab | Interface |
|---|---|---|
| `fetchers.py` | Adapter sumber publik (TheSpeedX, monosans, proxyscrape, geonode API, dsb). Normalisasi ke objek `Proxy`, dedupe by `ip:port` | `fetch_all() -> list[Proxy]` |
| `checker.py` | Validasi async per proxy: request HTTP lewat proxy, timeout 3s hard cap, deteksi anonymity (elite/anonymous/transparent) dari header yang diterima judge endpoint | `check(proxies) -> list[Proxy]` |
| `geo.py` | Lookup negara via ip-api batch (100/req). Rate limit → kolom negara kosong, proxy tetap lolos | `enrich(proxies)` |
| `speedtest.py` | Latency (ms) + throughput download file kecil lewat proxy. Hanya untuk top N=500 kandidat, diurut dari latency validasi tercepat | `measure(proxies)` |
| `scorer.py` | Uptime scoring. Baca/tulis `data/history.json`: last_seen, success/fail count, skor decay | `update(proxies) -> None` |
| `exporters.py` | Tulis semua format output + tabel README + `docs/index.html` + `docs/data.js` | `export_all(proxies)` |
| `cli.py` | Orkestrator argparse: `run` (semua), flag `--skip-fetch`, `--skip-speedtest`, dst untuk debug | entrypoint |

Objek inti: dataclass `Proxy` — ip, port, protocol (http/socks4/socks5), country, anonymity, latency_ms, speed_kbps, score, last_seen.

## Output

```
results/
  all.txt                  # ip:port semua protokol
  http.txt / socks4.txt / socks5.txt
  countries/{CC}.txt       # per kode negara
  ranked/top100.txt        # urut skor desc, latency asc
  all.json                 # metadata lengkap
  all.csv
data/history.json          # state uptime
docs/index.html            # dashboard (statis)
docs/data.js               # data dashboard, regenerate tiap run
README.md                  # tabel statistik auto-update
```

Format JSON per proxy:

```json
{"ip":"1.2.3.4","port":8080,"protocol":"socks5","country":"ID",
 "anonymity":"elite","latency_ms":340,"speed_kbps":820,
 "score":87.5,"last_seen":"2026-08-21T10:00:00Z"}
```

## Scoring Uptime (0–100)

- Sukses check: +5. Gagal: −15.
- Decay ×0.95 per hari sejak update terakhir, diterapkan ke skor tersimpan sebelum penambahan/pengurangan baru.
- Proxy baru mulai 50.
- Proxy tidak terlihat >7 hari → dihapus dari history.
- Ranking `ranked/top100.txt` = skor desc, lalu latency asc.

## Dashboard

Satu `index.html` statis + `data.js` (di-regenerate tiap run). Chart.js dari CDN. Isi:
- Total proxy per protokol & per negara (bar chart)
- Top 20 tabel: ip, negara, protokol, latency, skor
- Histogram latency

Deploy: GitHub Pages dari folder `docs/` branch main.

## Error Handling

- Sumber gagal → log warning, lanjut sumber lain. Semua sumber gagal → exit non-zero.
- Check proxy timeout 3s hard cap; error ditelan jadi fail.
- ip-api rate limit → negara kosong, jangan gagalkan run.
- `history.json` corrupt/unparseable → salin ke `history.json.bak`, mulai state baru.
- Push bentrok (race antar run) → `git pull --rebase` sebelum push, retry 1x.
- Speedtest dibatasi top 500 agar total runtime <20 menit (batas aman Actions).

## Testing

- pytest unit: parser tiap sumber (fixture HTML/API offline), rumus skor (decay, plus/minus, prune), format exporter (snapshot txt/json/csv).
- Smoke test CLI end-to-end dengan fixture lokal, tanpa network.
- CI dua job: job `test` (pytest) → job `update` (pipeline + commit + deploy), `needs: test`.

## Workflow GitHub Actions (`.github/workflows/update.yml`)

- Trigger: cron `0 */2 * * *` + `workflow_dispatch`.
- `concurrency: proxyforge-update` (cancel in-progress) anti tabrakan run.
- Steps: checkout → setup Python → pip install → pytest → run CLI → commit `results/ data/ docs/ README.md` → push (dengan rebase retry).
- Pages: deploy dari `docs/`.

## Di Luar Cakupan (Fase 2+)

- Notifikasi Telegram.
- API dinamis / backend.
- Akun/autentikasi apa pun.
