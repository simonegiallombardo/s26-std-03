"""
test_models.py — tests for the data vocabulary in models.py.

These are the simplest tests in the suite and demonstrate the core pytest
mechanics: plain `assert`, `pytest.raises` for expected exceptions, and
`@pytest.mark.parametrize` for running one test body over many inputs.

We test models.py even though it "has no logic" because it carries DESIGN
GUARANTEES we rely on everywhere else: immutability of the IR, the real
immutability of collection fields (tuple, not list), and the DepthSpec
invariant. If any of these silently broke, bugs would surface far away in the
loader or in a teammate's generator. A test here pins the guarantee at its
source.
"""

import dataclasses

import pytest

from disassembly_loader import (
    Action,
    Component,
    DepthMode,
    DepthSpec,
    Guide,
    Severity,
    Step,
    ValidationWarning,
)


# =============================================================================
# Frozen enforcement: IR objects must reject mutation after construction.
# =============================================================================

def test_step_is_frozen():
    """
    A Step must not allow attribute reassignment.

    Mechanic shown: `pytest.raises`. We EXPECT the assignment to raise
    FrozenInstanceError; the test passes only if it does. If the assignment
    were allowed (frozen removed by accident), no exception is raised, the
    `with` block completes normally, and pytest fails the test because the
    expected exception did not occur.
    """
    step = Step(index=1, operation="Open outer shell", input=Component(node_id=1, name="Product"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        step.index = 2  # type: ignore[misc]  # intentionally illegal


def test_guide_is_frozen():
    """Same guarantee for Guide, the top-level object handed to consumers."""
    guide = Guide(product=Component(node_id=1, name="Product"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        guide.schema_version = "9.9"  # type: ignore[misc]


# =============================================================================
# Tuple-not-list: collection fields must be genuinely immutable.
# =============================================================================

def test_ir_collection_fields_are_tuples():
    """
    Collection fields on IR objects must be tuples, not lists.

    WHY THIS MATTERS: `frozen=True` freezes the field *binding*, not the object
    it points to. With a list field, `step.outputs.append(x)` would still
    mutate a "frozen" Step. Using tuple makes that impossible. This test pins
    the choice so a future refactor that swaps tuple->list is caught here
    instead of causing a spooky mutation bug downstream.
    """
    step = Step(index=1, operation="op", input=Component(node_id=1, name="P"))
    assert isinstance(step.outputs, tuple)
    assert isinstance(step.actions, tuple)
    assert isinstance(step.tools_required, tuple)

    guide = Guide(product=Component(node_id=1, name="P"))
    assert isinstance(guide.steps, tuple)
    assert isinstance(guide.warnings, tuple)


def test_tuple_field_rejects_mutation():
    """A tuple field has no `append`; attempting it raises AttributeError."""
    step = Step(index=1, operation="op", input=Component(node_id=1, name="P"))
    with pytest.raises(AttributeError):
        step.outputs.append(Component(node_id=2, name="x"))  # type: ignore[attr-defined]


# =============================================================================
# DepthSpec invariant: keep_whole_ids only valid in MANUAL mode.
# =============================================================================

def test_depthspec_manual_accepts_ids():
    """MANUAL mode with explicit ids is the valid use and must construct fine."""
    spec = DepthSpec(mode=DepthMode.MANUAL, keep_whole_ids=(5, 7))
    assert spec.mode is DepthMode.MANUAL
    assert spec.keep_whole_ids == (5, 7)


@pytest.mark.parametrize("mode", [DepthMode.FULL, DepthMode.KEEP_MAIN])
def test_depthspec_rejects_ids_outside_manual(mode):
    """
    Supplying keep_whole_ids in a non-MANUAL mode must raise ValueError.

    Mechanic shown: `@pytest.mark.parametrize`. Instead of writing one test for
    FULL and a near-identical one for KEEP_MAIN, we list the modes and pytest
    runs the SAME body once per value, reporting them as separate test cases
    (test_..._[FULL] and test_..._[KEEP_MAIN]). One body, several cases, each
    independently pass/fail.
    """
    with pytest.raises(ValueError):
        DepthSpec(mode=mode, keep_whole_ids=(5,))


def test_depthspec_full_without_ids_is_fine():
    """FULL mode with no ids is the normal case and must construct fine."""
    spec = DepthSpec(mode=DepthMode.FULL)
    assert spec.keep_whole_ids == ()


# =============================================================================
# Enum-as-string: severities/types must serialize to readable strings.
# =============================================================================

def test_severity_serializes_as_string():
    """
    Severity inherits from str, so it compares equal to and serializes as its
    string value — no custom JSON encoder needed for warnings.
    """
    warning = ValidationWarning(
        rule="no_cycles",
        severity=Severity.WARNING,
        message="cycle detected among nodes 28 -> 31 -> 28",
        node_ids=(28, 31),
    )
    assert warning.severity == "warning"
    assert warning.node_ids == (28, 31)


def test_action_defaults_are_safe():
    """An Action built with only the required fields has sane empty defaults."""
    action = Action(node_id=3)
    assert action.text == ""
    assert action.tools is None
    assert action.image_path is None