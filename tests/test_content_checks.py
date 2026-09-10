"""Localisation, icon and position-exemption checks.

Kept in a separate fixture from test_checks.py so the two sets of deliberate
defects don't interfere with each other's exact-match assertions.
"""

from pathlib import Path

import pytest

from hoi4qa.checks import run_all
from hoi4qa.clausewitz import ParseError, parse
from hoi4qa.model import load_directory

FIXTURES = Path(__file__).parent / "fixtures_content"
PLAIN = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def data():
    return load_directory(FIXTURES)


@pytest.fixture(scope="module")
def findings(data):
    return run_all(data)


def _ids(findings, category):
    return sorted(f.focus_id for f in findings if f.category == category)


def test_fixture_loads_localisation_and_sprites(data):
    assert data.has_localisation and data.has_sprites
    assert "CON_alpha" in data.loc_keys
    assert data.sprite_names == {"GFX_con_alpha", "GFX_con_unused"}


def test_missing_localisation(findings):
    assert _ids(findings, "missing-localisation") == ["CON_gamma"]


def test_text_override_is_honoured(findings):
    """CON_beta is not localised under its own id, and that is correct."""
    reported = _ids(findings, "missing-localisation") + _ids(findings, "missing-description")
    assert "CON_beta" not in reported


def test_missing_description(findings):
    assert _ids(findings, "missing-description") == ["CON_delta"]


def test_missing_icon(findings):
    assert _ids(findings, "missing-icon") == ["CON_epsilon"]


def test_position_check_exempts_allow_branch_and_offset(findings):
    """The fix for the vanilla false positives, pinned.

    CON_branch_a/b and CON_offset_a/b share grid squares legitimately. The
    genuinely overlapping pair is reported, and so is the pair whose
    allow_branch is an empty stub -- an empty block exempts nothing.
    """
    assert _ids(findings, "position-collision") == ["CON_overlap_b", "CON_stub_b"]


def test_infrastructure_without_bypass(findings):
    """Only the capped, fixed-state, unskippable case is reported.

    A bookkeeping `set_state_flag` must not disqualify it; a real bypass, a
    second reward, an uncapped building and a dynamic scope all must.
    """
    assert _ids(findings, "infrastructure-without-bypass") == ["CON_infra_no_bypass"]


def test_infrastructure_states_are_collected(data):
    focus = next(f for f in data.all_focuses if f.id == "CON_infra_no_bypass")
    assert focus.reward_is_infrastructure_only
    assert focus.infrastructure_states == ["11", "12"]

    dynamic = next(f for f in data.all_focuses if f.id == "CON_infra_dynamic")
    assert not dynamic.reward_is_infrastructure_only


def test_empty_stub_blocks_do_not_count_as_present(data):
    """Vanilla ships 4,670 empty `bypass = { }` stubs; none is a condition."""
    stub = next(f for f in data.all_focuses if f.id == "CON_stub_a")
    assert not stub.has_bypass
    assert not stub.has_available
    assert not stub.has_allow_branch

    real = next(f for f in data.all_focuses if f.id == "CON_branch_a")
    assert real.has_allow_branch


def test_checklist_omits_untestable_bypass_items(data):
    """A focus whose bypass is an empty stub must not become a test item."""
    from hoi4qa.checklist import build_checklist, find_tree

    text = "\n".join(build_checklist(find_tree(data, "CON")))
    assert "CON_stub_a` bypasses" not in text
    assert "Conditional availability" not in text or "CON_stub_a`:" not in text


def test_content_checks_stay_silent_without_localisation_or_sprites():
    """The other fixture ships neither, so these checks must produce nothing."""
    plain = run_all(load_directory(PLAIN))
    assert not [f for f in plain if f.category.startswith("missing-")]


def test_lenient_parsing_recovers_from_unterminated_block():
    """Vanilla ships six .gfx files whose root block is never closed."""
    block = parse('objectTypes = { pdxmesh = { name = "a" }', lenient=True)
    assert block.get_block("objectTypes") is not None
    assert len(block.recovered) == 1
    assert "never closed" in block.recovered[0]


def test_strict_parsing_still_raises_on_unterminated_block():
    with pytest.raises(ParseError):
        parse('objectTypes = { pdxmesh = { name = "a" }', lenient=False)
