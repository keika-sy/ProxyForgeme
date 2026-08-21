# ProxyForge

Sistem otomatis pengumpulan, validasi, pengukuran kecepatan, dan publikasi proxy gratis. Terinspirasi dari proyek serupa, dengan fitur tambahan: speed test + ranking, uptime scoring antar-run, output multi-format, dan dashboard statistik.

Diperbarui otomatis oleh GitHub Actions setiap **2 jam**.

## Fitur

- **Multi-protokol:** HTTP, SOCKS4, SOCKS5
- **Validasi ketat:** timeout < 3 detik, deteksi anonymity (elite / anonymous / transparent)
- **Geo-location:** dikelompokkan per negara
- **Speed test:** latency + throughput untuk 500 kandidat tercepat
- **Uptime scoring:** skor 0–100 per proxy, decay harian, proxy mati >7 hari dibuang
- **Multi-format:** TXT, JSON, CSV, ranked top 100
- **Dashboard:** halaman statistik statis (GitHub Pages)

## Endpoint List (Raw)

| Kategori | Link Raw |
|---|---|
| All Proxies | `results/all.txt` |
| HTTP Only | `results/http.txt` |
| SOCKS4 Only | `results/socks4.txt` |
| SOCKS5 Only | `results/socks5.txt` |
| Per Negara | `results/countries/{CC}.txt` |
| Ranked Top 100 | `results/ranked/top100.txt` |
| JSON | `results/all.json` |
| CSV | `results/all.csv` |

Ganti `OWNER/REPO` dengan repo kamu untuk link raw lengkap, contoh:
`https://raw.githubusercontent.com/OWNER/REPO/main/results/all.txt`

## Cara Kerja

1. **Fetch:** ambil proxy dari banyak sumber publik (TheSpeedX, monosans, proxyscrape, geonode).
2. **Check:** validasi async — hanya proxy hidup yang lolos.
3. **Speedtest:** ukur latency + throughput.
4. **Score:** update riwayat uptime (`data/history.json` dipertahankan antar run).
5. **Export:** tulis semua format + dashboard + tabel README.

## Menjalankan Lokal

```bash
pip install -e ".[dev]"
pytest -q                 # test
python -m proxyforge run  # pipeline penuh
```

## Setup GitHub Pages (Dashboard)

Settings → Pages → Source: **Deploy from a branch** → Branch: `main`, folder `/docs`.

## Setup Repo Baru

1. Push repo ini ke GitHub.
2. Aktifkan Actions (default aktif).
3. (Opsional) Aktifkan Pages seperti di atas.

---

<!-- PROXYFORGE:START -->
**279** proxy aktif | HTTP: **118** | SOCKS4: **111** | SOCKS5: **50**

| Kategori | Link Raw |
|---|---|
| All | `results/all.txt` |
| HTTP | `results/http.txt` |
| SOCKS4 | `results/socks4.txt` |
| SOCKS5 | `results/socks5.txt` |
| Ranked Top 100 | `results/ranked/top100.txt` |
| JSON | `results/all.json` |
| CSV | `results/all.csv` |

Top negara: US (123), FR (13), RU (13), ID (12), CN (10), SG (10), HK (9), DE (8), NL (7), GB (6)

_Diupdate otomatis oleh GitHub Actions setiap 2 jam._
<!-- PROXYFORGE:END -->
