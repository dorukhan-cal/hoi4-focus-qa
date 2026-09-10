# hoi4-focus-qa

Static QA analysis and test-checklist generation for Hearts of Iron IV national focus trees.

Focus trees are defined as script in `common/national_focus/*.txt`, and a whole class of
content defects is visible in that script before anyone launches the game: a focus that
excludes another without being excluded back, a branch that can never be reached because it
requires both halves of an exclusive pair, a prerequisite pointing at an id that no longer
exists. This tool reads the script, reports those defects, and turns a tree into a checklist
a tester can actually work through.

It reads a local installation. It contains and redistributes no game data.

## Usage

```bash
python3 -m hoi4qa "/path/to/Hearts of Iron IV"
```

```bash
# What trees are in there?
python3 -m hoi4qa "/path/to/Hearts of Iron IV" --list-trees

# Full report as Markdown, including informational findings
python3 -m hoi4qa "/path/to/Hearts of Iron IV" --severity info --format md -o report.md

# Test checklist for one tree, by tree id or country tag
python3 -m hoi4qa "/path/to/Hearts of Iron IV" --checklist SOV -o soviet-checklist.md

# Check a different language: keys present in English but never translated
python3 -m hoi4qa "/path/to/Hearts of Iron IV" --language french

# Point it at a mod instead
python3 -m hoi4qa ~/Documents/Paradox\ Interactive/Hearts\ of\ Iron\ IV/mod/my_mod

# Non-zero exit when errors are present, for CI
python3 -m hoi4qa ./my_mod --fail-on-error
```

Python 3.9+, no dependencies. `pytest` only for the tests. Verified on the macOS system
Python (3.9.6).

## Checks

| Check | Severity | What it means |
| --- | --- | --- |
| `malformed-script` | error | The file only parsed after error recovery — unbalanced braces or similar. |
| `duplicate-id` | error | The same focus id is defined more than once; the later definition is ignored by the game. |
| `dangling-prerequisite` | error | A prerequisite names a focus that does not exist. |
| `dangling-mutually-exclusive` | error | An exclusivity block names a focus that does not exist. |
| `dangling-relative-position` | error | `relative_position_id` names a focus that does not exist, so layout is undefined. |
| `dangling-shared-focus` | error | A tree references a shared focus that is not defined anywhere. |
| `self-prerequisite` | error | A focus requires itself and can never be taken. |
| `self-mutually-exclusive` | error | A focus excludes itself. |
| `unreachable` | error | Compulsory prerequisites contradict each other — typically requiring both halves of an exclusive pair. |
| `prerequisite-cycle` | error | A prerequisite loop; every focus in it is unreachable. |
| `asymmetric-exclusivity` | warning | A excludes B, but B does not exclude A. Exclusivity is only enforced in the declared direction, so order of selection changes the outcome. |
| `position-collision` | warning | Two focuses occupy the same grid square of the same tree and will draw on top of each other. |
| `missing-localisation` | error | The focus has no localisation key, so the raw key is shown in game. Respects a `text` override. |
| `missing-icon` | error | `icon` names a sprite that no `.gfx` file declares, so a placeholder is shown. |
| `missing-description` | warning | The name is localised but `<key>_desc` is not, so the focus has no description text. |
| `no-completion-reward` | warning | Completing the focus has no effect. Sometimes intended, often not. |

Checks are deliberately conservative: each one reports only when the script is genuinely
inconsistent, never when it merely looks unusual.

## Results on vanilla 1.19.2

Against a clean install of **1.19.2.0 "Operation Postern"** (checksum `d245`) — 81 focus files,
67 trees, 10,888 focuses, 129,087 localisation keys and 29,432 sprite declarations, about 7
seconds:

```
7 error(s), 0 warning(s), 0 info

[malformed-script]
 ! TSR_lingguang_incident_joint_branch.txt:469  unmatched closing brace, skipped
 ! powerbalanceview.gfx:1                       block never closed, terminated at end of file
 ! WW_meshes_planes.gfx:1                       block never closed
 ! _BfB_meshes_infantry.gfx:1                   block never closed
 ! NSB_infantry.gfx:1                           block never closed
 ! flame_tanks.gfx:1                            block never closed
 ! empty.gfx:1                                  block never closed
```

**Seven shipped files are malformed.** The focus file carries one closing brace too many, at end
of file after all seven `joint_focus` blocks, so no content is lost. The six `.gfx` files have the
opposite problem — a root block that is never closed. `empty.gfx` is 112 bytes and simply stops.
The practical effect in both directions is an entry in the game's own error log rather than
missing content. Each was confirmed with an independent brace counter that shares no code with
the parser.

**No focus in the game is missing localisation or an icon.** All 10,828 icon references resolve
against 2,907 distinct declared sprites, and every focus name and description is present — in
English, and also in French, German and Polish.

Full output in [`examples/vanilla-1.19.2-report.md`](examples/vanilla-1.19.2-report.md), and an
excerpt of the generated checklist for the 438-focus German tree — 44 exclusive decision points,
1,092 lines in full — in [`examples/germany-checklist.md`](examples/germany-checklist.md).

## Checks considered and rejected

**`available` without `bypass`** was written, run, and deleted: it fired on 4,129 of 10,888
focuses. A check matching 38% of the corpus describes the house style, not a defect. The same
reasoning exempted `allow_branch` branches from `position-collision`, where sharing a grid square
is how the feature works.

## Checklist generation

`--checklist TREE` turns a tree into Markdown with checkboxes, covering:

- every mutually exclusive decision point, with the focuses gated behind each alternative
- the lock direction to verify for each branch, and a save/reload round trip on each
- entry points that must be selectable at game start
- every `available` gate to test both open and closed
- every `bypass` condition to satisfy externally and confirm
- whole-tree passes: icons resolving, localisation present, save/reload mid-tree, AI playing
  the tree unassisted, Ironman and achievement validity, late-game performance

## Limitations

- The reachability check follows only compulsory single-entry prerequisite blocks, so it under-
  reports rather than guessing. Multi-entry (OR) prerequisites are not resolved.
- Position checks skip focuses using `relative_position_id`, `offset`, or `allow_branch`, since
  all three legitimately place focuses on the same square.
- `available` and `bypass` triggers are detected but not evaluated; proving a trigger is
  unsatisfiable needs the full scripted-trigger and game-state model.
- Cross-tree effects such as `unlock_national_focus` are not followed.
- Country tags are read from the tree's `country` weight block and may be absent for trees that
  select themselves another way.

## Tests

```bash
python3 -m pytest tests/ -q
```

`tests/fixtures/` contains a synthetic tree carrying one deliberate defect per graph check, and
`tests/fixtures_content/` a second tree with its own localisation and `.gfx` files covering the
content checks and the position-check exemptions. Both are written from scratch and contain no
game content.

## Notes

Built with Claude Code. The parser is a hand-checked tokenizer and recursive descent parser for
the Clausewitz script format, kept deliberately small: blocks preserve statement order and
duplicate keys, because in this format `prerequisite` appearing three times is meaningful rather
than an error.

Parsing is lenient when loading a directory: vanilla ships files with unbalanced braces, and
aborting on them would silently drop every definition inside. The recovery is recorded and
reported as a finding instead.

Most of what the first run against real data reported was the tool's fault, not the game's.
Unhandled `joint_focus` blocks, joint-specific completion reward keys, and `allow_branch` branches
sharing grid positions by design accounted for three of four categories; the localisation check
then reported six missing keys that all turned out to use a `text` override. Each was verified
against the game files and fixed before anything was called a defect.
