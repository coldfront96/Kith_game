# Belief simulation — Gate 1

A headless simulation of the belief ledger, Bleed, binding and refugee contagion described in [DESIGN.md](../DESIGN.md). No rendering, no engine, no art.

It exists to answer one question before a line of Godot gets written:

> **Does the belief ledger have dynamics worth building a game on?**

If belief always flattens to mush, or Bleed goes from fine to crater in three ticks with no visible middle, then no amount of art makes that feel like anything. Find out in a weekend, not in year three.

## Run it

```bash
cd sim
python3 run.py                 # all scenarios, report + plots in out/
python3 run.py --no-plot       # report only
python3 run.py collector       # one scenario with its full event log
python3 sweep.py -n 600        # how fragile is any of this?
```

Only needs `matplotlib`, and only for the plots.

## Where the knobs are

**All of them are in `data/tuning.json`.** Nothing is hardcoded. Tuning means editing JSON and re-running, never touching Python.

The world is data too — `data/myths.json`, `data/regions.json`. DESIGN.md flags save migration as the day-one engineering trap, so the schema has to outlive the prototype; Godot reads these same files later. Every file carries `schema_version` and loading refuses a version it does not speak. That guard has already caught one mismatch during development, which is the entire argument for having it.

## The scenarios

| Scenario | Player policy | Tests |
| --- | --- | --- |
| `absent` | does nothing | Is the world stable when left alone? |
| `monoculture` | spams one story in one region | The Bleed cliff |
| `gardener` | props up whichever myth is closest to forgotten | Is balancing playable, or a losing fight with decay? |
| `opportunist` | feeds the strongest myth, backs off when the land turns | Is the telegraphed middle long enough to react to? |
| `collector` | travels, pushes whichever unbound myth is closest to collectable | Does targeted intervention beat doing nothing? |

## Gate 1 result: pass

```
scenario        bound  myths      pop  onset  middle  sterile  xborder
absent           6/10    6/10    6,900      -       -        0        0
monoculture      6/10    5/10    5,299     25      24        1        3
gardener         8/10    8/10    6,900      -       -        0        0
opportunist      6/10    7/10    6,900     25       -        0        0
collector       10/10    6/10    6,900      -       -        0        0
```

- **Policies produce visibly different worlds.** Binding ranges 6–10, surviving myths 5–8, population 5,299–6,900.
- **The middle is 24 ticks** — roughly six months of in-world time between the land visibly turning and the point of no return. DESIGN.md asks for a long, loud, visible middle; this clears it.
- **`opportunist` proves the window is usable.** It walks up to Bleed at t25, notices, backs off, recovers with no deaths. An attentive player can save themselves.
- **`collector` binds 10/10 while only 6 myths survive.** It learned four stories that later died out anyway. Binding is preservation — the storybook outlives the ecology.

## The baseline is stable on purpose

An earlier version of this README called it a failure that `absent` and `gardener` came out identical — that the world not needing the player meant tending had no payoff.

That was wrong, and the reason is a scaling argument. At ten regions and a thousand Kith, a world that decays without attention does not produce diligent players. It produces players who triage: deliberately let eight regions die so the remaining two are manageable. Mandatory global upkeep is how you get a game where the optimal move is arson.

So the world holds itself together, and the player's relationship to it is **local and intentional**. You go somewhere because you want something out of it. The payoff for intervening is not that the world needed you — it is `bind_threshold`:

> **You can only learn a myth's verses where people still tell it.**

A deep-rooted myth clears that line on its own, so you can bind it whenever. A shallow-rooted one fades below it and the only way to get that Kith is to deliberately revive a dying story — accepting the Bleed pressure that pushing creates. The fading myth is the prize, not just the tragedy. That is what `collector` tests, and it binds everything while leaving the valley intact.

## Findings

### 1. The world needs homeostasis or it eats itself

First run, `absent` sterilised all three regions. Flat decay kills obscure myths first, which *raises* the dominant myth's share, which trips Bleed. Every region monocultured and died with no player involvement.

Fix: regions tell their own stories. Each gets a per-tick budget split between what is already popular and a floor under its native traditions, scaled by surviving population — a dying place tells fewer stories.

### 2. Only the player should be able to cause Bleed

Native telling alone was not enough; "retell what's popular" is rich-get-richer and still monocultured. The fix fell out of the fiction: **an over-told story gets boring.** Native retelling is damped by `(1 - share)`, so a saturated myth earns less attention from people who already know it.

The player's telling is **not** damped. Populations self-regulate, and the Messenger is the only force that can shove a region past its natural ceiling. That is thematically exact and nobody designed it in — it fell out of making the numbers behave.

### 3. An even tradition floor erases obscurity

With the floor split evenly across a region's native myths, every region converged on a perfectly stable duopoly at 50/50 and every imported myth died. Nothing was ever faint, so nothing ever needed rescuing, and binding was free.

Fix: `rootedness` per myth, weighting its share of the tradition floor. Deep-rooted stories hold themselves up; shallow ones fade without deliberate help. This is what creates the scarcity the whole binding mechanic depends on.

### 4. Refugee contagion runs on a very long fuse

In `monoculture`, Green Hollow craters and its survivors scatter around t27. Greenmother rides out with them into Stonereach, climbs for over a hundred ticks, crosses the threshold near t150, and Stonereach is cratering by t180.

**Roughly three years of in-world time between the player's mistake and the second valley starting to burn**, in a region they never touched. They will probably never connect the two events.

And it is not deterministic. Fenmouth took refugees too and stayed healthy, because it had enough mythic diversity to absorb them; Stonereach was small and thin and got taken over. **Diverse regions resist contagion, thin ones do not.** Also emergent.

## Robustness: how fragile is this?

`sweep.py` samples the eight constants that shape Bleed and scores each draw on three requirements — stable unattended, punishes monoculture, middle ≥ 15 ticks.

```
PARAMETER SWEEP - 600 draws, 204 viable (34%)
  stable unattended         282/600  ( 47%)
  punishes monoculture      594/600  ( 99%)
  middle >= 15 ticks        376/600  ( 63%)
  middle length           min 5  median 17  max 123
```

**34% of the sampled space works.** That is a broad, forgiving basin rather than a knife edge, which is the answer Gate 1 needed. No single constant came back tight enough to be individually load-bearing; the binding constraint is their interaction.

Two things the sweep changed:

- **Stability is the hard requirement, not the telegraphing window.** Only 47% of draws leave the world intact unattended, while 99% punish monoculture. Making bad play hurt is nearly free; making the world safe to ignore is the real design work.
- **`bleed_threshold` was marginal.** The hand-tuned 0.55 sat on the very bottom edge of the viable range (0.52–0.75, median 0.65). It is now 0.65, which moved bleed onset from t16 to t25 and cut monoculture's death toll by half while still sterilising the region.

## Known gaps

- **One player verb.** The sim has only `tell`. Suppression, syncretism, Rumors and cosmology translation are all unmodelled, so "Gate 1 passes" means the belief-and-Bleed loop passes, not the design.
- **Tick scale is a guess.** "One tick ≈ one week" is a label, not a pacing model. The 24-tick middle is meaningful as a ratio, not as six real months.
- **Three regions, ten myths.** Behaviour at ten regions and hundreds of myths is untested, and the zero-sum share model may behave differently when a region holds thirty stories instead of four.

## Next

Gate 2 is a Godot grey-box: one valley, coloured cubes, this simulation driving terrain swaps. The question there is no longer whether the system has dynamics — it does — but whether *watching* it produces a feeling.

## Layout

```
sim/
  run.py              CLI, report, plots
  sweep.py            parameter robustness
  kith/
    model.py          dataclasses, JSON loading, schema guard
    engine.py         the tick loop
    scenarios.py      the five player policies
  data/
    myths.json        ten myths, their domains, homes and rootedness
    regions.json      one valley, three settlements, two cosmologies
    tuning.json       every constant
  out/                generated plots
```
