#!/usr/bin/env python3
"""Parameter sweep: how fragile is the Bleed mechanic?

The scenario report tells you the system behaves well at one point in
parameter space - the point I tuned it to. That is not the same as the system
being sound. If the long telegraphing middle only exists in a knife-edge
window, Godot will expose that painfully and expensively.

This samples the main constants at random and scores each draw against three
requirements taken from DESIGN.md:

  STABLE     doing nothing leaves the world intact. No region sterile, most
             myths alive, bleed stays near zero. A world that kills itself
             unattended is wrong, and it punishes players for existing.
  PUNISHING  spamming one story in one place wrecks that place. If bad play
             costs nothing, Bleed is decoration.
  REACTABLE  at least MIN_MIDDLE ticks between the land visibly turning and
             the point of no return. Under that it is a cliff, not a garden,
             and it reads to the player as a betrayal.

A draw that satisfies all three is viable. The output is what fraction of the
sampled space is viable, and which value ranges the viable draws cluster in.

    python3 sweep.py             # 400 draws
    python3 sweep.py -n 1500     # more
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kith import engine, scenarios  # noqa: E402
from kith.model import load_world  # noqa: E402

MIN_MIDDLE = 15

# name -> (low, high). The constants that actually shape the Bleed dynamic.
RANGES = {
    "bleed_threshold": (0.40, 0.75),
    "bleed_rate": (0.03, 0.18),
    "bleed_feedback": (0.000, 0.030),
    "bleed_recovery": (0.005, 0.050),
    "decay_flat": (0.002, 0.010),
    "native_telling_per_myth": (0.0030, 0.0130),
    "native_fashion_damping": (0.0, 2.0),
    "telling_gain": (0.015, 0.060),
    "maintainer_vigor": (0.0, 1.0),
    "contest_swing": (0.01, 0.20),
    "contest_saturation_damping": (0.0, 2.0),
}


def evaluate(draw: dict[str, float], ticks: int) -> dict:
    out: dict[str, object] = {}

    world = load_world()
    world.tuning.update(draw)
    total_myths = len(world.myths)
    hist = engine.run(world, scenarios.absent, ticks)
    peak = max(max(f.bleed.values()) for f in hist.frames)
    out["stable"] = (
        not any(r.sterile for r in world.regions.values())
        and len(world.living_myths()) >= total_myths // 2
        and peak < 0.20
    )

    world = load_world()
    world.tuning.update(draw)
    hist = engine.run(world, scenarios.monoculture, ticks)
    onsets: dict[str, int] = {}
    for e in hist.events:
        if e.kind == "bleed_onset":
            onsets.setdefault(e.region, e.tick)  # first onset only
    no_return = {e.region: e.tick for e in hist.events if e.kind == "no_return"}
    peak = max(max(f.bleed.values()) for f in hist.frames)

    out["punishing"] = any(r.sterile for r in world.regions.values()) or peak > 0.90
    middles = [no_return[r] - onsets[r] for r in no_return if r in onsets]
    out["middle"] = min(middles) if middles else None
    out["reactable"] = out["middle"] is not None and out["middle"] >= MIN_MIDDLE

    # Rivals have to stay in the fight. The player going 600-1 means the
    # Messengers are scenery, and a player who cannot ever win means the
    # strength-from-belief loop gives them nothing.
    world = load_world()
    world.tuning.update(draw)
    engine.run(world, scenarios.warlord, ticks)
    fights = world.contests
    rate = world.player_wins / fights if fights else 0.0
    out["fights"] = fights
    out["win_rate"] = rate
    out["competitive"] = fights >= 20 and 0.35 <= rate <= 0.95

    # Deliberate collecting must still beat doing nothing, or intervention
    # has no payoff and the optimal play is to leave the world alone.
    world = load_world()
    world.tuning.update(draw)
    engine.run(world, scenarios.absent, ticks)
    lazy = len(world.bound)
    world = load_world()
    world.tuning.update(draw)
    engine.run(world, scenarios.collector, ticks)
    out["bind_gap"] = len(world.bound) - lazy
    out["rewarding"] = out["bind_gap"] >= 2

    out["viable"] = bool(
        out["stable"] and out["punishing"] and out["reactable"]
        and out["competitive"] and out["rewarding"]
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=400, help="number of draws")
    ap.add_argument("--ticks", type=int, default=220)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    base = load_world().tuning
    results = []

    for i in range(args.n):
        draw = {k: rng.uniform(lo, hi) for k, (lo, hi) in RANGES.items()}
        try:
            res = evaluate(draw, args.ticks)
        except Exception:
            continue
        results.append((draw, res))
        if (i + 1) % 50 == 0:
            done = sum(1 for _, r in results if r["viable"])
            print(f"  {i + 1}/{args.n} draws, {done} viable", file=sys.stderr)

    viable = [d for d, r in results if r["viable"]]
    n = len(results)

    print()
    print("=" * 78)
    print(f"PARAMETER SWEEP - {n} draws, {len(viable)} viable ({100 * len(viable) / max(1, n):.0f}%)")
    print("=" * 78)

    for label, key in (
        ("stable unattended", "stable"),
        ("punishes monoculture", "punishing"),
        (f"middle >= {MIN_MIDDLE} ticks", "reactable"),
        ("rivals competitive", "competitive"),
        ("collecting beats idling", "rewarding"),
    ):
        hits = sum(1 for _, r in results if r[key])
        print(f"  {label:<24} {hits:>4}/{n}  ({100 * hits / max(1, n):>3.0f}%)")

    middles = [r["middle"] for _, r in results if r["middle"] is not None]
    if middles:
        middles.sort()
        print(
            f"  middle length           min {middles[0]}  median {middles[len(middles) // 2]}"
            f"  max {middles[-1]}  (n={len(middles)})"
        )

    if not viable:
        print("\n  No viable draws. The current shape of the mechanic may not survive.")
        return 1

    print()
    print(f"{'parameter':<26}{'viable range':>22}{'median':>10}{'current':>10}")
    print("-" * 78)
    for key, (lo, hi) in RANGES.items():
        vals = sorted(d[key] for d in viable)
        med = vals[len(vals) // 2]
        span = (vals[-1] - vals[0]) / (hi - lo)
        flag = "  <- tight" if span < 0.45 else ""
        print(
            f"{key:<26}{vals[0]:>10.4f} - {vals[-1]:<9.4f}{med:>10.4f}{base[key]:>10.4f}{flag}"
        )
    print("-" * 78)
    print("  'viable range' is where viable draws actually landed, out of the range")
    print("  sampled. A tight range means that constant is load-bearing and the")
    print("  mechanic is sensitive to it. A wide one means it barely matters.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
