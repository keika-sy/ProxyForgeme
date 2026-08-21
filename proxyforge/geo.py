from __future__ import annotations

import asyncio
import logging

import aiohttp

from .models import Proxy

log = logging.getLogger(__name__)

BATCH_URL = "http://ip-api.com/batch?fields=status,countryCode,query"
BATCH_SIZE = 100


async def _lookup_batch(session: aiohttp.ClientSession, ips: list[str]) -> dict[str, str]:
    try:
        async with session.post(BATCH_URL, json=ips, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            rows = await resp.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 - rate limit / network: leave countries empty
        log.warning("geo batch failed (%d ips): %s", len(ips), exc)
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("status") == "success":
            out[str(row["query"])] = str(row.get("countryCode", ""))
    return out


async def enrich(proxies: list[Proxy]) -> None:
    """Fill proxy.country in place. Failures leave it empty."""
    ips = list({p.ip for p in proxies})
    mapping: dict[str, str] = {}
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(ips), BATCH_SIZE):
            chunk = ips[i : i + BATCH_SIZE]
            mapping.update(await _lookup_batch(session, chunk))
            await asyncio.sleep(4.5)  # free tier: ~15 req/min
    for p in proxies:
        p.country = mapping.get(p.ip, "")
    known = sum(1 for p in proxies if p.country)
    log.info("geo: resolved %d/%d unique ips", known, len(ips))
