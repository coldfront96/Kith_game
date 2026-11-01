"""The tick loop.

One tick is roughly a week of in-world time. Order within a tick matters and is
deliberate:

    1. the region tells its own stories (homeostasis - people do this without you)
    2. the player tells a story somewhere
    3. attention decays (flat decay kills obscure myths first)
    4. the land feeds the dominant myth back into itself   <- the runaway term
    5. bleed accrues or heals against the dominant share
    6. people die or flee
    7. refugees carry their myths into whoever shelters them
    8. extinctions and last-tellings are recorded

Everything is driven by sim/data/tuning.json. No constants live in this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import messengers as mess
from .model import World


@dataclass
class Event:
    tick: int
    kind: str
    region: str
    detail: str


@dataclass
class Frame:
    """One tick of recorded history, for plotting and reporting."""

    tick: int
    shares: dict[str, dict[str, float]]  # region -> myth -> share
    vitality: dict[str, float]
    bleed: dict[str, float]
    population: dict[str, float]
    living: int
    bound: int


@dataclass
class History:
    frames: list[Frame] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    def series(self, getter) -> list:
        return [getter(f) for f in self.frames]


def _record(world: World, history: History, kind: str, region: str, detail: str) -> None:
    history.events.append(Event(world.tick, kind, region, detail))


def tell(world: World, region_id: str, myth_id: str) -> None:
    """The player's only verb: retell a story in a place."""
    region = world.regions[region_id]
    if region.sterile:
        return
    world.player_location = region_id
    gain = world.tuning["telling_gain"] * region.transmission
    region.weights[myth_id] = region.weights.get(myth_id, 0.0) + gain


def _native_telling(world: World) -> None:
    """People retell their own stories whether or not the player is anywhere near.

    Without this the world has no homeostasis: flat decay kills small myths,
    which raises the dominant myth's *share*, which trips Bleed. Every region
    then monocultures and sterilises itself with no player involvement, which
    is both wrong and extremely boring.

    The budget splits two ways. Half follows what is already told (reinforcing,
    rich-get-richer). Half is spread evenly across the myths native to the
    region - the tradition floor that keeps an old story alive even when it is
    out of fashion. A region's output scales with its surviving population, so
    a dying place tells fewer stories: population is both the engine and the
    hostage.
    """
    t = world.tuning
    tradition_cut = t["native_tradition_share"]

    for region in world.regions.values():
        if region.sterile or not region.weights:
            continue

        # Budget scales with how many stories the place actually knows,
        # because decay_flat is charged per myth. A flat per-region budget
        # meant a myth-rich region hemorrhaged its own traditions.
        alive = region.population / max(1.0, region.population0)
        budget_base = t["native_telling_per_myth"] * len(region.weights)
        budget = budget_base * region.transmission * min(1.0, alive)
        if budget <= 0:
            continue

        native = [m.id for m in world.myths.values() if m.home == region.id]
        known_native = [m for m in native if m in region.weights]

        tradition_pot = budget * tradition_cut if known_native else 0.0
        fashion_pot = budget - tradition_pot

        # Fashion gain is damped by how saturated a myth already is: everyone
        # has heard it, so retelling it earns less. share*(1-share) peaks at
        # 0.25, hence the x4 to keep peak throughput comparable. This is the
        # homeostat - and note the player's own telling is NOT damped, so a
        # population self-regulates and only the Messenger can shove a region
        # past its natural ceiling into Bleed.
        damping = t["native_fashion_damping"]
        for myth_id, share in region.shares().items():
            if share > 0:
                region.weights[myth_id] += fashion_pot * share * ((1.0 - share) ** damping) * 4.0

        if known_native:
            # Weighted by rootedness, not split evenly. An even split forces
            # every region to a perfectly stable duopoly of its natives, which
            # means nothing is ever obscure and nothing ever needs rescuing.
            # Rootedness is what makes some stories fade on their own.
            roots = {m: world.myth(m).rootedness for m in known_native}
            total_root = sum(roots.values())
            if total_root > 0:
                for myth_id, root in roots.items():
                    region.weights[myth_id] += tradition_pot * (root / total_root)


def _decay(world: World, history: History) -> None:
    flat = world.tuning["decay_flat"]
    prop = world.tuning["decay_proportional"]
    floor = world.tuning["extinction_floor"]

    for region in world.regions.values():
        for myth_id in list(region.weights):
            w = region.weights[myth_id]
            w = (w - flat) * (1.0 - prop)
            if w <= floor:
                del region.weights[myth_id]
                _record(
                    world, history, "forgotten", region.id,
                    f"{world.myth(myth_id).name} is no longer told in {region.name}",
                )
            else:
                region.weights[myth_id] = w


def _bleed(world: World, history: History) -> None:
    t = world.tuning
    threshold = t["bleed_threshold"]
    headroom = max(1e-6, 1.0 - threshold)

    for region in world.regions.values():
        if region.sterile:
            continue

        myth_id, share = region.dominant()

        if myth_id is not None and share > threshold:
            overshoot = (share - threshold) / headroom
            region.bleed = min(1.0, region.bleed + t["bleed_rate"] * overshoot)
            domain = world.myth(myth_id).domain
            if region.bleed_domain != domain and region.bleed > t["bleed_visible"]:
                region.bleed_domain = domain
                _record(
                    world, history, "bleed_onset", region.id,
                    f"{region.name} is turning to {world.domain_terrain[domain]}",
                )
            # the land proves the story
            region.weights[myth_id] = region.weights.get(myth_id, 0.0) + (
                t["bleed_feedback"] * region.bleed
            )
        else:
            region.bleed = max(0.0, region.bleed - t["bleed_recovery"])
            if region.bleed == 0.0:
                region.bleed_domain = None

        if not region.doomed and region.bleed >= t["point_of_no_return"]:
            region.doomed = True
            _record(
                world, history, "no_return", region.id,
                f"{region.name} is past saving",
            )


def _people(world: World, history: History) -> None:
    t = world.tuning
    onset = t["population_bleed_onset"]
    displaced: dict[str, float] = {}

    for region in world.regions.values():
        if region.sterile or region.bleed <= onset:
            continue
        severity = (region.bleed - onset) / max(1e-6, 1.0 - onset)
        lost = region.population * t["population_loss_rate"] * severity
        region.population = max(0.0, region.population - lost)
        displaced[region.id] = lost * t["refugee_fraction"]

        if region.population <= t["sterile_population"] and not region.sterile:
            region.sterile = True
            region.weights.clear()
            _record(
                world, history, "sterile", region.id,
                f"{region.name} is empty - no one left to believe anything",
            )

    # refugees carry their myths into whoever shelters them
    for origin_id, people in displaced.items():
        origin = world.regions[origin_id]
        hosts = [world.regions[n] for n in origin.neighbors if not world.regions[n].sterile]
        if not hosts or people <= 0:
            continue
        share_each = people / len(hosts)
        carried = origin.shares()
        for host in hosts:
            host.population += share_each
            # Mixing model: the host's belief vector is pulled toward the
            # refugees' in proportion to how much of the new population they
            # are. refugee_carry > 1 because the displaced are disproportionately
            # loud about the story that just took their home from them.
            blend = min(1.0, t["refugee_carry"] * share_each / max(1.0, host.population))
            if blend <= 0:
                continue
            host_vitality = max(host.vitality, t["vitality_thin"])
            for myth_id, share in carried.items():
                if share <= 0:
                    continue
                target = share * host_vitality
                current = host.weights.get(myth_id, 0.0)
                if target <= current:
                    continue
                host.weights[myth_id] = current + blend * (target - current)
                if current <= 0 and host.weights[myth_id] > t["extinction_floor"]:
                    _record(
                        world, history, "carried", host.id,
                        f"{world.myth(myth_id).name} arrives in {host.name} with refugees from {origin.name}",
                    )


def _watch_last_tellings(world: World, history: History) -> None:
    cut = world.tuning["last_telling_share"]
    for region in world.regions.values():
        if region.sterile:
            continue
        for myth_id, share in region.shares().items():
            if 0 < share < cut:
                _record(
                    world, history, "last_telling", region.id,
                    f"{world.myth(myth_id).name} is nearly gone from {region.name}",
                )


def _binding(world: World, history: History) -> None:
    """A myth whose share clears bind_threshold anywhere is collectable there.

    This is what gives deliberate intervention a payoff that global upkeep does
    not need to supply. The player is not maintaining the world - they go to a
    region because they want something out of it, push a specific story up past
    the line, and take the local Bleed risk that comes with pushing. A myth
    already fading is the only one that needs the push, so the dying story is
    the prize.
    """
    if not world.auto_bind:
        return
    cut = world.tuning["bind_threshold"]
    for region in world.regions.values():
        if region.sterile:
            continue
        for myth_id, share in region.shares().items():
            if share >= cut and myth_id not in world.bound:
                world.bound.add(myth_id)
                _record(
                    world, history, "bound", region.id,
                    f"{world.myth(myth_id).name} can be bound in {region.name}",
                )


def _snapshot(world: World) -> Frame:
    return Frame(
        tick=world.tick,
        shares={r.id: r.shares() for r in world.regions.values()},
        vitality={r.id: r.vitality for r in world.regions.values()},
        bleed={r.id: r.bleed for r in world.regions.values()},
        population={r.id: r.population for r in world.regions.values()},
        living=len(world.living_myths()),
        bound=len(world.bound),
    )


def run(world: World, policy, ticks: int | None = None) -> History:
    """Run a scenario. `policy` is called once per tick and may call tell()."""
    history = History()
    ticks = int(ticks if ticks is not None else world.tuning["ticks"])

    history.frames.append(_snapshot(world))

    for _ in range(ticks):
        world.tick += 1
        _native_telling(world)
        mess.step_maintainers(world, history, _record)
        policy(world)
        mess.step_contests(world, history, _record)
        _decay(world, history)
        _bleed(world, history)
        _people(world, history)
        _binding(world, history)
        _watch_last_tellings(world, history)
        history.frames.append(_snapshot(world))

    return history
