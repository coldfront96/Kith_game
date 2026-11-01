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


def collector(world: World) -> None:
    """The player travels, and intervenes only where they want something.

    Find the unbound myth closest to becoming collectable and push that one,
    wherever it is. Once a myth is bound, stop caring about it and move on.
    This is targeted intervention, not upkeep: the player never tries to hold
    the whole world in balance, they just go get what they came for.

    The point of this policy is to test whether deliberate play beats doing
    nothing on the metric the player actually cares about - creatures bound -
    without requiring them to babysit every region.
    """
    best = None
    cut = world.tuning["bind_threshold"]

    for region in world.regions.values():
        if region.sterile:
            continue
        for myth_id, share in region.shares().items():
            if myth_id in world.bound or share <= 0 or share >= cut:
                continue
            # closest to the line is cheapest to push over it
            if best is None or share > best[2]:
                best = (region.id, myth_id, share)

    if best is not None:
        tell(world, best[0], best[1])


ALL = {
    "absent": absent,
    "monoculture": monoculture,
    "gardener": gardener,
    "opportunist": opportunist,
    "collector": collector,
}


def warlord(world: World) -> None:
    """The combat-optimal player: force your own stories into the places where
    you are weakest, so your Kith hit hardest everywhere you go.

    This policy exists to answer one question - does strength-from-belief
    actually pressure a player into Bleed, or merely tempt them? It plays the
    incentive straight, with no restraint, and we measure what the valley costs.
    """
    best = None
    for region in world.regions.values():
        if region.sterile or not region.weights:
            continue
        shares = region.shares()
        mine = sum(shares.get(m, 0.0) for m in world.bound)
        if best is None or mine < best[1]:
            best = (region.id, mine)

    if best is None:
        return

    region = world.regions[best[0]]
    shares = region.shares()
    carried = {m: shares.get(m, 0.0) for m in world.bound if shares.get(m, 0.0) > 0}
    if carried:
        # push whichever of your stories already has the most purchase here
        tell(world, region.id, max(carried, key=lambda k: carried[k]))
    else:
        tell(world, region.id, max(shares, key=lambda k: shares[k]))


ALL["warlord"] = warlord
