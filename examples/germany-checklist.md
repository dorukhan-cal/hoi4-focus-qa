# Test checklist: german_focus (GER)

Source: `germany.txt` — 438 focuses

## Before you start

- [ ] Record game version and checksum
- [ ] Record DLC combination; repeat the pass with the gating DLC disabled
- [ ] Vanilla, no mods enabled

## Branch decisions (mutual exclusivity)

44 exclusive decision points. Each alternative needs its own playthrough, and taking one must lock the others.

### Decision 1: GER_prioritize_economic_growth | GER_the_four_year_plan

- [ ] Take `GER_prioritize_economic_growth`
  - [ ] Verify `GER_the_four_year_plan` becomes unavailable
  - [ ] Verify the 21 focuses gated behind it become available in order
  - [ ] Save, reload, and confirm the lock survives the round trip
- [ ] Take `GER_the_four_year_plan`
  - [ ] Verify `GER_prioritize_economic_growth` becomes unavailable
  - [ ] Verify the 22 focuses gated behind it become available in order
  - [ ] Save, reload, and confirm the lock survives the round trip

### Decision 2: GER_adopt_new_panzer_doctrine | GER_the_prussian_legacy

- [ ] Take `GER_adopt_new_panzer_doctrine`
  - [ ] Verify `GER_the_prussian_legacy` becomes unavailable
  - [ ] Verify the 15 focuses gated behind it become available in order
  - [ ] Save, reload, and confirm the lock survives the round trip
- [ ] Take `GER_the_prussian_legacy`
  - [ ] Verify `GER_adopt_new_panzer_doctrine` becomes unavailable
  - [ ] Verify the 15 focuses gated behind it become available in order
  - [ ] Save, reload, and confirm the lock survives the round trip

### Decision 3: GER_defend_the_vaterland | GER_improve_the_logistics_system

- [ ] Take `GER_defend_the_vaterland`
  - [ ] Verify `GER_improve_the_logistics_system` becomes unavailable

---

*Excerpt. The full generated checklist for this tree runs to 1,092 lines covering all 44
exclusive decision points, 438 focuses, and the whole-tree passes. Generate it against your own
installation with:*

```bash
python3 -m hoi4qa "/path/to/Hearts of Iron IV" --checklist GER -o germany-checklist.md
```

*Only an excerpt is committed here: the full output enumerates every focus identifier in the
tree, and this repository deliberately contains no bulk game-derived data.*
