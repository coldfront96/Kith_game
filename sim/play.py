#!/usr/bin/env python3
"""Kith, playable in a terminal. Gate 1.5.

The sim says the belief ledger has dynamics. The charts say a myth went from
0.31 to 0.04. Neither says whether any of it is any good to *play*, and that
is the only question left that does not need an engine to answer:

  - is listening satisfying, or tedious by the fourth town?
  - is the information legible enough to decide from, or do you end up
    wishing for the map overlay after all?
  - does thirty ticks of warning feel long when you are living it?
  - does reviving a dying story feel like a rescue, or like chores?

No graphics, no combat verses, no syncretism. Just travel, listen, tell,
learn - the spine. If the spine is boring here it will be boring in Godot
with better lighting.

    python3 play.py
    python3 play.py --seed 5
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kith import engine, voices  # noqa: E402
from kith.model import load_world  # noqa: E402

COST = {"tell": 1, "learn": 3, "go": 4, "listen": 1}

HELP = """
  look            what you can see and hear right now        (free)
  listen          stay a while and pay attention              (1 week)
  tell <myth>     spread a story you carry                    (1 week)
  learn <myth>    collect its verses, if it is still told here (3 weeks)
  go <place>      travel                                      (4 weeks)
  book            your storybook - what you carry, what you saw, when
  wait [n]        let n weeks pass                            (default 4)
  help            this
  quit            stop
"""


def wrap(text: str, indent: str = "  ") -> str:
    return "\n".join(textwrap.fill(line, 74, initial_indent=indent, subsequent_indent=indent + "  ")
                     for line in text.split("\n"))


class Game:
    def __init__(self, seed: int) -> None:
        self.w = load_world()
        self.w.auto_bind = False
        self.seed = seed
        self.here = "greenhollow"
        self.w.player_location = self.here
        self.journal: dict[str, dict] = {}
        self.heard_of: set[str] = set()

    # ---------- helpers ----------

    def region(self):
        return self.w.regions[self.here]

    def match(self, frag: str, pool) -> str | None:
        frag = frag.strip().lower()
        if not frag:
            return None
        hits = [k for k in pool if frag in k.lower() or frag in pool[k].lower()]
        return hits[0] if len(hits) == 1 else (hits[0] if hits else None)

    def myth_names(self) -> dict[str, str]:
        return {m.id: m.name for m in self.w.myths.values()}

    def advance(self, weeks: int) -> None:
        hist = engine.run(self.w, lambda _w: None, weeks)
        notable = []
        for ev in hist.events:
            if ev.kind in ("bleed_onset", "no_return", "sterile", "carried", "contest"):
                notable.append(ev.detail)
        for d in dict.fromkeys(notable):
            print(wrap(f"* {d}"))
        # you are still standing here, so what you know is current
        if self.here in self.journal:
            self.record_visit()

    def record_visit(self) -> None:
        r = self.region()
        v = self.w.voices
        shares = r.shares()
        n = len(shares)
        self.journal[self.here] = {
            "tick": self.w.tick,
            "bands": {self.w.myth(m).name: v.band(s, n) for m, s in shares.items() if s > 0},
        }
        self.heard_of.update(m for m, s in shares.items() if s > 0)

    # ---------- commands ----------

    def look(self) -> None:
        snap = voices.walk(self.w, self.here, 7, seed=self.seed + self.w.tick)
        print()
        print(f"  {self.region().name.upper()}   week {self.w.tick}")
        if snap["sterile"]:
            print(wrap("Nobody is here. Nothing is told."))
            return
        if snap["land"]:
            print()
            print(wrap(snap["land"]))
        print()
        for speaker, myth, said in snap["heard"][:5]:
            print(wrap(f'{speaker}: "{said}"'))
        if snap["unsung"]:
            print()
            print(wrap(f"No child here has a rhyme for: {', '.join(snap['unsung'])}"))
        here = [m.name for m in self.w.messengers.values() if m.location == self.here]
        if here:
            print()
            print(wrap(f"{' and '.join(here)} is here too."))
        print()
        print(f"  roads: {', '.join(self.w.regions[n].name for n in self.region().neighbors)}")
        self.record_visit()

    def listen(self) -> None:
        snap = voices.walk(self.w, self.here, 14, seed=self.seed + self.w.tick * 7)
        print()
        for speaker, myth, said in snap["heard"]:
            print(wrap(f'{speaker}: "{said}"   [{myth}]'))
        print()
        for mk in snap["markers"][:4]:
            print(wrap(mk))
        self.record_visit()
        self.advance(COST["listen"])

    def tell(self, arg: str) -> None:
        carried = {m: self.w.myth(m).name for m in self.w.bound}
        if not carried:
            print(wrap("You carry no stories yet. Listen, then learn one."))
            return
        key = self.match(arg, carried)
        if not key:
            print(wrap(f"You carry: {', '.join(sorted(carried.values()))}"))
            return
        engine.tell(self.w, self.here, key)
        print(wrap(f"You tell {carried[key]} in {self.region().name}. People listen."))
        self.advance(COST["tell"])

    def learn(self, arg: str) -> None:
        shares = self.region().shares()
        n = len(shares)
        local = {m: self.w.myth(m).name for m in shares if shares[m] > 0}
        key = self.match(arg, local)
        if not key:
            print(wrap("Nobody here tells that. " + (f"You might ask about: {', '.join(sorted(local.values()))}" if local else "")))
            return
        if key in self.w.bound:
            print(wrap(f"You already carry {local[key]}."))
            return
        if shares[key] < self.w.tuning["bind_threshold"]:
            band = self.w.voices.band(shares[key], n)
            print(wrap(f"Too few people here still tell {local[key]} ({band}). You cannot piece the verses together. Someone would have to spread it first."))
            return
        self.w.bound.add(key)
        print(wrap(f"You collect the verses of {local[key]}. It comes with you."))
        self.advance(COST["learn"])

    def go(self, arg: str) -> None:
        options = {r: self.w.regions[r].name for r in self.region().neighbors}
        key = self.match(arg, options)
        if not key:
            print(wrap(f"Roads lead to: {', '.join(options.values())}"))
            return
        self.here = key
        self.w.player_location = key
        print(wrap(f"You walk to {self.w.regions[key].name}."))
        self.advance(COST["go"])
        self.look()

    def book(self) -> None:
        print()
        carried = sorted(self.w.myth(m).name for m in self.w.bound)
        print(wrap(f"You carry {len(carried)} of {len(self.w.myths)}: " + (", ".join(carried) if carried else "nothing yet")))
        if not self.journal:
            return
        print()
        for rid, entry in self.journal.items():
            age = self.w.tick - entry["tick"]
            when = "now" if age == 0 else f"{age} weeks ago"
            print(f"  {self.w.regions[rid].name} ({when})")
            for name, band in sorted(entry["bands"].items(), key=lambda kv: kv[1]):
                print(f"      {band:<13} {name}")
        print()
        print(wrap("(What you wrote down when you were last there. It may be out of date.)"))

    # ---------- loop ----------

    def run(self) -> None:
        print(wrap("You carry stories between places. Nobody else does."))
        print(wrap("Type help for what you can do."))
        self.look()
        while True:
            try:
                raw = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not raw:
                continue
            cmd, _, arg = raw.partition(" ")
            cmd = cmd.lower()
            if cmd in ("quit", "q", "exit"):
                return
            elif cmd in ("help", "h", "?"):
                print(HELP)
            elif cmd in ("look", "l"):
                self.look()
            elif cmd == "listen":
                self.listen()
            elif cmd in ("tell", "t"):
                self.tell(arg)
            elif cmd == "learn":
                self.learn(arg)
            elif cmd in ("go", "travel"):
                self.go(arg)
            elif cmd in ("book", "b"):
                self.book()
            elif cmd == "wait":
                n = int(arg) if arg.strip().isdigit() else 4
                self.advance(n)
                print(wrap(f"{n} weeks pass."))
            else:
                print(wrap("Not something you can do. Try help."))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    Game(args.seed).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
