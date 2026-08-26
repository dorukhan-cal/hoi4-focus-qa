"""The fixture tree carries one deliberate defect per check."""

from pathlib import Path

import pytest

from hoi4qa.checklist import build_checklist, find_tree
from hoi4qa.checks import ERROR, run_all
from hoi4qa.clausewitz import ParseError, parse
from hoi4qa.model import load_directory

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def data():
    return load_directory(FIXTURES)


@pytest.fixture(scope="module")
def findings(data):
    return run_all(data)


def _for(findings, category):
    return [f for f in findings if f.category == category]


def test_tree_loads(data):
    assert data.files_read == 1
    assert len(data.trees) == 1
    assert data.trees[0].id == "testland_focus"
    assert data.trees[0].country_tag == "TST"
    assert not data.parse_errors


def test_duplicate_id(findings):
    found = _for(findings, "duplicate-id")
    assert len(found) == 1
    assert found[0].focus_id == "TST_rearmament"


def test_dangling_prerequisite(findings):
    found = _for(findings, "dangling-prerequisite")
    assert [f.focus_id for f in found] == ["TST_expeditionary_force"]
    assert "TST_colonial_office" in found[0].message


def test_dangling_relative_position(findings):
    assert [f.focus_id for f in _for(findings, "dangling-relative-position")] == ["TST_home_defence"]


def test_asymmetric_exclusivity(findings):
    found = _for(findings, "asymmetric-exclusivity")
    assert [f.focus_id for f in found] == ["TST_land_doctrine"]


def test_unreachable_through_exclusive_pair(findings):
    found = _for(findings, "unreachable")
    assert [f.focus_id for f in found] == ["TST_combined_arms"]


def test_prerequisite_cycle_reported_once(findings):
    found = _for(findings, "prerequisite-cycle")
    assert len(found) == 1
    assert "TST_second_congress" in found[0].message


def test_position_collision(findings):
    assert [f.focus_id for f in _for(findings, "position-collision")] == ["TST_total_mobilisation"]


def test_missing_completion_reward(findings):
    assert [f.focus_id for f in _for(findings, "no-completion-reward")] == ["TST_war_economy"]


def test_errors_sort_first(findings):
    severities = [f.severity for f in findings]
    assert severities[: severities.count(ERROR)] == [ERROR] * severities.count(ERROR)


def test_checklist_covers_the_exclusive_decision(data):
    tree = find_tree(data, "TST")
    text = "\n".join(build_checklist(tree))
    assert "TST_land_doctrine | TST_naval_doctrine" in text
    assert "Save, reload, and confirm the lock survives" in text
    # The duplicated entry focus must appear once, not twice.
    assert text.count("`TST_rearmament` selectable on day one") == 1


# --- parser ---------------------------------------------------------------


def test_repeated_keys_are_preserved():
    block = parse("a = { focus = one } a = { focus = two }")
    assert len(block.get_all("a")) == 2


def test_comments_and_quotes():
    block = parse('# comment\nname = "Hello World" # trailing\nvalue = 3')
    assert block.get_scalar("name") == "Hello World"
    assert block.get_scalar("value") == "3"


def test_bare_list_values():
    block = parse("traits = { fast brave }")
    assert block.get_block("traits").values == ["fast", "brave"]


def test_comparison_operators_parse():
    block = parse("limit = { threat > 0.5 }")
    assert block.get_block("limit").statements[0] == ("threat", ">", "0.5")


def test_lenient_parsing_recovers_from_stray_closing_brace():
    """Vanilla ships one such file; rejecting it would hide everything inside."""
    block = parse("focus = { id = A }\n}\nfocus = { id = B }", lenient=True)
    assert [f.get_scalar("id") for f in block.get_all("focus")] == ["A", "B"]
    assert len(block.recovered) == 1
    assert "unmatched closing brace" in block.recovered[0]


def test_strict_parsing_still_raises_on_stray_brace():
    with pytest.raises(ParseError):
        parse("focus = { id = A }\n}", lenient=False)


def test_joint_focus_reward_keys_count_as_rewards():
    from hoi4qa.model import _extract_focus

    joint = parse(
        "joint_focus = { id = J completion_reward_joint_originator = { x = 1 } }"
    ).get_block("joint_focus")
    focus = _extract_focus(joint, "(joint)", Path("f.txt"), is_shared=True, is_joint=True)
    assert focus.has_completion_reward
    assert focus.is_joint


def test_unterminated_block_raises():
    with pytest.raises(ParseError):
        parse("focus = { id = X")


def test_unmatched_closing_brace_raises():
    with pytest.raises(ParseError):
        parse("a = 1 }")
