"""Static checks over loaded focus trees.

Every check is conservative: it only reports something when the data itself is
inconsistent, not when it merely looks unusual. A check that cries wolf is worse
than no check, because nobody reads the second report.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Focus, FocusData

ERROR = "error"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclass
class Finding:
    severity: str
    category: str
    focus_id: str
    tree_id: str
    location: str
    message: str

    def sort_key(self) -> tuple:
        return (_SEVERITY_ORDER.get(self.severity, 9), self.category, self.tree_id, self.focus_id)


def _index(data: FocusData) -> dict[str, Focus]:
    """First definition wins, matching how the game loads duplicate ids."""
    index: dict[str, Focus] = {}
    for focus in data.all_focuses:
        index.setdefault(focus.id, focus)
    return index


def check_duplicate_ids(data: FocusData) -> list[Finding]:
    findings = []
    for focus_id, focuses in data.by_id().items():
        if len(focuses) > 1:
            where = ", ".join(f.location for f in focuses)
            findings.append(
                Finding(
                    ERROR,
                    "duplicate-id",
                    focus_id,
                    focuses[0].tree_id,
                    focuses[0].location,
                    f"focus id defined {len(focuses)} times ({where})",
                )
            )
    return findings


def check_dangling_references(data: FocusData) -> list[Finding]:
    known = _index(data)
    findings = []

    for focus in data.all_focuses:
        for group in focus.prerequisite_groups:
            for prereq_id in group:
                if prereq_id not in known:
                    findings.append(
                        Finding(
                            ERROR,
                            "dangling-prerequisite",
                            focus.id,
                            focus.tree_id,
                            focus.location,
                            f"prerequisite references unknown focus '{prereq_id}'",
                        )
                    )

        for exclusive_id in focus.mutually_exclusive:
            if exclusive_id not in known:
                findings.append(
                    Finding(
                        ERROR,
                        "dangling-mutually-exclusive",
                        focus.id,
                        focus.tree_id,
                        focus.location,
                        f"mutually_exclusive references unknown focus '{exclusive_id}'",
                    )
                )

        if focus.relative_position_id and focus.relative_position_id not in known:
            findings.append(
                Finding(
                    ERROR,
                    "dangling-relative-position",
                    focus.id,
                    focus.tree_id,
                    focus.location,
                    f"relative_position_id references unknown focus '{focus.relative_position_id}'",
                )
            )

    for tree in data.trees:
        for ref in tree.shared_focus_refs:
            if ref not in known:
                findings.append(
                    Finding(
                        ERROR,
                        "dangling-shared-focus",
                        ref,
                        tree.id,
                        f"{tree.path.name}:{tree.line}",
                        f"tree references unknown shared focus '{ref}'",
                    )
                )

    return findings


def check_self_references(data: FocusData) -> list[Finding]:
    findings = []
    for focus in data.all_focuses:
        if focus.id in focus.all_prerequisites:
            findings.append(
                Finding(
                    ERROR,
                    "self-prerequisite",
                    focus.id,
                    focus.tree_id,
                    focus.location,
                    "focus lists itself as a prerequisite, so it can never be taken",
                )
            )
        if focus.id in focus.mutually_exclusive:
            findings.append(
                Finding(
                    ERROR,
                    "self-mutually-exclusive",
                    focus.id,
                    focus.tree_id,
                    focus.location,
                    "focus lists itself as mutually exclusive with itself",
                )
            )
    return findings


def check_asymmetric_exclusivity(data: FocusData) -> list[Finding]:
    """A says it excludes B, but B never mentions A.

    The game only blocks the direction that is declared, so this asymmetry means
    a player who takes B first can usually still take A.
    """
    known = _index(data)
    findings = []

    for focus in data.all_focuses:
        for other_id in focus.mutually_exclusive:
            other = known.get(other_id)
            if other is None:
                continue  # reported by the dangling-reference check
            if focus.id not in other.mutually_exclusive:
                findings.append(
                    Finding(
                        WARNING,
                        "asymmetric-exclusivity",
                        focus.id,
                        focus.tree_id,
                        focus.location,
                        f"excludes '{other_id}', but '{other_id}' does not exclude it back "
                        f"({other.location}) -- the block only applies in one direction",
                    )
                )
    return findings


def _required_ancestors(focus: Focus, known: dict[str, Focus]) -> set[str]:
    """Focuses that must be taken before `focus`, following only forced steps.

    A prerequisite block with one entry is compulsory. A block with several
    entries is a choice, so nothing in it is guaranteed and we do not follow it.
    """
    required: set[str] = set()
    queue = [focus]
    seen = {focus.id}

    while queue:
        current = queue.pop()
        for group in current.prerequisite_groups:
            if len(group) != 1:
                continue
            prereq_id = group[0]
            if prereq_id in seen:
                continue
            seen.add(prereq_id)
            required.add(prereq_id)
            prereq = known.get(prereq_id)
            if prereq is not None:
                queue.append(prereq)

    return required


def check_unreachable(data: FocusData) -> list[Finding]:
    """Focuses whose compulsory prerequisites contradict each other."""
    known = _index(data)
    findings = []

    for focus in data.all_focuses:
        required = _required_ancestors(focus, known)

        blocked_by = next(
            (
                ancestor_id
                for ancestor_id in sorted(required)
                if ancestor_id in focus.mutually_exclusive
                or focus.id in known.get(ancestor_id, focus).mutually_exclusive
            ),
            None,
        )
        if blocked_by is not None:
            findings.append(
                Finding(
                    ERROR,
                    "unreachable",
                    focus.id,
                    focus.tree_id,
                    focus.location,
                    f"requires '{blocked_by}' but is mutually exclusive with it, so it can never be taken",
                )
            )
            continue

        for ancestor_id in sorted(required):
            ancestor = known.get(ancestor_id)
            if ancestor is None:
                continue
            clash = next((other for other in sorted(ancestor.mutually_exclusive) if other in required), None)
            if clash is not None:
                findings.append(
                    Finding(
                        ERROR,
                        "unreachable",
                        focus.id,
                        focus.tree_id,
                        focus.location,
                        f"requires both '{ancestor_id}' and '{clash}', which are mutually exclusive",
                    )
                )
                break

    return findings


def check_cycles(data: FocusData) -> list[Finding]:
    """Prerequisite loops. Anything inside one is unreachable."""
    known = _index(data)
    colour: dict[str, int] = {}  # 0 = visiting, 1 = done
    cycles: list[list[str]] = []

    def visit(focus_id: str, stack: list[str]) -> None:
        if colour.get(focus_id) == 1:
            return
        if colour.get(focus_id) == 0:
            cycles.append(stack[stack.index(focus_id):] + [focus_id])
            return

        colour[focus_id] = 0
        stack.append(focus_id)
        focus = known.get(focus_id)
        if focus is not None:
            for prereq_id in sorted(focus.all_prerequisites):
                if prereq_id in known:
                    visit(prereq_id, stack)
        stack.pop()
        colour[focus_id] = 1

    for focus in data.all_focuses:
        visit(focus.id, [])

    findings = []
    reported: set[frozenset[str]] = set()
    for cycle in cycles:
        key = frozenset(cycle)
        if key in reported:
            continue
        reported.add(key)
        focus = known[cycle[0]]
        findings.append(
            Finding(
                ERROR,
                "prerequisite-cycle",
                focus.id,
                focus.tree_id,
                focus.location,
                "prerequisite loop: " + " -> ".join(cycle),
            )
        )
    return findings


def check_position_collisions(data: FocusData) -> list[Finding]:
    """Two focuses drawn on the same square of the same tree.

    Only focuses whose position is fixed and unconditional are compared. Three
    kinds are skipped because sharing a square is legitimate for them:
    `relative_position_id` (laid out at runtime), `offset` (moved per country),
    and `allow_branch` (mutually visible branches, only one shown at a time).
    """
    findings = []
    for tree in data.trees:
        seen: dict[tuple[str, str], Focus] = {}
        for focus in tree.focuses:
            if focus.relative_position_id or focus.x is None or focus.y is None:
                continue
            if focus.has_allow_branch or focus.has_offset:
                continue
            key = (focus.x, focus.y)
            first = seen.get(key)
            if first is not None:
                findings.append(
                    Finding(
                        WARNING,
                        "position-collision",
                        focus.id,
                        tree.id,
                        focus.location,
                        f"shares grid position x={focus.x} y={focus.y} with '{first.id}' ({first.location})",
                    )
                )
            else:
                seen[key] = focus
    return findings


def check_missing_blocks(data: FocusData) -> list[Finding]:
    """Content-completeness signals worth eyeballing, not defects in themselves.

    A companion check flagging `available` without `bypass` was removed: on
    vanilla 1.19.2 it fired on 4129 of 10888 focuses. A check that matches 38% of
    the corpus describes the house style, not a defect.
    """
    return [
        Finding(
            WARNING,
            "no-completion-reward",
            focus.id,
            focus.tree_id,
            focus.location,
            "focus has no completion_reward, so completing it does nothing",
        )
        for focus in data.all_focuses
        if not focus.has_completion_reward
    ]


def check_malformed_files(data: FocusData) -> list[Finding]:
    """Files that only parsed after error recovery: the script itself is broken."""
    return [
        Finding(
            ERROR,
            "malformed-script",
            "(file)",
            "-",
            f"{name}:{message.split(':')[0].replace('line ', '')}",
            f"{name} contains malformed script -- {message}",
        )
        for name, message in data.malformed
    ]


def check_localisation(data: FocusData) -> list[Finding]:
    """Focuses whose displayed name or description has no localisation key.

    The key is not always the focus id: a `text` field overrides it, usually to
    avoid colliding with an identically named idea or doctrine. Checking the id
    blindly reports every one of those as missing.
    """
    if not data.has_localisation:
        return []

    findings = []
    for focus in data.all_focuses:
        key = focus.loc_key
        if key not in data.loc_keys:
            findings.append(
                Finding(
                    ERROR,
                    "missing-localisation",
                    focus.id,
                    focus.tree_id,
                    focus.location,
                    f"no {data.loc_language} key '{key}' -- the raw key will be shown in game",
                )
            )
        elif f"{key}_desc" not in data.loc_keys:
            findings.append(
                Finding(
                    WARNING,
                    "missing-description",
                    focus.id,
                    focus.tree_id,
                    focus.location,
                    f"no {data.loc_language} key '{key}_desc' -- the focus has no description text",
                )
            )
    return findings


def check_icons(data: FocusData) -> list[Finding]:
    """Focuses whose icon does not resolve to a declared sprite."""
    if not data.has_sprites:
        return []

    return [
        Finding(
            ERROR,
            "missing-icon",
            focus.id,
            focus.tree_id,
            focus.location,
            f"icon '{focus.icon}' is not declared in any .gfx file -- a placeholder will be shown",
        )
        for focus in data.all_focuses
        if focus.icon and focus.icon not in data.sprite_names
    ]


ALL_CHECKS = (
    check_malformed_files,
    check_localisation,
    check_icons,
    check_duplicate_ids,
    check_dangling_references,
    check_self_references,
    check_asymmetric_exclusivity,
    check_unreachable,
    check_cycles,
    check_position_collisions,
    check_missing_blocks,
)


def run_all(data: FocusData) -> list[Finding]:
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(data))
    findings.sort(key=Finding.sort_key)
    return findings
