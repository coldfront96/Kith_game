"""Three player policies.

The gate these exist to pass: do the three produce visibly different worlds?
If they converge, the belief ledger has no dynamics worth building a game on.
"""

from __future__ import annotations

from .engine import tell
from .model import World

FOCUS = "greenhollow"


def absent(world: World) -> None:
    """The player does nothing. Baseline: what does the valley do alone?"""
    return None


def monoculture(world: World) -> None:
    """The player spams one story in one place. Tests the Bleed cliff."""
    tell(world, FOCUS, "greenmother")


def gardener(world: World) -> None:
    """The player deliberately props up whichever myth in the focus region is
    closest to being forgotten. Tests whether balancing is actually playable
    or just a losing fight against decay."""
    region = world.regions[FOCUS]
    if region.sterile:
        return
    shares = {m: s for m, s in region.shares().items() if s > 0}
    if not shares:
        return
    weakest = min(shares, key=lambda k: shares[k])
    tell(world, FOCUS, weakest)


def opportunist(world: World) -> None:
    """The player chases power: always feeds the strongest myth, but backs off
    the moment the land starts to turn. Tests whether the telegraphed middle is
    long enough to actually react to."""
    region = world.regions[FOCUS]
    if region.sterile:
        return
    myth_id, _ = region.dominant()
    if myth_id is None:
        return
    if region.bleed > 0.15:
        shares = {m: s for m, s in region.shares().items() if s > 0 and m != myth_id}
        if shares:
            tell(world, FOCUS, min(shares, key=lambda k: shares[k]))
        return
    tell(world, FOCUS, myth_id)


ALL = {
    "absent": absent,
    "monoculture": monoculture,
    "gardener": gardener,
    "opportunist": opportunist,
}
