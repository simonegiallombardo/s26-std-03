"""
test_builder.py — tests for the pipeline orchestration (builder.py).

builder.build_guide ties adapter + validation + linearizer into the final Guide.
These tests assert the assembled result is correct end to end: the product, the
steps, the warnings, and the optional bill of materials, including the subtle
cases confirmed on real data (mass conservation under a depth cut; a malformed
graph yielding an empty-but-warned guide).
"""

import pytest

from disassembly_loader import (
    DepthMode,
    DepthSpec,
    build_guide,
)
from disassembly_loader.models import DisassemblyGraph, Edge, GraphNode, NodeType


# =============================================================================
# Full pipeline on a clean file.
# =============================================================================

def test_build_guide_assembles_complete_guide(bialetti_path):
    """build_guide must return a Guide with product, steps, and a schema_version."""
    guide = build_guide(str(bialetti_path))
    assert guide.product.name  # the root product, named
    assert len(guide.steps) == 7
    assert guide.schema_version  # contract marker present


def test_build_guide_default_depth_is_full(bialetti_path):
    """With no depth argument, the guide is a full disassembly (most steps)."""
    full = build_guide(str(bialetti_path))
    keep = build_guide(str(bialetti_path), depth=DepthSpec(mode=DepthMode.KEEP_MAIN))
    assert len(full.steps) > len(keep.steps)


# =============================================================================
# Bill of materials: optional, leaf-only, mass-conserving.
# =============================================================================

def test_bom_absent_by_default(bialetti_path):
    """Without include_bom, the bill_of_materials stays None (always present as a
    field in the JSON, but null here)."""
    guide = build_guide(str(bialetti_path))
    assert guide.bill_of_materials is None


def test_bom_is_leaf_only_and_balances(bialetti_path):
    """
    With include_bom, the BoM is the leaf parts and their weights sum to the
    product weight (mass balance, FR 2.4). Bialetti: 18 leaves summing to 2500 g.
    """
    guide = build_guide(str(bialetti_path), include_bom=True)
    assert guide.bill_of_materials is not None
    assert len(guide.bill_of_materials) == 18
    total = sum(c.weight for c in guide.bill_of_materials if c.weight)
    assert total == pytest.approx(guide.product.weight)


def test_bom_conserves_mass_under_depth_cut(bialetti_path):
    """
    A kept-whole block carries the mass of everything inside it, so the BoM total
    is the SAME under keep_main as under full — the cut hides parts, it does not
    lose mass. Confirmed on Bialetti: both total 2500 g.
    """
    full = build_guide(str(bialetti_path), include_bom=True)
    keep = build_guide(
        str(bialetti_path), depth=DepthSpec(mode=DepthMode.KEEP_MAIN), include_bom=True
    )
    full_mass = sum(c.weight for c in full.bill_of_materials if c.weight)
    keep_mass = sum(c.weight for c in keep.bill_of_materials if c.weight)
    assert keep_mass == pytest.approx(full_mass)
    # and the kept-whole block reports how many leaves it hides
    kept = [c for c in keep.bill_of_materials if c.kept_whole]
    assert kept and kept[0].contained_leaf_count and kept[0].contained_leaf_count > 0


# =============================================================================
# Malformed graph: empty guide, BUT warnings explain why (never silent).
# =============================================================================

def test_malformed_graph_yields_empty_but_warned_guide(nespresso_path):
    """
    nespresso is structurally malformed (actions used as fan-out hubs; the root
    never reaches a diamond), so no grammatical steps can be produced: the guide
    is empty. That is correct — we do not invent steps from non-grammatical
    structure. But the guide must carry warnings explaining the problem, never be
    empty AND silent.
    """
    guide = build_guide(str(nespresso_path))
    assert len(guide.steps) == 0
    assert len(guide.warnings) > 0, "an empty guide must be explained by warnings"


# =============================================================================
# build_guide does not mutate / is read-only on the source (NFR 2.1).
# =============================================================================

def test_build_guide_is_repeatable(bialetti_path):
    """Building twice from the same file yields the same number of steps (the
    source is read-only; nothing is consumed or mutated)."""
    a = build_guide(str(bialetti_path))
    b = build_guide(str(bialetti_path))
    assert len(a.steps) == len(b.steps)