#!/usr/bin/env python3
"""Walk through a settlement and listen.

The charts tell you a myth went from 0.31 to 0.04. This tells you whether a
player would have noticed. That is the actual question the readout design has
to answer, and no number answers it.

    python3 listen.py                                  # one valley over time
    python3 listen.py --scenario monoculture
    python3 listen.py --region fenmouth --ticks 0,60,120,220
    python3 listen.py --seed 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kith import engine, scenarios, voices  # noqa: E402
from kith.model import load_world  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="monoculture", choices=sorted(scenarios.ALL))
    ap.add_argument("--region", default="greenhollow")
    ap.add_argument("--ticks", default="0,40,90,150,220")
    ap.add_argument("--overheard", type=int, default=9)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    stops = sorted({int(t) for t in args.ticks.split(",")})
    world = load_world()
    if args.region not in world.regions:
        ap.error(f"unknown region {args.region}; have {list(world.regions)}")

    policy = scenarios.ALL[args.scenario]
    print()
    print("=" * 66)
    print(f"  {world.regions[args.region].name} under '{args.scenario}'")
    print("=" * 66)

    last = 0
    for stop in stops:
        if stop > last:
            engine.run(world, policy, stop - last)
            last = stop
        snap = voices.walk(world, args.region, args.overheard, seed=args.seed + stop)
        print()
        print(voices.render(snap, stop))

    print()
    shares = world.regions[args.region].shares()
    print("  (ledger, for comparison: " + ", ".join(
        f"{world.myth(m).name} {s:.2f}" for m, s in sorted(shares.items(), key=lambda kv: -kv[1]) if s > 0.001
    ) + ")")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
