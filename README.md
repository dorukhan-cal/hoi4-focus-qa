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
| `no-completion-reward` | warning | Completing the focus has no effect. Sometimes intended, often not. |

Checks are deliberately conservative: each one reports only when the script is genuinely
inconsistent, never when it merely looks unusual. A check that cries wolf gets ignored, and an
ignored check is worse than no check.

## Results on vanilla 1.19.2

Against a clean install of **1.19.2.0 "Operation Postern"** (checksum `d245`) — 81 files,
67 trees, 10,888 focuses, about 4 seconds:

```
1 error(s), 0 warning(s), 0 info

[malformed-script]
 ! TSR_lingguang_incident_joint_branch.txt:469: unmatched closing brace, skipped
```

That file carries one closing brace too many. It sits at end of file, after all seven
`joint_focus` blocks, so no content is lost — the practical effect is an entry in the game's own
error log rather than missing content. It was confirmed with an independent brace counter that
does not share code with the parser, because a parser reporting a parse problem is not evidence.

Full output in [`examples/vanilla-1.19.2-report.md`](examples/vanilla-1.19.2-report.md), and an
excerpt of the generated checklist for the 438-focus German tree — 44 exclusive decision points,
1,092 lines in full — in [`examples/germany-checklist.md`](examples/germany-checklist.md).

## Checks considered and rejected

**`available` without `bypass`.** The idea was to flag focuses that stay available after their
purpose is already achieved. On vanilla it fired on **4,129 of 10,888 focuses**, or 38% of the
corpus. A check matching more than a third of everything describes the house style, not a defect,
so it was removed rather than shipped at low severity. The same reasoning removed a
`position-collision` finding on `allow_branch` branches, where sharing a grid square is how the
feature works.

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

`tests/fixtures/` contains a synthetic tree carrying one deliberate defect per check. It is
written from scratch and contains no game content.

## Notes

Built with Claude Code. The parser is a hand-checked tokenizer and recursive descent parser for
the Clausewitz script format, kept deliberately small: blocks preserve statement order and
duplicate keys, because in this format `prerequisite` appearing three times is meaningful rather
than an error.

Parsing is lenient by default when loading a directory. The game tolerates a stray closing brace
at file scope, and vanilla ships one, so aborting on it would silently drop seven joint focuses
and produce a cascade of phantom "unknown focus" errors elsewhere. The recovery is recorded and
reported as a finding instead — under-reporting coverage while appearing to succeed is the worst
failure mode available to a QA tool.

Three of the four categories in the first run against real data turned out to be the tool's bugs
rather than the game's: unhandled `joint_focus` blocks, joint-specific completion reward keys, and
`allow_branch` branches sharing grid positions by design. They were verified against the game
files and fixed before anything was reported as a defect.
