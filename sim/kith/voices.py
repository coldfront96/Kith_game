"""Turning the belief ledger into something you overhear.

The player never reads the ledger. They walk through a settlement and notice
that nobody has mentioned the Bride in a while. This module is the bridge:
given a region's belief state, produce what the place actually sounds like.

Structural floor, authored ceiling. Templates are keyed by (belief band x
speaker) so every myth in the game has coverage forever and none is ever silent
just because nobody got round to writing for it. Myth-specific nouns slot in,
and bespoke lines can be layered on top where a myth deserves them.

Children are the leading indicator. They learn what is common, so their voices
dry up a band ahead of everyone else's - a myth no child mentions is one
generation from gone, and that is information no share number gives you.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SPEAKERS = ["child", "worker", "elder", "priest"]
_DATA = Path(__file__).resolve().parent.parent / "data" / "voices.json"


class Voices:
    def __init__(self, path: Path = _DATA) -> None:
        with path.open(encoding="utf-8") as fh:
            blob = json.load(fh)
        self.bands: dict[str, float] = blob["bands"]
        self.lines: dict = blob["lines"]
        self.markers: dict[str, str] = blob["markers"]
        self.land: dict[str, str] = blob["land"]
        self.child_silence = blob["child_silence_band"]
        self.rhyme_band = blob["rhyme_band"]
        self._order = sorted(self.bands, key=lambda b: -self.bands[b])

    def band(self, share: float, n_myths: int = 1) -> str:
        """Which belief band a share falls in, relative to an even split.

        Cuts are multiples of 1/n so they scale with how many stories a region
        holds. An absolute cut would call a 0.10 myth healthy in a thin region
        and dying in a rich one, for the same 0.10.
        """
        if share <= 0:
            return "gone"
        rel = share * max(1, n_myths)
        for name in self._order:
            if rel >= self.bands[name]:
                return name
        return self._order[-1]

    def _fill(self, template: str, myth) -> str:
        v = dict(myth.voice or {})
        v.setdefault("subject", myth.name)
        v.setdefault("place", "the old ground")
        v.setdefault("sign", "the sign")
        v.setdefault("verb", "it is remembered")
        try:
            return template.format(name=myth.name, **v)
        except KeyError:
            return template

    def line(self, myth, share: float, speaker: str, rng: random.Random, n_myths: int = 1) -> str | None:
        band = self.band(share, n_myths)
        if band == "gone":
            return None
        if speaker == "child" and band == self.child_silence:
            return None
        pool = self.lines.get(band, {}).get(speaker, [])
        if not pool:
            return None
        return self._fill(rng.choice(pool), myth)

    def marker(self, myth, share: float, n_myths: int = 1) -> str:
        return self._fill(self.markers[self.band(share, n_myths)], myth)

    def still_sung(self, share: float, n_myths: int = 1) -> bool:
        """Do children still have a rhyme for it? The early warning."""
        return share * max(1, n_myths) >= self.bands[self.rhyme_band]


def walk(world, region_id: str, overheard: int = 9, seed: int | None = None) -> dict:
    """One pass through a settlement. Returns what you would notice.

    Myths are sampled in proportion to belief, which is the whole mechanic:
    a story everyone tells comes up constantly, one at three percent you hear
    once, from one person, if you happen to be standing in the right place.
    """
    rng = random.Random(seed)
    v = world.voices
    region = world.regions[region_id]
    shares = {m: s for m, s in region.shares().items() if s > 0}

    out: dict = {
        "region": region.name,
        "sterile": region.sterile,
        "heard": [],
        "markers": [],
        "land": None,
        "silent": [],
        "unsung": [],
    }
    if region.sterile or not shares:
        return out

    if region.bleed > world.tuning["bleed_visible"] and region.bleed_domain:
        out["land"] = v.land.get(region.bleed_domain)

    myth_ids = list(shares)
    n = len(myth_ids)
    weights = [shares[m] for m in myth_ids]
    seen: set[str] = set()
    for _ in range(overheard * 3):
        if len(out["heard"]) >= overheard:
            break
        myth_id = rng.choices(myth_ids, weights=weights, k=1)[0]
        myth = world.myth(myth_id)
        speaker = rng.choice(SPEAKERS)
        said = v.line(myth, shares[myth_id], speaker, rng, n)
        if said and said not in seen:
            seen.add(said)
            out["heard"].append((speaker, myth.name, said))

    for myth_id, share in sorted(shares.items(), key=lambda kv: -kv[1]):
        myth = world.myth(myth_id)
        out["markers"].append(v.marker(myth, share, n))
        if not v.still_sung(share, n):
            out["unsung"].append(myth.name)

    spoken = {name for _, name, _ in out["heard"]}
    out["silent"] = [world.myth(m).name for m in shares if world.myth(m).name not in spoken]
    return out


def render(snapshot: dict, tick: int) -> str:
    """Format a walk as prose you can actually read."""
    lines = [f"--- {snapshot['region']}, tick {tick} " + "-" * max(0, 46 - len(snapshot["region"]))]
    if snapshot["sterile"]:
        lines.append("  Nobody is here. Nothing is told.")
        return "\n".join(lines)

    if snapshot["land"]:
        lines.append(f"  {snapshot['land']}")
        lines.append("")

    for speaker, myth, said in snapshot["heard"]:
        lines.append(f"  {speaker + ':':<8} \"{said}\"")
        lines.append(f"  {'':<8}   ({myth})")

    if snapshot["markers"]:
        lines.append("")
        for mk in snapshot["markers"][:3]:
            lines.append(f"  {mk}")

    if snapshot["unsung"]:
        lines.append("")
        lines.append(f"  No child here has a rhyme for: {', '.join(snapshot['unsung'])}")
    return "\n".join(lines)
