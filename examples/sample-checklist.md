# Test checklist: testland_focus (TST)

Source: `testland.txt` — 11 focuses

## Before you start

- [ ] Record game version and checksum
- [ ] Record DLC combination; repeat the pass with the gating DLC disabled
- [ ] Vanilla, no mods enabled

## Branch decisions (mutual exclusivity)

1 exclusive decision point. Each alternative needs its own playthrough, and taking one must lock the others.

### Decision 1: TST_land_doctrine | TST_naval_doctrine

- [ ] Take `TST_land_doctrine`
  - [ ] Verify `TST_naval_doctrine` becomes unavailable
  - [ ] Verify the 1 focus gated behind it become available in order
  - [ ] Save, reload, and confirm the lock survives the round trip
- [ ] Take `TST_naval_doctrine`
  - [ ] Verify `TST_land_doctrine` becomes unavailable
  - [ ] Verify the 1 focus gated behind it become available in order
  - [ ] Save, reload, and confirm the lock survives the round trip

## Entry points

Focuses with no prerequisite — all should be selectable at game start.

- [ ] `TST_rearmament` selectable on day one

## Conditional availability

1 focus(es) carry an `available` block. Test each gate open and closed.

- [ ] `TST_total_mobilisation`: unavailable while the condition fails, available once met  ← no bypass block

## Whole-tree passes

- [ ] Every focus has an icon that resolves (no missing GFX)
- [ ] Every focus name and description has localisation (no raw keys shown)
- [ ] Save mid-tree, reload, confirm progress and queue are intact
- [ ] AI plays the tree unassisted and reaches a sensible end state
- [ ] Achievements and Ironman remain valid throughout
- [ ] Late-game performance: no measurable slowdown from this tree's ongoing effects
