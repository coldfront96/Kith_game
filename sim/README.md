# Belief simulation — Gate 1

A headless simulation of the belief ledger, Bleed, and refugee contagion described in [DESIGN.md](../DESIGN.md). No rendering, no engine, no art.

It exists to answer one question before a single line of Godot gets written:

> **Does the belief ledger have dynamics worth building a game on?**

If belief always flattens to mush, or Bleed goes from fine to crater in three ticks with no visible middle, then no amount of art makes that feel like anything. Find out in a weekend, not in year three.

## Run it

```bash
cd sim
python3 run.py                 # all scenarios, report + plots in out/
python3 run.py --no-plot       # report only
python3 run.py monoculture     # one scenario with its full event log
python3 run.py --ticks 400     # longer run
```

Only needs `matplotlib` (and only for the plots).

## Where the knobs are

**All of them are in `data/tuning.json`.** Nothing is hardcoded. Tuning this system means editing JSON and re-running, never touching Python.

The world itself is data too — `data/myths.json` and `data/regions.json`. This is deliberate: DESIGN.md flags save migration as the day-one engineering trap, so the schema has to outlive the prototype. Godot reads these same files later. Every data file carries `schema_version` and loading refuses a version it does not speak.

## The scenarios

| Scenario | Player policy | Tests |
| --- | --- | --- |
| `absent` | does nothing | Is the world stable on its own? |
| `monoculture` | spams one story in one region | The Bleed cliff |
| `gardener` | props up whichever myth is closest to forgotten | Is balancing playable, or a losing fight with decay? |
| `opportunist` | feeds the strongest myth, backs off when the land turns | Is the telegraphed middle long enough to react to? |

## Gate 1 result: pass

```
scenario        myths      pop  onset  middle  sterile  xborder
absent          6/6     6,900      -       -        0        0
monoculture     5/6     3,835     13      24        1        3
gardener        6/6     6,900      -       -        0        0
opportunist     6/6     6,900     61       -        0        0
```

- **Policies produce visibly different worlds.** Monoculture costs 44% of the valley's population, sterilises a region and loses a myth. The others do not.
- **The middle is 24 ticks** — roughly six months of in-world time between the land visibly turning and the point of no return. DESIGN.md calls for a long, loud, visible middle and this clears it comfortably.
- **`opportunist` proves the window is usable.** It walks right up to Bleed (onset at t61), notices, backs off, and recovers with no deaths. A player who is paying attention can save themselves.
- **Bleed crosses borders**, and the way it does is the most interesting thing the sim produced (below).

## Three findings

### 1. The world needs homeostasis or it eats itself

First run, `absent` sterilised all three regions. Flat decay kills obscure myths first, which *raises* the dominant myth's share, which trips Bleed. Every region monocultured and died with no player involvement.

Fix: regions tell their own stories. `_native_telling()` gives each region a per-tick budget split between what is already popular and a floor under its native traditions, scaled by surviving population — so a dying place tells fewer stories.

### 2. Only the player should be able to cause Bleed

Native telling alone was not enough; the "retell what's popular" term is rich-get-richer and still monocultured. The fix fell out of the fiction: **an over-told story gets boring.** Native retelling is damped by `(1 - share)`, so a saturated myth earns less attention from the people who already know it.

The player's telling is **not** damped. Which means populations self-regulate, and the Messenger is the only force in the world that can shove a region past its natural ceiling. That is thematically exact and it was not designed in — it fell out of making the numbers behave.

### 3. Refugee contagion has a very long fuse

In `monoculture`, Green Hollow craters and its survivors scatter at t27. Greenmother rides out with them into Stonereach, climbs for over a hundred ticks, crosses the threshold around t150, and Stonereach is cratering by t180.

**That is roughly three years of in-world time between the player's mistake and the second valley starting to burn.** The player will very likely never connect the two events, which is exactly right.

And it is not deterministic. Fenmouth took refugees too and stayed healthy, because it had enough mythic diversity to absorb them. Stonereach was small and thin, so it got taken over. **A diverse region resists contagion; a thin one does not.** Nobody designed that — it is a consequence of share-based belief plus a mixing model.

## Known gap

`absent` and `gardener` produce identical outcomes. Tending the garden currently has no upside, only downside-avoidance, which runs into DESIGN.md's own warning that Bleed must never be purely punitive.

This is a design question, not a tuning one: **what does a well-tended region give the player that a neglected one does not?** Richer encounter tables, syncretism opportunities, higher vitality unlocking more Kith. Until that is answered, the optimal strategy is to leave the world alone, which is not a game.

## Next

Gate 2 is a Godot grey-box: one valley, colored cubes, this simulation driving terrain swaps. The question there is no longer whether the system has dynamics — it does — but whether *watching* it produces a feeling.

## Layout

```
sim/
  run.py              CLI, report, plots
  kith/
    model.py          dataclasses, JSON loading, schema guard
    engine.py         the tick loop
    scenarios.py      the four player policies
  data/
    myths.json        six myths, their domains and homes
    regions.json      one valley, three settlements, two cosmologies
    tuning.json       every constant
  out/                generated plots
```
