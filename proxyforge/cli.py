from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .checker import check, detect_real_ip
from .exporters import export_all, rank
from .fetchers import fetch_all
from .geo import enrich
from .models import Proxy, dedupe
from .scorer import attach_scores, update
from .speedtest import measure

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="proxyforge")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the full pipeline")
    run.add_argument("--out-dir", type=Path, default=Path("results"))
    run.add_argument("--data-file", type=Path, default=Path("data/history.json"))
    run.add_argument("--docs-dir", type=Path, default=Path("docs"))
    run.add_argument("--readme", type=Path, default=Path("README.md"))
    run.add_argument("--timeout", type=float, default=3.0)
    run.add_argument("--concurrency", type=int, default=150)
    run.add_argument("--max-speedtest", type=int, default=500)
    run.add_argument("--skip-fetch", action="store_true", help="reload candidates from results/all.json")
    run.add_argument("--skip-geo", action="store_true")
    run.add_argument("--skip-speedtest", action="store_true")
    return p


async def _run(args: argparse.Namespace) -> int:
    if args.skip_fetch:
        log.info("fetch skipped, loading %s", args.out_dir / "all.json")
        raw = [Proxy.from_dict(d) for d in json.loads((args.out_dir / "all.json").read_text())]
    else:
        raw = await fetch_all()
    candidates = dedupe(raw)
    log.info("pipeline: %d unique candidates", len(candidates))

    real_ip = await detect_real_ip(args.timeout)
    alive = await check(candidates, real_ip, timeout=args.timeout, concurrency=args.concurrency)
    if not alive:
        log.error("no proxies alive; aborting")
        return 1

    if not args.skip_geo:
        await enrich(alive)
    if not args.skip_speedtest:
        await measure(alive, max_n=args.max_speedtest)

    update(alive, candidates, args.data_file)
    attach_scores(alive, args.data_file)

    export_all(rank(alive), args.out_dir, args.docs_dir, args.readme)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - top-level guard for CI visibility
        log.exception("fatal: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
