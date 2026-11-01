#!/usr/bin/env python3
"""Does any of this survive a world bigger than one valley?

Everything so far was validated on three regions, ten myths and three
maintainers - which means almost every region had a Messenger standing in it
almost all the time. The release model in DESIGN.md ships region after region
into one growing world, so the two questions that matter are:

  COVERAGE   how many Messengers does a world need per region before the
             homeostasis stops holding? Finding 5 already showed a maintainer
             cannot help a region they are not standing in.

  DILUTION   Bleed triggers on a dominant myth's SHARE. In a region holding
             four stories the average share is 0.25 and the threshold is easy
             to reach. In one holding thirty it is 0.033, and no myth may ever
             get near the threshold - which would mean Bleed quietly stops
             existing as the world gets richer.

Builds synthetic worlds in memory rather than reading data/, so region count,
myth count and maintainer count can all be varied.

    python3 scale.py                 # the full grid
    python3 scale.py --ticks 300
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kith import engine, scenarios  # noqa: E402
from kith.messengers import Messenger  # noqa: E402
from kith.model import Myth, Region, World, load_world  # noqa: E402

DOMAINS = ["fire", "water", "hunger", "stone", "growth", "dusk"]


def make_world(n_regions: int, myths_per_region: int, n_maintainers: int, tuning: dict) -> World:
    """A ring of regions, each with its own native myths of varying rootedness."""
    regions: dict[str, Region] = {}
    myths: dict[str, Myth] = {}

    for i in range(n_regions):
        rid = f"r{i}"
        nxt, prv = f"r{(i + 1) % n_regions}", f"r{(i - 1) % n_regions}"
        neighbors = [nxt] if n_regions == 2 else [nxt, prv]
        regions[rid] = Region(
            id=rid,
            name=f"Region {i}",
            cosmology="humors" if i % 2 == 0 else "houses",
            # Vary the regions. A uniform ring is trivially stable and the
            # coverage grid came back all-ok even with zero Messengers, which
            # told us nothing. Small, low-transmission places are fragile and
            # are what a sparse Messenger circuit actually fails to protect.
            population=float(400 + (i * 937) % 3600),
            transmission=0.45 + ((i * 7) % 11) * 0.05,
            neighbors=neighbors,
            population0=float(400 + (i * 937) % 3600),
            weights={},
        )

    for i in range(n_regions):
        rid = f"r{i}"
        for j in range(myths_per_region):
            mid = f"m{i}_{j}"
            # one pillar, one strong, the rest increasingly shallow
            root = 1.0 if j == 0 else max(0.08, 1.0 - (j * (0.9 / max(1, myths_per_region - 1))))
            myths[mid] = Myth(
                id=mid, name=f"Myth {i}.{j}", domain=DOMAINS[(i + j) % len(DOMAINS)],
                home=rid, rootedness=root,
            )
            regions[rid].weights[mid] = 0.30 * root + 0.02

    messengers: dict[str, Messenger] = {}
    for k in range(n_maintainers):
        # spread their starting posts evenly around the ring
        home = f"r{(k * n_regions) // max(1, n_maintainers)}"
        local = [m for m in myths.values() if m.home == home][:3]
        messengers[f"msg{k}"] = Messenger(
            id=f"msg{k}", name=f"Messenger {k}", home=home, behavior="maintainer",
            bound=[m.id for m in local], travel_period=7 + (k % 5),
        )

    return World(
        myths=myths, regions=regions,
        domain_terrain={d: d for d in DOMAINS},
        tuning=dict(tuning), messengers=messengers,
    )


def measure(n_regions: int, myths_per_region: int, n_maintainers: int, tuning: dict, ticks: int) -> dict:
    w = make_world(n_regions, myths_per_region, n_maintainers, tuning)
    total = len(w.myths)
    h = engine.run(w, scenarios.absent, ticks)
    peak = max(max(f.bleed.values()) for f in h.frames)
    alive = len(w.living_myths())
    stable = (
        not any(r.sterile for r in w.regions.values())
        and alive >= total * 0.6
        and peak < 0.20
    )

    # can a determined player still wreck one place?
    w2 = make_world(n_regions, myths_per_region, n_maintainers, tuning)
    target = "r0"
    pick = next(m for m in w2.myths if w2.myths[m].home == target)

    def spam(world):
        if not world.regions[target].sterile:
            engine.tell(world, target, pick)

    h2 = engine.run(w2, spam, ticks)
    peak2 = max(max(f.bleed.values()) for f in h2.frames)
    can_bleed = peak2 > 0.70

    return {
        "stable": stable, "alive": alive, "total": total, "peak": peak,
        "can_bleed": can_bleed, "peak_mono": peak2,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=220)
    args = ap.parse_args()
    tuning = load_world().tuning

    print()
    print("=" * 78)
    print("COVERAGE - how many Messengers does a world need to hold together?")
    print("=" * 78)
    print("  'absent' scenario, 4 myths per region. ok = world stable unattended.")
    print()
    region_counts = [3, 5, 8, 12]
    header = "  regions |" + "".join(f"{m:>6}" for m in range(0, 13, 2)) + "   maintainers"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for n in region_counts:
        row = f"  {n:>7} |"
        for k in range(0, 13, 2):
            r = measure(n, 4, k, tuning, args.ticks)
            row += f"{'  ok  ' if r['stable'] else '  --  '}"
        print(row)
    print()
    print("  Read down a column: adding regions without adding Messengers.")
    print("  Read across a row: how many a world of that size actually needs.")

    print()
    print("=" * 78)
    print("DILUTION - does Bleed survive a region that knows many stories?")
    print("=" * 78)
    print("  One player spamming one myth in one region, 5 regions, 3 maintainers.")
    print()
    print(f"  {'myths/region':>13}{'peak bleed':>13}{'craters?':>11}{'avg share':>12}")
    print("  " + "-" * 49)
    for mpr in (3, 4, 6, 10, 16, 25):
        r = measure(5, mpr, 3, tuning, args.ticks)
        print(
            f"  {mpr:>13}{r['peak_mono']:>13.2f}"
            f"{('  yes' if r['can_bleed'] else '   no'):>11}{1.0 / mpr:>12.3f}"
        )
    print()
    print(f"  bleed_threshold is {tuning['bleed_threshold']:.3f}. A myth has to hold that much")
    print("  of a region's attention to start transmuting the land, so the more")
    print("  stories a place knows, the further one has to climb to get there.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
