"""Focus-tree model extracted from parsed Clausewitz blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .clausewitz import Block, ParseError, parse_file


@dataclass
class Focus:
    id: str
    tree_id: str
    path: Path
    line: int
    # Each prerequisite block is an OR group; multiple blocks are ANDed together.
    prerequisite_groups: list[list[str]] = field(default_factory=list)
    mutually_exclusive: list[str] = field(default_factory=list)
    x: str | None = None
    y: str | None = None
    relative_position_id: str | None = None
    cost: str | None = None
    icon: str | None = None
    has_available: bool = False
    has_bypass: bool = False
    has_completion_reward: bool = False
    has_allow_branch: bool = False
    # `offset` blocks move a focus per country, so its declared x/y is only one
    # of several positions it can occupy.
    has_offset: bool = False
    is_shared: bool = False
    is_joint: bool = False

    @property
    def all_prerequisites(self) -> set[str]:
        return {focus_id for group in self.prerequisite_groups for focus_id in group}

    @property
    def location(self) -> str:
        return f"{self.path.name}:{self.line}"


@dataclass
class FocusTree:
    id: str
    path: Path
    line: int
    focuses: list[Focus] = field(default_factory=list)
    shared_focus_refs: list[str] = field(default_factory=list)
    is_default: bool = False
    country_tag: str | None = None


@dataclass
class FocusData:
    """Everything loaded from a game or mod directory."""

    trees: list[FocusTree] = field(default_factory=list)
    shared_focuses: list[Focus] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    # (file name, description) for files that parsed only after recovery.
    malformed: list[tuple[str, str]] = field(default_factory=list)
    files_read: int = 0

    @property
    def all_focuses(self) -> list[Focus]:
        return [f for tree in self.trees for f in tree.focuses] + self.shared_focuses

    def by_id(self) -> dict[str, list[Focus]]:
        index: dict[str, list[Focus]] = {}
        for focus in self.all_focuses:
            index.setdefault(focus.id, []).append(focus)
        return index


def _extract_focus(
    block: Block,
    tree_id: str,
    path: Path,
    is_shared: bool = False,
    is_joint: bool = False,
) -> Focus | None:
    focus_id = block.get_scalar("id")
    if not focus_id:
        return None

    focus = Focus(
        id=focus_id,
        tree_id=tree_id,
        path=path,
        line=block.line,
        x=block.get_scalar("x"),
        y=block.get_scalar("y"),
        relative_position_id=block.get_scalar("relative_position_id"),
        cost=block.get_scalar("cost"),
        icon=block.get_scalar("icon"),
        has_available=block.has("available"),
        has_bypass=block.has("bypass"),
        # Joint focuses reward the originating and participating countries
        # separately, so they carry neither plain `completion_reward`.
        has_completion_reward=(
            block.has("completion_reward")
            or block.has("completion_reward_joint_originator")
            or block.has("completion_reward_joint_member")
        ),
        has_allow_branch=block.has("allow_branch"),
        has_offset=block.has("offset"),
        is_shared=is_shared,
        is_joint=is_joint,
    )

    for prereq in block.get_all("prerequisite"):
        if isinstance(prereq, Block):
            group = [value for value in prereq.get_all("focus") if isinstance(value, str)]
            if group:
                focus.prerequisite_groups.append(group)

    for exclusive in block.get_all("mutually_exclusive"):
        if isinstance(exclusive, Block):
            focus.mutually_exclusive.extend(
                value for value in exclusive.get_all("focus") if isinstance(value, str)
            )

    return focus


def _tag_from_country_block(tree_block: Block) -> str | None:
    """Best-effort country tag for a tree, read from its `country` weight block."""
    country = tree_block.get_block("country")
    if country is None:
        return None
    for modifier in country.get_all("modifier"):
        if isinstance(modifier, Block):
            tag = modifier.get_scalar("tag")
            if tag:
                return tag
    return None


def load_directory(root: Path) -> FocusData:
    """Load every focus tree under `root/common/national_focus` (or `root` itself)."""
    focus_dir = root / "common" / "national_focus"
    if not focus_dir.is_dir():
        focus_dir = root

    data = FocusData()
    if not focus_dir.is_dir():
        data.parse_errors.append(f"no such directory: {focus_dir}")
        return data

    for path in sorted(focus_dir.rglob("*.txt")):
        try:
            root_block = parse_file(path, lenient=True)
        except ParseError as exc:
            data.parse_errors.append(str(exc))
            continue
        except OSError as exc:
            data.parse_errors.append(f"{path}: {exc}")
            continue

        data.files_read += 1
        for message in root_block.recovered:
            data.malformed.append((path.name, message))

        # Shared and joint focuses live at file scope and are pulled into trees
        # by id. Joint focuses additionally span several countries at once.
        for shared in root_block.get_all("shared_focus"):
            if isinstance(shared, Block):
                focus = _extract_focus(shared, tree_id="(shared)", path=path, is_shared=True)
                if focus:
                    data.shared_focuses.append(focus)

        for joint in root_block.get_all("joint_focus"):
            if isinstance(joint, Block):
                focus = _extract_focus(joint, tree_id="(joint)", path=path, is_shared=True, is_joint=True)
                if focus:
                    data.shared_focuses.append(focus)

        for tree_block in root_block.get_all("focus_tree"):
            if not isinstance(tree_block, Block):
                continue

            tree = FocusTree(
                id=tree_block.get_scalar("id") or f"(unnamed@{path.name})",
                path=path,
                line=tree_block.line,
                is_default=tree_block.get_scalar("default") == "yes",
                country_tag=_tag_from_country_block(tree_block),
            )

            for key in ("shared_focus", "joint_focus"):
                for value in tree_block.get_all(key):
                    if isinstance(value, str):
                        tree.shared_focus_refs.append(value)
                    elif isinstance(value, Block):
                        focus = _extract_focus(
                            value, tree.id, path, is_shared=True, is_joint=(key == "joint_focus")
                        )
                        if focus:
                            data.shared_focuses.append(focus)

            for focus_block in tree_block.get_all("focus"):
                if isinstance(focus_block, Block):
                    focus = _extract_focus(focus_block, tree.id, path)
                    if focus:
                        tree.focuses.append(focus)

            data.trees.append(tree)

    return data
