from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

VALID_PROTOCOLS = ("http", "socks4", "socks5")
ANONYMITY_LEVELS = ("transparent", "anonymous", "elite")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class Proxy:
    ip: str
    port: int
    protocol: str
    country: str = ""
    anonymity: str = ""
    latency_ms: int | None = None
    speed_kbps: float | None = None
    score: float = 50.0
    last_seen: str = field(default_factory=lambda: utcnow().isoformat())

    def __post_init__(self) -> None:
        if self.protocol not in VALID_PROTOCOLS:
            raise ValueError(f"invalid protocol: {self.protocol!r}")

    @property
    def key(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def proxy_url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Proxy":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def dedupe(proxies: list[Proxy]) -> list[Proxy]:
    seen: set[str] = set()
    out: list[Proxy] = []
    for p in proxies:
        if p.key in seen:
            continue
        seen.add(p.key)
        out.append(p)
    return out


def dumps_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
