"""Data model for the Kith belief simulation.

Everything here loads from JSON under sim/data/. Nothing about the world is
hardcoded, because the save-migration trap in DESIGN.md means this schema
outlives the prototype - Godot will read the same files later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 2

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SchemaError(RuntimeError):
    """Raised when a data file is a schema version this code does not speak."""


def _load(name: str) -> dict:
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        blob = json.load(handle)
    found = blob.get("schema_version")
    if found != SCHEMA_VERSION:
        raise SchemaError(
            f"{path.name} is schema_version {found!r}, this build speaks {SCHEMA_VERSION}"
        )
    return blob


@dataclass(frozen=True)
class Myth:
    id: str
    name: str
    domain: str
    home: str
    rootedness: float = 1.0
    blurb: str = ""


@dataclass
class Region:
    id: str
    name: str
    cosmology: str
    population: float
    transmission: float
    neighbors: list[str]

    # mutable state
    population0: float = 0.0  # starting population, for scaling native telling
    weights: dict[str, float] = field(default_factory=dict)
    bleed: float = 0.0
    bleed_domain: str | None = None
    sterile: bool = False
    doomed: bool = False  # passed the point of no return

    @property
    def vitality(self) -> float:
        """Total raw attention. Low vitality is a thin, featureless place."""
        return sum(self.weights.values())

    def shares(self) -> dict[str, float]:
        """Belief as a share of regional attention. This is the zero-sum view:
        raising one myth necessarily lowers every other."""
        total = self.vitality
        if total <= 0:
            return {m: 0.0 for m in self.weights}
        return {m: w / total for m, w in self.weights.items()}

    def dominant(self) -> tuple[str | None, float]:
        s = self.shares()
        if not s:
            return None, 0.0
        myth_id = max(s, key=lambda k: s[k])
        return myth_id, s[myth_id]


@dataclass
class World:
    myths: dict[str, Myth]
    regions: dict[str, Region]
    domain_terrain: dict[str, str]
    tuning: dict[str, float]
    tick: int = 0

    # Myths the player has managed to bind. A myth can only be bound where its
    # share clears bind_threshold - you cannot learn verses nobody recites. Once
    # bound it stays bound, even if the myth later dies out of the world.
    bound: set[str] = field(default_factory=set)

    # Rival Messengers and where the player last spoke. A contest fires
    # wherever a maintainer and the player are standing in the same place.
    messengers: dict = field(default_factory=dict)
    player_location: str = ""
    contests: int = 0
    player_wins: int = 0
    player_losses: int = 0

    def myth(self, myth_id: str) -> Myth:
        return self.myths[myth_id]

    def living_myths(self) -> set[str]:
        """Myths that still exist anywhere in the world."""
        alive: set[str] = set()
        for region in self.regions.values():
            alive.update(m for m, w in region.weights.items() if w > 0)
        return alive

    def extinct_myths(self) -> set[str]:
        return set(self.myths) - self.living_myths()


def load_world() -> World:
    myth_blob = _load("myths.json")
    region_blob = _load("regions.json")
    tuning_blob = _load("tuning.json")

    myths = {m["id"]: Myth(**m) for m in myth_blob["myths"]}

    regions: dict[str, Region] = {}
    for spec in region_blob["regions"]:
        initial = region_blob["initial_weights"].get(spec["id"], {})
        unknown = set(initial) - set(myths)
        if unknown:
            raise SchemaError(f"region {spec['id']} seeds unknown myths: {sorted(unknown)}")
        regions[spec["id"]] = Region(
            id=spec["id"],
            name=spec["name"],
            cosmology=spec["cosmology"],
            population=float(spec["population"]),
            transmission=float(spec["transmission"]),
            neighbors=list(spec["neighbors"]),
            population0=float(spec["population"]),
            weights=dict(initial),
        )

    for region in regions.values():
        missing = [n for n in region.neighbors if n not in regions]
        if missing:
            raise SchemaError(f"region {region.id} names unknown neighbors: {missing}")

    tuning = {k: v for k, v in tuning_blob.items() if not k.startswith("comment")}
    tuning.pop("schema_version", None)

    from .messengers import Messenger

    messenger_blob = _load("messengers.json")
    messengers: dict[str, Messenger] = {}
    for spec in messenger_blob["messengers"]:
        bad = [b for b in spec["bound"] if b not in myths]
        if bad or spec["home"] not in regions:
            raise SchemaError(f"messenger {spec['id']} references unknown myths/region: {bad or spec['home']}")
        messengers[spec["id"]] = Messenger(**spec)

    return World(
        myths=myths,
        regions=regions,
        domain_terrain=myth_blob["domain_terrain"],
        tuning=tuning,
        messengers=messengers,
    )
