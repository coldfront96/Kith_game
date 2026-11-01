"""Rival Messengers: the homeostasis with a face.

In the sim as first written, the thing holding the world together was
`_native_telling()` - an abstract per-region budget. That works but it is a
number in a tick loop. Making it agents means the stabilising force can be met,
argued with, fought and displaced, and it answers the ten-regions problem: the
player does not have to tend the world because *they* tend the world.

Maintainers walk their circuit and prop up whichever story in the region they
are standing in is closest to being forgotten. The player is the rogue: the
only Messenger who pushes a myth instead of balancing one.

Contests resolve as a tug-of-war over a single shared audience rather than two
health bars. Each side's standing in the region is the summed local belief in
the myths they carry, so a contest on someone's home turf opens with the crowd
already against you. The outcome is written straight into the region's ledger -
the fight IS a belief transaction, with nothing separate to reconcile.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Messenger:
    id: str
    name: str
    home: str
    behavior: str
    bound: list[str]
    travel_period: int
    location: str = ""
    wins: int = 0
    losses: int = 0

    def __post_init__(self) -> None:
        if not self.location:
            self.location = self.home


def standing(world, who_bound, region_id: str) -> float:
    """How much of the local audience already believes the stories you carry.

    This is the combat stat, and the player never sets it directly - it is
    whatever the region currently believes.
    """
    region = world.regions[region_id]
    shares = region.shares()
    return sum(shares.get(m, 0.0) for m in who_bound)


def _circuit(world, m: Messenger) -> None:
    """Move toward whichever reachable region is furthest out of balance."""
    here = world.regions[m.location]
    options = [here.id, *here.neighbors]
    worst, worst_score = m.location, -1.0
    for region_id in options:
        region = world.regions[region_id]
        if region.sterile:
            continue
        _, share = region.dominant()
        score = share + region.bleed
        if score > worst_score:
            worst, worst_score = region_id, score
    m.location = worst


def step_maintainers(world, history, record) -> None:
    """Each maintainer props up the weakest story where they stand, then
    periodically moves on."""
    t = world.tuning
    gain = t["telling_gain"] * t["maintainer_vigor"]

    for m in world.messengers.values():
        region = world.regions[m.location]
        if region.sterile:
            _circuit(world, m)
            continue

        shares = {k: v for k, v in region.shares().items() if v > 0}
        if shares:
            weakest = min(shares, key=lambda k: shares[k])
            region.weights[weakest] = region.weights.get(weakest, 0.0) + gain * region.transmission

        # Maintainers bind what they champion, by the same rule the player
        # uses. Without this they carry a fixed loadout for the whole game
        # while the player's repertoire grows without bound, and the player
        # wins essentially every contest in the entire parameter space.
        if len(m.bound) < t["rival_repertoire_cap"]:
            for myth_id, share in region.shares().items():
                if share >= t["bind_threshold"] and myth_id not in m.bound:
                    m.bound.append(myth_id)
                    break

        if m.travel_period > 0 and world.tick % m.travel_period == 0:
            _circuit(world, m)


def step_contests(world, history, record) -> None:
    """A contest fires wherever a maintainer and the player are both standing.

    One shared slider, opening at the local belief ratio. Winner takes ground,
    loser gives it, and the result lands in the ledger. A myth the loser has
    bound never falls below `bound_floor` share - they still carry that story
    and they are standing right there telling it.
    """
    t = world.tuning
    if not world.player_location:
        return

    region = world.regions[world.player_location]
    if region.sterile or not region.weights:
        return

    for m in world.messengers.values():
        if m.location != world.player_location:
            continue

        # Only what you disagree on is contested. A story you both carry is
        # common ground, not an argument - and counting it gave the travelling
        # generalist who had bound everything an automatic win everywhere,
        # because their total included the rival's own myths.
        shared = world.bound & set(m.bound)
        mine_only = world.bound - shared
        theirs_only = set(m.bound) - shared
        mine = standing(world, mine_only, region.id)
        theirs = standing(world, theirs_only, region.id)
        total = mine + theirs
        if total <= 0:
            continue

        margin = (mine - theirs) / total
        if abs(margin) < t["contest_deadzone"]:
            continue

        world.contests += 1
        winner_bound = mine_only if margin > 0 else theirs_only
        loser_bound = theirs_only if margin > 0 else mine_only
        if margin > 0:
            world.player_wins += 1
            m.losses += 1
        else:
            world.player_losses += 1
            m.wins += 1

        # Damped by how much of the room the winner already holds. Without
        # this, contests run away - winning raises standing, which wins more
        # contests - and rivals stop mattering after the early game.
        won_standing = mine if margin > 0 else theirs
        damp = max(0.0, 1.0 - won_standing) ** t["contest_saturation_damping"]
        pot = t["contest_swing"] * abs(margin) * region.vitality * damp
        shares = region.shares()

        # take it off the loser, proportionally, respecting the floor
        taken = 0.0
        loser_live = {k: shares.get(k, 0.0) for k in loser_bound if shares.get(k, 0.0) > 0}
        loser_total = sum(loser_live.values())
        if loser_total <= 0:
            continue
        for myth_id, share in loser_live.items():
            want = pot * (share / loser_total)
            floor_weight = t["bound_floor"] * region.vitality
            available = max(0.0, region.weights.get(myth_id, 0.0) - floor_weight)
            moved = min(want, available)
            region.weights[myth_id] = region.weights.get(myth_id, 0.0) - moved
            taken += moved

        # and give it to the winner, proportionally to what they already hold
        winner_live = {k: shares.get(k, 0.0) for k in winner_bound if shares.get(k, 0.0) > 0}
        winner_total = sum(winner_live.values())
        if winner_total <= 0 or taken <= 0:
            continue
        for myth_id, share in winner_live.items():
            region.weights[myth_id] = region.weights.get(myth_id, 0.0) + taken * (share / winner_total)

        record(
            world, history, "contest", region.id,
            f"{'player' if margin > 0 else m.name} takes the room in {region.name}",
        )
