from __future__ import annotations

import asyncio
import logging
import time

import aiohttp
from aiohttp_socks import ProxyConnector

from .models import Proxy

log = logging.getLogger(__name__)

TEST_URLS = (
    "http://speedtest.tele2.net/10KB.zip",
    "http://example.com/",
)


async def _measure_one(proxy: Proxy, sem: asyncio.Semaphore, timeout: float) -> None:
    async with sem:
        connector = ProxyConnector.from_url(proxy.proxy_url, rdns=proxy.protocol == "socks5")
        for url in TEST_URLS:
            start = time.monotonic()
            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                        body = await resp.read()
                dt = max(time.monotonic() - start, 1e-6)
                proxy.latency_ms = int(dt * 1000)
                proxy.speed_kbps = round(len(body) / 1024 / dt, 1)
                return
            except Exception:  # noqa: BLE001 - fall through to next test url
                continue


async def measure(proxies: list[Proxy], max_n: int = 500, timeout: float = 8.0) -> None:
    """Fill latency_ms/speed_kbps in place for the top `max_n` fastest candidates."""
    candidates = sorted(proxies, key=lambda p: p.latency_ms if p.latency_ms is not None else 10**9)[:max_n]
    sem = asyncio.Semaphore(50)
    await asyncio.gather(*(_measure_one(p, sem, timeout) for p in candidates))
    done = sum(1 for p in candidates if p.speed_kbps is not None)
    log.info("speedtest: measured %d/%d", done, len(candidates))
