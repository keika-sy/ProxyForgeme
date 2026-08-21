from __future__ import annotations

import asyncio
import json
import logging
import re

import aiohttp
from aiohttp_socks import ProxyConnector

from .models import Proxy

log = logging.getLogger(__name__)

JUDGES = (
    "https://httpbin.org/get",
    "http://azenv.net/",
)

IPV4_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
PROXY_HEADER_RE = re.compile(r"via|forwarded|proxy", re.IGNORECASE)


async def detect_real_ip(timeout: float) -> str | None:
    """Find this machine's public IP by hitting a judge without any proxy."""
    async with aiohttp.ClientSession() as session:
        for url in JUDGES:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    body = await resp.text()
                m = IPV4_RE.search(_extract_origin(body))
                if m:
                    return m.group(1)
            except Exception:  # noqa: BLE001
                continue
    return None


def _extract_origin(body: str) -> str:
    try:
        data = json.loads(body)
        origin = str(data.get("origin", ""))
        headers = " ".join(f"{k}: {v}" for k, v in data.get("headers", {}).items())
        return f"{origin} {headers}"
    except (json.JSONDecodeError, AttributeError):
        return body


def classify_anonymity(body: str, real_ip: str | None) -> str:
    leaked = bool(real_ip and real_ip in body)
    has_proxy_headers = bool(PROXY_HEADER_RE.search(body))
    if leaked:
        return "transparent"
    if has_proxy_headers:
        return "anonymous"
    return "elite"


async def check_one(proxy: Proxy, real_ip: str | None, timeout: float, sem: asyncio.Semaphore) -> Proxy | None:
    async with sem:
        connector = ProxyConnector.from_url(proxy.proxy_url, rdns=proxy.protocol == "socks5")
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                for judge in JUDGES:
                    start = asyncio.get_running_loop().time()
                    try:
                        async with session.get(judge, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                            if resp.status != 200:
                                continue
                            body = await resp.text()
                        proxy.latency_ms = int((asyncio.get_running_loop().time() - start) * 1000)
                        proxy.anonymity = classify_anonymity(body, real_ip) if real_ip else ""
                        return proxy
                    except Exception:  # noqa: BLE001 - try next judge
                        continue
                return None
        except Exception:  # noqa: BLE001 - dead proxy
            return None


async def check(proxies: list[Proxy], real_ip: str | None, timeout: float = 3.0, concurrency: int = 150) -> list[Proxy]:
    sem = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(*(check_one(p, real_ip, timeout, sem) for p in proxies))
    alive = [p for p in results if p is not None]
    log.info("check: %d/%d alive", len(alive), len(proxies))
    return alive
