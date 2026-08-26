"""Turn a focus tree into a test checklist a human can actually work through."""

from __future__ import annotations

from .model import Focus, FocusData, FocusTree


def _transitive_dependents(focuses: list[Focus]) -> dict[str, set[str]]:
    """For each focus, the focuses that can only be reached through it."""
    direct: dict[str, set[str]] = {}
    for focus in focuses:
        for prereq_id in focus.all_prerequisites:
            direct.setdefault(prereq_id, set()).add(focus.id)

    dependents: dict[str, set[str]] = {}
    for focus in focuses:
        seen: set[str] = set()
        queue = list(direct.get(focus.id, ()))
        while queue:
            current = queue.pop()
            if current in seen:
                continue
            seen.add(current)
            queue.extend(direct.get(current, ()))
        dependents[focus.id] = seen
    return dependents


def _exclusive_groups(focuses: list[Focus]) -> list[list[str]]:
    """Connected components of the mutual-exclusivity graph: one decision each."""
    by_id = {focus.id: focus for focus in focuses}
    neighbours: dict[str, set[str]] = {focus.id: set() for focus in focuses}

    for focus in focuses:
        for other_id in focus.mutually_exclusive:
            if other_id in by_id:
                neighbours[focus.id].add(other_id)
                neighbours[other_id].add(focus.id)

    groups: list[list[str]] = []
    seen: set[str] = set()
    for focus in focuses:
        if focus.id in seen or not neighbours[focus.id]:
            continue
        component: set[str] = set()
        queue = [focus.id]
        while queue:
            current = queue.pop()
            if current in component:
                continue
            component.add(current)
            queue.extend(neighbours[current] - component)
        seen |= component
        groups.append(sorted(component))

    return groups


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or singular + "s")


def build_checklist(tree: FocusTree) -> list[str]:
    lines: list[str] = []
    focuses = tree.focuses
    label = f"{tree.id}" + (f" ({tree.country_tag})" if tree.country_tag else "")

    lines.append(f"# Test checklist: {label}")
    lines.append("")
    lines.append(f"Source: `{tree.path.name}` — {len(focuses)} focuses")
    lines.append("")
    lines.append("## Before you start")
    lines.append("")
    lines.append("- [ ] Record game version and checksum")
    lines.append("- [ ] Record DLC combination; repeat the pass with the gating DLC disabled")
    lines.append("- [ ] Vanilla, no mods enabled")
    lines.append("")

    groups = _exclusive_groups(focuses)
    dependents = _transitive_dependents(focuses)

    if groups:
        lines.append("## Branch decisions (mutual exclusivity)")
        lines.append("")
        lines.append(
            f"{len(groups)} exclusive decision {_plural(len(groups), 'point')}. Each alternative needs "
            "its own playthrough, and taking one must lock the others."
        )
        lines.append("")
        for number, group in enumerate(groups, start=1):
            lines.append(f"### Decision {number}: {' | '.join(group)}")
            lines.append("")
            for focus_id in group:
                blocked = [other for other in group if other != focus_id]
                gated = len(dependents.get(focus_id, ()))
                lines.append(f"- [ ] Take `{focus_id}`")
                lines.append(
                    f"  - [ ] Verify {', '.join(f'`{b}`' for b in blocked)} "
                    f"{_plural(len(blocked), 'becomes', 'become')} unavailable"
                )
                if gated:
                    lines.append(
                        f"  - [ ] Verify the {gated} {_plural(gated, 'focus', 'focuses')} gated behind it "
                        "become available in order"
                    )
                lines.append("  - [ ] Save, reload, and confirm the lock survives the round trip")
            lines.append("")

    # De-duplicate by id: a duplicated focus id is reported by the checks, and
    # repeating it here would just look like a checklist bug.
    entry_points = list({focus.id: focus for focus in focuses if not focus.prerequisite_groups}.values())
    if entry_points:
        lines.append("## Entry points")
        lines.append("")
        lines.append("Focuses with no prerequisite — all should be selectable at game start.")
        lines.append("")
        for focus in entry_points:
            lines.append(f"- [ ] `{focus.id}` selectable on day one")
        lines.append("")

    gated = [focus for focus in focuses if focus.has_available]
    if gated:
        lines.append("## Conditional availability")
        lines.append("")
        lines.append(f"{len(gated)} focus(es) carry an `available` block. Test each gate open and closed.")
        lines.append("")
        for focus in gated:
            bypass_note = "" if focus.has_bypass else "  ← no bypass block"
            lines.append(f"- [ ] `{focus.id}`: unavailable while the condition fails, available once met{bypass_note}")
        lines.append("")

    bypassable = [focus for focus in focuses if focus.has_bypass]
    if bypassable:
        lines.append("## Bypass conditions")
        lines.append("")
        lines.append("Satisfy each condition externally and confirm the focus actually bypasses.")
        lines.append("")
        for focus in bypassable:
            lines.append(f"- [ ] `{focus.id}` bypasses when its condition is already true")
        lines.append("")

    lines.append("## Whole-tree passes")
    lines.append("")
    lines.append("- [ ] Every focus has an icon that resolves (no missing GFX)")
    lines.append("- [ ] Every focus name and description has localisation (no raw keys shown)")
    lines.append("- [ ] Save mid-tree, reload, confirm progress and queue are intact")
    lines.append("- [ ] AI plays the tree unassisted and reaches a sensible end state")
    lines.append("- [ ] Achievements and Ironman remain valid throughout")
    lines.append("- [ ] Late-game performance: no measurable slowdown from this tree's ongoing effects")
    lines.append("")

    return lines


def find_tree(data: FocusData, wanted: str) -> FocusTree | None:
    for tree in data.trees:
        if tree.id == wanted or tree.country_tag == wanted:
            return tree
    return None
