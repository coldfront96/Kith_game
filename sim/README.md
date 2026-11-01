# Belief simulation — Gate 1

A headless simulation of the belief ledger, Bleed, binding, refugee contagion and rival Messengers described in [DESIGN.md](../DESIGN.md). No rendering, no engine, no art.

It exists to answer questions before a line of Godot gets written. If belief flattens to mush, or Bleed goes fine-to-crater in three ticks, or rival Messengers turn out to be scenery, no amount of art fixes it. Find out in a weekend.

## Run it

```bash
cd sim
python3 run.py                 # all scenarios, report + plots in out/
python3 run.py --no-plot       # report only
python3 run.py collector       # one scenario with its full event log
python3 sweep.py -n 400        # how fragile is any of this?
```

Only needs `matplotlib`, and only for the plots.

## Where the knobs are

**All of them are in `data/tuning.json`.** Nothing is hardcoded. Tuning means editing JSON and re-running, never touching Python.

The world is data too — `myths.json`, `regions.json`, `messengers.json`. DESIGN.md flags save migration as the day-one engineering trap, so the schema has to outlive the prototype; Godot reads these same files later. Every file carries `schema_version` and loading refuses a version it does not speak. That guard has already caught one mismatch during development, which is the whole argument for having it.

**The current values are the medians of the viable region found by `sweep.py`, not hand-picked.** Re-run the sweep after any structural change.

## The scenarios

| Scenario | Player policy | Tests |
| --- | --- | --- |
| `absent` | does nothing | Is the world stable when left alone? |
| `monoculture` | spams one story in one region | The Bleed cliff |
| `gardener` | props up whichever myth is closest to forgotten | Is balancing playable? |
| `opportunist` | feeds the strongest myth, backs off when the land turns | Is the telegraphed middle reactable? |
| `collector` | travels, pushes whichever unbound myth is closest to collectable | Does targeted intervention beat idling? |
| `warlord` | forces its own stories into wherever it is weakest | Does strength-from-belief *pressure* the player into Bleed, or only tempt them? |

## Result: pass

```
scenario        bound  myths      pop  onset  middle  sterile  xborder
absent           6/10    8/10    6,900      -       -        0        0
monoculture      6/10    5/10    5,299     21      29        1       10
gardener         8/10    8/10    6,900      -       -        0        0
opportunist      8/10    8/10    6,900     21       -        0        0
collector       10/10    9/10    6,900      -       -        0        0
warlord          6/10    5/10    5,298     22      30        1       10

                contests  win rate
warlord              369       66%
collector            125       95%
gardener               5       40%
```

- **The world holds itself together.** `absent` ends with full population, no Bleed, no sterile regions.
- **The middle is 29 ticks** between the land visibly turning and the point of no return. `opportunist` walks up to Bleed at t21, notices, backs off, recovers with no deaths.
- **Deliberate collecting beats idling 10 to 6.** Four myths exist that you only ever get by reviving them on purpose.
- **Rivals are competitive.** 66% win rate for an aggressive player — you mostly win, you sometimes lose.

### The answer to the combat-pressure question

**`warlord` and `monoculture` produce almost identical devastation** — same sterile region, same death toll, same 10 cross-border carries. Playing the combat incentive straight, with no restraint, wrecks a valley exactly as thoroughly as mindless spam does.

So strength-from-belief does not merely tempt the player toward Bleed. It **pressures** them. The optimal fighting strategy and the ecological warning point in opposite directions, hard, and the only thing standing between a competitive player and a dead valley is 29 ticks of warning and their own restraint.

That is the design's thesis working as a moment-to-moment decision rather than a lecture. It is also a real risk: an unreflective player optimising for combat will ruin places without ever deciding to.

## Rival Messengers

Maintainers walk a circuit, prop up whichever story is closest to forgotten where they stand, and move toward whichever reachable region is furthest out of balance. They are the homeostasis with a face — and they answer the ten-regions problem, because the player does not have to tend the world when *they* tend the world.

**Contests** fire wherever a maintainer and the player are standing together. One shared slider, not two health bars, opening at the local belief ratio — so a contest on someone's home turf starts with the crowd already against you. The outcome is written straight into the region's ledger. A myth the loser carries never drops below `bound_floor`, so a losing streak cannot spiral.

## Findings

### 1. The world needs homeostasis or it eats itself

`absent` originally sterilised all three regions. Flat decay kills obscure myths first, which *raises* the dominant myth's share, which trips Bleed. Fix: regions tell their own stories, scaled by surviving population.

### 2. Only the player should be able to cause Bleed

"Retell what's popular" is rich-get-richer and still monocultured. Fix came from the fiction: **an over-told story gets boring.** Native retelling is damped by `(1 - share)`. The player's telling is not damped, so populations self-regulate and the Messenger is the only force that can push a region past its ceiling.

### 3. An even tradition floor erases obscurity

With the floor split evenly, every region converged on a stable 50/50 duopoly of its natives. Nothing was ever faint, so nothing needed rescuing and binding was free. Fix: `rootedness` per myth weights its share of the floor.

### 4. Refugee contagion runs on a very long fuse

Green Hollow craters, survivors scatter, their myth rides out with them and starts killing a second region a hundred-plus ticks later — in a place the player never touched. Not deterministic: a region with enough mythic diversity absorbs the refugees, a thin one gets taken over.

### 5. Maintainers alone cannot hold the world

Turning native telling off entirely and relying on Messengers only works at near-maximum vigor, and only because there happen to be three of them for three regions. A region nobody is standing in decays fast. **Homeostasis has to be two-layered** — villages tell their own stories whether or not anyone visits, and Messengers top up what is fading. Neither alone is enough.

### 6. Static rivals lose every fight, forever

The first version gave maintainers a fixed loadout. The player binds permanently and grows without bound, so their standing climbed all game while the rivals' stayed flat — **the player went 356 to 1**, and the sweep found rivals competitive in only 3% of the entire parameter space. No constant fixes that.

Fix: rivals bind by the same rule the player does, capped by `rival_repertoire_cap`. Viability went **2% → 21%** and rivals-competitive went **3% → 66%**.

A related bug found on the way: standing originally counted *every* myth you had bound, including ones your opponent also carried, so a generalist got credit for their rival's own stories. Contests now turn on exclusive holdings only. You do not argue about what you agree on.

## Robustness

`sweep.py` samples eleven constants and scores each draw on five requirements: stable unattended, punishes monoculture, middle ≥ 15 ticks, rivals competitive, collecting beats idling.

```
PARAMETER SWEEP - 400 draws, 21% viable
  stable unattended         83%
  punishes monoculture      49%
  middle >= 15 ticks        41%
  rivals competitive        66%
  collecting beats idling   53%
```

No single constant came back tight enough to be individually load-bearing — every viable range spans most of what was sampled. **Viability lives in the combination, not in any one number**, which is why hand-tuning kept producing a system that worked in one respect and broke in another.

Adding Messengers invalidated the previous tuning completely. That is worth remembering: this system is not separable, and any structural change means re-sweeping rather than nudging.

## Known gaps

- **Combat is abstracted to a single standing comparison.** The verse-level design — verses as moves, invoking cosmological frames mid-contest, calling out a Rumor's false origin — is not modelled at all. The sim only answers whether the *economy* around contests works.
- **Two player verbs.** `tell` and travel. Suppression, syncretism, Rumors and cosmology translation are unmodelled.
- **Tick scale is a guess.** "One tick ≈ one week" is a label, not a pacing model.
- **Three regions, ten myths, three rivals.** Behaviour at ten regions and hundreds of myths is untested, and zero-sum share may behave very differently when a region holds thirty stories instead of four.

## Next

Gate 2 is a Godot grey-box: one valley, coloured cubes, this simulation driving terrain swaps. The question there is no longer whether the system has dynamics — it does — but whether *watching* it produces a feeling.

## Layout

```
sim/
  run.py              CLI, report, plots
  sweep.py            parameter robustness over eleven constants
  kith/
    model.py          dataclasses, JSON loading, schema guard
    engine.py         the tick loop
    messengers.py     rival Messengers, circuits, contests
    scenarios.py      the six player policies
  data/
    myths.json        ten myths with domains, homes, rootedness
    regions.json      one valley, three settlements, two cosmologies
    messengers.json   three maintainers
    tuning.json       every constant
  out/                generated plots
```
