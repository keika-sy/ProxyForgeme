from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

from .models import Proxy

log = logging.getLogger(__name__)

LINE_RE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})\s*$")

TEXT_SOURCES: list[dict] = [
    {"name": "thespeedx-http", "protocol": "http", "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"},
    {"name": "thespeedx-socks4", "protocol": "socks4", "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt"},
    {"name": "thespeedx-socks5", "protocol": "socks5", "url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt"},
    {"name": "monosans-http", "protocol": "http", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"},
    {"name": "monosans-socks4", "protocol": "socks4", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt"},
    {"name": "monosans-socks5", "protocol": "socks5", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"},
    {"name": "proxyscrape-http", "protocol": "http", "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all"},
    {"name": "proxyscrape-socks4", "protocol": "socks4", "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=3000&country=all"},
    {"name": "proxyscrape-socks5", "protocol": "socks5", "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=3000&country=all"},
]

GEONODE_URL = (
    "https://proxylist.geonode.com/api/proxy-list"
    "?limit=500&page={page}&sort_by=lastChecked&sort_type=desc&protocols[]={protocol}"
)
GEONODE_PAGES = 3


def parse_text(body: str, protocol: str) -> list[Proxy]:
    out: list[Proxy] = []
    for line in body.splitlines():
        m = LINE_RE.match(line)
        if m and 1 <= int(m.group(2)) <= 65535:
            out.append(Proxy(ip=m.group(1), port=int(m.group(2)), protocol=protocol))
    return out


def parse_geonode(payload: dict, protocol: str) -> list[Proxy]:
    out: list[Proxy] = []
    for row in payload.get("data", []):
        try:
            out.append(Proxy(ip=str(row["ip"]), port=int(row["port"]), protocol=protocol))
        except (KeyError, TypeError, ValueError):
            continue
    return out


async def _fetch_text(session: aiohttp.ClientSession, src: dict) -> list[Proxy]:
    async with session.get(src["url"], timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        return parse_text(await resp.text(), src["protocol"])


async def _fetch_geonode(session: aiohttp.ClientSession, protocol: str) -> list[Proxy]:
    out: list[Proxy] = []
    for page in range(1, GEONODE_PAGES + 1):
        url = GEONODE_URL.format(page=page, protocol=protocol)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                out.extend(parse_geonode(await resp.json(content_type=None), protocol))
        except Exception as exc:  # noqa: BLE001 - one page failing must not kill the run
            log.warning("geonode %s page %d failed: %s", protocol, page, exc)
            break
    return out


async def fetch_all(timeout: float = 30.0) -> list[Proxy]:
    """Fetch every source concurrently. Sources that fail are logged and skipped."""
    tasks: dict[str, asyncio.Task] = {}
    async with aiohttp.ClientSession() as session:
        for src in TEXT_SOURCES:
            tasks[src["name"]] = asyncio.create_task(_fetch_text(session, src))
        for protocol in ("http", "socks4", "socks5"):
            tasks[f"geonode-{protocol}"] = asyncio.create_task(_fetch_geonode(session, protocol))

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    collected: list[Proxy] = []
    ok_sources = 0
    for name, res in zip(tasks, results):
        if isinstance(res, BaseException):
            log.warning("source %s failed: %s", name, res)
        else:
            ok_sources += 1
            collected.extend(res)
            log.info("source %s: %d proxies", name, len(res))

    if ok_sources == 0:
        raise RuntimeError("all sources failed")
    log.info("fetch: %d raw proxies from %d sources", len(collected), ok_sources)
    return collected
