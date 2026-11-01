#!/usr/bin/env python3
"""Run the Kith belief scenarios, print a report, write plots.

    python3 run.py                  # all scenarios, report + plots
    python3 run.py --no-plot        # report only
    python3 run.py --ticks 400      # override run length
    python3 run.py monoculture      # one scenario, with its event log

The report answers Gate 1 from DESIGN.md:
  - do the policies produce visibly different worlds?
  - how long is the middle between bleed onset and the point of no return?
  - does Bleed cross a border?
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kith import engine, scenarios  # noqa: E402
from kith.model import load_world  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"


def summarize(name: str, world, history) -> dict:
    onsets = {e.region: e.tick for e in history.events if e.kind == "bleed_onset"}
    no_return = {e.region: e.tick for e in history.events if e.kind == "no_return"}
    carried = {(e.region, e.detail.split(" arrives")[0]) for e in history.events if e.kind == "carried"}

    middles = [no_return[r] - onsets[r] for r in no_return if r in onsets]

    final = history.frames[-1]
    return {
        "name": name,
        "living_myths": final.living,
        "extinct": sorted(m for m in world.extinct_myths()),
        "population": sum(final.population.values()),
        "sterile": [r.name for r in world.regions.values() if r.sterile],
        "doomed": [r.name for r in world.regions.values() if r.doomed],
        "peak_bleed": {r: max(f.bleed[r] for f in history.frames) for r in final.bleed},
        "first_onset": min(onsets.values()) if onsets else None,
        "middle": min(middles) if middles else None,
        "crossed_border": len(carried),
        "thin": [
            r.name for r in world.regions.values()
            if not r.sterile and r.vitality < world.tuning["vitality_thin"]
        ],
    }


def print_report(rows: list[dict], start_pop: float) -> None:
    print()
    print("=" * 78)
    print("GATE 1 - does the belief ledger have dynamics worth building on?")
    print("=" * 78)
    head = f"{'scenario':<14}{'myths':>7}{'pop':>9}{'onset':>7}{'middle':>8}{'sterile':>9}{'xborder':>9}"
    print(head)
    print("-" * 78)
    for r in rows:
        print(
            f"{r['name']:<14}"
            f"{r['living_myths']:>3}/6  "
            f"{r['population']:>8,.0f}"
            f"{(r['first_onset'] if r['first_onset'] is not None else '-'):>7}"
            f"{(r['middle'] if r['middle'] is not None else '-'):>8}"
            f"{len(r['sterile']):>9}"
            f"{r['crossed_border']:>9}"
        )
    print("-" * 78)
    print(f"population at t=0: {start_pop:,.0f}   |   onset/middle in ticks (~1 week each)")
    print()
    print("READ IT LIKE THIS")
    print("  middle   ticks from the land visibly turning to past saving. This is the")
    print("           telegraphing window. Under ~15 and the mechanic is a cliff, not")
    print("           a garden - the player cannot react in time and it reads as a")
    print("           betrayal. DESIGN.md calls for a long, loud, visible middle.")
    print("  myths    survivors out of 6. If every scenario lands on the same number,")
    print("           player choice is not moving the ecology and Gate 1 fails.")
    print("  xborder  times a myth rode refugees into a neighbouring region.")
    print()
    for r in rows:
        bits = []
        if r["extinct"]:
            bits.append(f"extinct: {', '.join(r['extinct'])}")
        if r["sterile"]:
            bits.append(f"sterile: {', '.join(r['sterile'])}")
        if r["thin"]:
            bits.append(f"thin: {', '.join(r['thin'])}")
        peak = ", ".join(f"{k} {v:.2f}" for k, v in r["peak_bleed"].items())
        bits.append(f"peak bleed: {peak}")
        print(f"  {r['name']:<13} " + " | ".join(bits))
    print()


def plot(name: str, world, history) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUT.mkdir(exist_ok=True)
    regions = list(world.regions)
    fig, axes = plt.subplots(3, len(regions), figsize=(5.2 * len(regions), 10), sharex=True)
    if len(regions) == 1:
        axes = axes.reshape(3, 1)

    ticks = [f.tick for f in history.frames]
    t = world.tuning

    for col, region_id in enumerate(regions):
        region = world.regions[region_id]

        ax = axes[0][col]
        for myth_id, myth in world.myths.items():
            series = [f.shares[region_id].get(myth_id, 0.0) for f in history.frames]
            if max(series) > 0.01:
                ax.plot(ticks, series, label=myth.name, linewidth=1.4)
        ax.axhline(t["bleed_threshold"], color="0.4", linestyle="--", linewidth=1)
        ax.set_title(f"{region.name} - belief share")
        ax.set_ylim(0, 1)
        ax.legend(fontsize=7, loc="upper left")

        ax = axes[1][col]
        ax.plot(ticks, [f.bleed[region_id] for f in history.frames], color="crimson", linewidth=1.6)
        ax.axhline(t["point_of_no_return"], color="0.4", linestyle="--", linewidth=1)
        ax.axhline(t["population_bleed_onset"], color="0.7", linestyle=":", linewidth=1)
        ax.set_title("bleed")
        ax.set_ylim(0, 1)

        ax = axes[2][col]
        ax.plot(ticks, [f.population[region_id] for f in history.frames], color="seagreen", linewidth=1.6)
        ax.set_title("population")
        ax.set_xlabel("tick")
        ax.set_ylim(bottom=0)

    fig.suptitle(f"Kith belief simulation - {name}", fontsize=13)
    fig.tight_layout()
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", help="run one scenario and show its events")
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    names = [args.scenario] if args.scenario else list(scenarios.ALL)
    unknown = [n for n in names if n not in scenarios.ALL]
    if unknown:
        parser.error(f"unknown scenario(s) {unknown}; choose from {list(scenarios.ALL)}")

    rows = []
    start_pop = sum(r.population for r in load_world().regions.values())

    for name in names:
        world = load_world()
        history = engine.run(world, scenarios.ALL[name], args.ticks)
        rows.append(summarize(name, world, history))
        if not args.no_plot:
            print(f"wrote {plot(name, world, history).relative_to(Path.cwd()) if str(OUT).startswith(str(Path.cwd())) else plot(name, world, history)}")

        if args.scenario:
            print(f"\nevents - {name}")
            print("-" * 78)
            seen = set()
            for e in history.events:
                key = (e.kind, e.region, e.detail)
                if key in seen:
                    continue
                seen.add(key)
                print(f"  t{e.tick:>4}  {e.kind:<14} {e.detail}")

    print_report(rows, start_pop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
