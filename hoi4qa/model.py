"""Focus-tree model extracted from parsed Clausewitz blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import re

from .clausewitz import Block, ParseError, parse_file, read_file


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
    # A focus may point its displayed name at a different localisation key --
    # usually to avoid colliding with an identically named idea or doctrine.
    text: str | None = None
    has_available: bool = False
    has_bypass: bool = False
    has_completion_reward: bool = False
    has_allow_branch: bool = False
    # `offset` blocks move a focus per country, so its declared x/y is only one
    # of several positions it can occupy.
    has_offset: bool = False
    is_shared: bool = False
    is_joint: bool = False
    # Set when the whole reward is infrastructure construction in a fixed set of
    # states. Infrastructure is capped, so such a focus can complete with no
    # effect once those states are already at the cap.
    reward_is_infrastructure_only: bool = False
    infrastructure_states: list[str] = field(default_factory=list)

    @property
    def loc_key(self) -> str:
        """The localisation key this focus displays under."""
        return self.text or self.id

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
    # Populated only when the directory actually ships these. Checks that depend
    # on them stay silent otherwise, so pointing the tool at a bare focus folder
    # doesn't produce thousands of phantom "missing" findings.
    loc_keys: set[str] = field(default_factory=set)
    loc_language: str = "english"
    sprite_names: set[str] = field(default_factory=set)
    has_localisation: bool = False
    has_sprites: bool = False

    @property
    def all_focuses(self) -> list[Focus]:
        return [f for tree in self.trees for f in tree.focuses] + self.shared_focuses

    def by_id(self) -> dict[str, list[Focus]]:
        index: dict[str, list[Focus]] = {}
        for focus in self.all_focuses:
            index.setdefault(focus.id, []).append(focus)
        return index


# Effects that record or display something rather than giving the player
# anything. A focus is still "infrastructure only" if it also does these.
_BOOKKEEPING = {
    "set_state_flag", "set_country_flag", "clr_state_flag", "clr_country_flag",
    "custom_effect_tooltip", "effect_tooltip", "log", "tooltip",
    "set_variable", "add_to_variable",
}
# Blocks that select a scope rather than granting anything.
_SCOPES = {
    "if", "else", "else_if", "hidden_effect", "owner", "controller",
    "FROM", "ROOT", "PREV", "THIS",
}


def _infrastructure_only_reward(reward: Block) -> tuple[bool, list[str]]:
    """Is the entire reward infrastructure construction?

    Returns (is_infrastructure_only, state_ids). State ids are listed when the
    reward names them directly; a reward that builds through a dynamic scope
    such as `every_owned_state` still counts, but comes back with no ids because
    which states it touches depends on the save.
    """
    types: list[str | None] = []
    states: list[str] = []
    other = False

    def walk(block: Block, state: str | None) -> None:
        nonlocal other
        for key, _, value in block.statements:
            if isinstance(value, Block):
                # `limit` holds triggers that select a scope, not effects.
                if key == "limit":
                    continue
                if key == "add_building_construction":
                    types.append(value.get_scalar("type"))
                    if state:
                        states.append(state)
                elif key.isdigit():
                    walk(value, key)
                elif (
                    key.isupper()
                    or key in _SCOPES
                    or key.startswith(("every_", "random_", "any_", "all_"))
                ):
                    walk(value, state)
                elif key not in _BOOKKEEPING:
                    other = True
            elif key not in _BOOKKEEPING and key not in ("type", "level", "instant_build", "province"):
                other = True

    walk(reward, None)

    ok = bool(types) and not other and all(t == "infrastructure" for t in types)
    return ok, sorted(set(states), key=int)


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
        text=block.get_scalar("text"),
        # `has_content` throughout, not `has`: an empty stub block is not a
        # condition, and reporting one as present sends testers to verify
        # something that cannot fire.
        has_available=block.has_content("available"),
        has_bypass=block.has_content("bypass"),
        # Joint focuses reward the originating and participating countries
        # separately, so they carry neither plain `completion_reward`.
        has_completion_reward=(
            block.has_content("completion_reward")
            or block.has_content("completion_reward_joint_originator")
            or block.has_content("completion_reward_joint_member")
        ),
        has_allow_branch=block.has_content("allow_branch"),
        has_offset=block.has_content("offset"),
        is_shared=is_shared,
        is_joint=is_joint,
    )

    reward = block.get_block("completion_reward")
    if reward is not None:
        focus.reward_is_infrastructure_only, focus.infrastructure_states = (
            _infrastructure_only_reward(reward)
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


_LOC_KEY = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\s*\d*\s*"')


def load_localisation(root: Path, language: str = "english") -> set[str]:
    """Every key defined for `language`.

    Localisation is not Clausewitz script -- it is `KEY:0 "text"` lines under a
    language header -- so it is read line by line rather than parsed.
    """
    keys: set[str] = set()
    loc_dir = root / "localisation" / language
    if not loc_dir.is_dir():
        return keys

    for path in loc_dir.rglob("*.yml"):
        try:
            text = read_file(path)
        except OSError:
            continue
        for line in text.splitlines():
            match = _LOC_KEY.match(line)
            if match:
                keys.add(match.group(1))
    return keys


def load_sprites(root: Path) -> tuple[set[str], list[tuple[str, str]]]:
    """Sprite names declared in any .gfx file, plus any malformed ones found.

    Sprite definitions appear under several block types, so rather than
    enumerating them this collects every `name` whose value looks like a sprite
    reference. Over-collecting is the safe direction: it can only suppress a
    finding, never invent one.
    """
    names: set[str] = set()
    malformed: list[tuple[str, str]] = []

    def collect(block: Block) -> None:
        for key, _, value in block.statements:
            if isinstance(value, Block):
                collect(value)
            elif key == "name" and value.startswith("GFX_"):
                names.add(value)

    for path in root.rglob("*.gfx"):
        try:
            root_block = parse_file(path, lenient=True)
        except (ParseError, OSError):
            continue
        collect(root_block)
        for message in root_block.recovered:
            malformed.append((path.name, message))

    return names, malformed


def load_directory(root: Path, language: str = "english") -> FocusData:
    """Load every focus tree under `root/common/national_focus` (or `root` itself)."""
    focus_dir = root / "common" / "national_focus"
    if not focus_dir.is_dir():
        focus_dir = root

    data = FocusData(loc_language=language)
    if not focus_dir.is_dir():
        data.parse_errors.append(f"no such directory: {focus_dir}")
        return data

    data.loc_keys = load_localisation(root, language)
    data.has_localisation = bool(data.loc_keys)

    if any(root.rglob("*.gfx")):
        data.sprite_names, gfx_malformed = load_sprites(root)
        data.has_sprites = bool(data.sprite_names)
        data.malformed.extend(gfx_malformed)

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
