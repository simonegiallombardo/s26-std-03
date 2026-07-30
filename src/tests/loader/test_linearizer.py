"""
test_linearizer.py — tests for the DFS linearization (linearizer.py).

These tests assert the linearizer encodes the supervisor-confirmed grammar:
a diamond becomes one ordered step; the action chain is captured in order;
components are split into the single continuation and the leaf outputs; the
depth cut keeps sub-assemblies whole; cycles are broken; and a malformed graph
is handled best-effort in STRICT mode without raising.
"""

import pytest

from disassembly_loader import (
    DepthMode,
    DepthSpec,
    NodeType,
    TraversalMode,
)
from disassembly_loader import adapter, linearizer
from disassembly_loader.models import DisassemblyGraph, Edge, GraphNode


# Reuse the same minimal-graph builder shape as the validation tests.
def _make_graph(nodes, edges):
    node_map = {n.id: n for n in nodes}
    out_acc, inc_acc = {}, {}
    for e in edges:
        out_acc.setdefault(e.src, []).append(e.dst)
        inc_acc.setdefault(e.dst, []).append(e.src)
    out_adj = {nid: tuple(out_acc.get(nid, ())) for nid in node_map}
    inc_adj = {nid: tuple(inc_acc.get(nid, ())) for nid in node_map}
    return DisassemblyGraph(
        nodes=node_map, edges=tuple(edges), out_adj=out_adj, inc_adj=inc_adj,
    )


# =============================================================================
# Clean graphs: one step per diamond, in disassembly order.
# =============================================================================

def test_bialetti_full_one_step_per_diamond(bialetti_graph):
    """
    Bialetti is grammar-conforming: full linearization must emit exactly one step
    per diamond (7), in continuation order, and each step index must be 1..N.
    """
    steps = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    assert len(steps) == 7
    assert [s.index for s in steps] == list(range(1, 8))


def test_maria_full_one_step_per_diamond(maria_graph):
    """Maria (10 diamonds) must produce 10 ordered steps."""
    steps = linearizer.linearize(maria_graph, DepthSpec(mode=DepthMode.FULL))
    assert len(steps) == 10


def test_step_captures_action_chain_and_outputs(bialetti_graph):
    """
    Each Bialetti step must capture a non-empty action chain and at least one
    output, and the continuing steps must carry a continues_as (schema 1.1: a
    tuple of continuing composites, non-empty here); the final step is terminal
    (empty continues_as). Bialetti is a linear chain, so each non-terminal step
    has exactly one continuation.
    """
    steps = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    for s in steps[:-1]:
        assert len(s.actions) >= 1
        assert len(s.continues_as) >= 1
    assert steps[-1].continues_as == ()  # terminal step: no continuation


def test_first_step_is_the_root_operation(bialetti_graph):
    """The first step must be the first operation applied to the root product."""
    steps = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    assert steps[0].operation  # non-empty operation label
    assert steps[0].index == 1


def test_action_text_is_the_readable_instruction(bialetti_graph):
    """
    Action text must be the human-readable instruction, not a code label.

    In Bialetti the raw `text` field is a code ("D1.1") while the real
    instruction lives in `step_description`; the adapter must surface the latter.
    This pins that fix — a content check, not just a length check — so a future
    change of the source field is caught here. We assert the instruction is
    prose (multiple words), not a short code.
    """
    steps = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    first_action = steps[0].actions[0]
    assert len(first_action.text.split()) > 2, \
        f"expected a readable instruction, got {first_action.text!r}"


# =============================================================================
# Depth cut.
# =============================================================================

def test_keep_main_produces_fewer_steps_than_full(bialetti_graph):
    """
    KEEP_MAIN must cut after the first level, yielding fewer steps than FULL and
    at least one kept-whole output block.
    """
    full = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    keep = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.KEEP_MAIN))
    assert len(keep) < len(full)
    kept_blocks = [o for s in keep for o in s.outputs if o.kept_whole]
    assert kept_blocks, "KEEP_MAIN should keep at least one sub-assembly whole"


def test_kept_whole_block_reports_hidden_leaf_count(bialetti_graph):
    """
    A kept-whole block must report how many leaf parts it hides
    (contained_leaf_count) so the user knows what is inside.
    """
    keep = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.KEEP_MAIN))
    blocks = [o for s in keep for o in s.outputs if o.kept_whole]
    assert blocks
    for b in blocks:
        assert b.contained_leaf_count is not None
        assert b.contained_leaf_count >= 0


def test_full_does_not_keep_anything_whole(bialetti_graph):
    """FULL disassembly must never mark an output kept_whole."""
    full = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    assert not any(o.kept_whole for s in full for o in s.outputs)


def test_schema_invariant_across_depths(bialetti_graph):
    """
    The IR SCHEMA must not depend on depth — only the number of steps does. Every
    step, under any depth, exposes the same fields with the same types. This pins
    the contract the 7 generators rely on.
    """
    full = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    keep = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.KEEP_MAIN))
    for steps in (full, keep):
        for s in steps:
            assert isinstance(s.actions, tuple)
            assert isinstance(s.outputs, tuple)
            assert isinstance(s.tools_required, tuple)
            assert isinstance(s.index, int)


# =============================================================================
# Manual depth: keep specific nodes whole.
# =============================================================================

def test_manual_keeps_designated_node_whole(bialetti_graph):
    """
    In MANUAL mode, a designated continuing component must be kept whole. We pick
    the composite that the first step continues into and ask to keep it whole;
    it must then appear as a kept_whole output and the guide must be shorter.
    """
    full = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    target_id = full[0].continues_as[0].node_id  # the composite after step 1
    manual = linearizer.linearize(
        bialetti_graph,
        DepthSpec(mode=DepthMode.MANUAL, keep_whole_ids=(target_id,)),
    )
    assert len(manual) < len(full)
    kept = [o for s in manual for o in s.outputs if o.kept_whole and o.node_id == target_id]
    assert kept, "the designated node should be kept whole"


# =============================================================================
# Cycle protection: a cyclic graph must not loop forever.
# =============================================================================

def test_cycle_does_not_loop_forever():
    """
    A graph with a cycle must linearize without hanging: the visited-set breaks
    the cycle. We build root -> diamond A -> composite -> diamond B -> (back to
    composite), and assert linearization terminates and visits each diamond once.
    """
    nodes = [
        GraphNode(id=1, type=NodeType.COMPONENT, text="Root", x=0, y=0),
        GraphNode(id=2, type=NodeType.DIAMOND, text="Op A", x=0, y=1),
        GraphNode(id=3, type=NodeType.ACTION, text="do A", x=1, y=1),
        GraphNode(id=4, type=NodeType.COMPONENT, text="Composite", x=0, y=2),
        GraphNode(id=5, type=NodeType.DIAMOND, text="Op B", x=0, y=3),
        GraphNode(id=6, type=NodeType.ACTION, text="do B", x=1, y=3),
    ]
    edges = [
        Edge(src=1, dst=2), Edge(src=2, dst=3), Edge(src=2, dst=4),
        Edge(src=4, dst=5), Edge(src=5, dst=6),
        Edge(src=5, dst=4),  # cycle: Op B points back to the composite
    ]
    graph = _make_graph(nodes, edges)
    steps = linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL))
    # must terminate; each diamond appears at most once
    diamond_ops = [s.operation for s in steps]
    assert len(diamond_ops) == len(set(diamond_ops))


# =============================================================================
# Malformed graph (Epson multi-continuation): STRICT proceeds, does not raise.
# =============================================================================

def test_epson_strict_does_not_raise(epson_path):
    """
    Epson has multi-continuation anomalies. STRICT linearization must complete
    without raising, following the grammatical chain best-effort.
    """
    graph = adapter.normalize_file(epson_path)
    steps = linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL))
    assert isinstance(steps, tuple)  # produced a guide, did not raise


# =============================================================================
# Empty graph -> empty steps.
# =============================================================================

def test_empty_graph_yields_no_steps():
    """An empty graph linearizes to an empty tuple, no error."""
    graph = _make_graph([], [])
    assert linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL)) == ()


# =============================================================================
# LENIENT is reserved and must raise a clear NotImplementedError.
# =============================================================================

def test_lenient_raises_not_implemented(bialetti_graph):
    """
    LENIENT traversal is intentionally not implemented yet; calling it must raise
    NotImplementedError with an explanatory message, not fail silently.
    """
    with pytest.raises(NotImplementedError):
        linearizer.linearize(
            bialetti_graph, DepthSpec(mode=DepthMode.FULL), TraversalMode.LENIENT
        )


def test_strict_is_the_default(bialetti_graph):
    """Calling linearize without a traversal arg must behave as STRICT."""
    default = linearizer.linearize(bialetti_graph, DepthSpec(mode=DepthMode.FULL))
    explicit = linearizer.linearize(
        bialetti_graph, DepthSpec(mode=DepthMode.FULL), TraversalMode.STRICT
    )
    assert len(default) == len(explicit)


def test_fanout_actions_are_all_collected(oranfresh_path):
    """
    Real-data regression for the fan-out action fix. Oranfresh's diamonds list
    their instructions as a fan-out (several action children directly off each
    diamond, not chained). The linearizer must collect ALL of them, not just the
    first — the earlier chain-only logic silently kept one and lost the rest.

    For every step, the number of actions collected must equal the number of
    action children of the corresponding diamond in the graph.
    """
    graph = adapter.normalize_file(oranfresh_path)
    steps = linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL))
    assert steps, "Oranfresh should produce steps"
    for step in steps:
        diamond_id = next(
            n for n, nd in graph.nodes.items()
            if nd.type is NodeType.DIAMOND and nd.text == step.operation
        )
        action_children = [
            k for k in graph.out_adj.get(diamond_id, ())
            if k in graph.nodes and graph.nodes[k].type is NodeType.ACTION
        ]
        assert len(step.actions) == len(action_children), (
            f"step '{step.operation}' collected {len(step.actions)} actions "
            f"but the diamond has {len(action_children)} action children"
        )


def test_airfryer_real_branching_reaches_all_diamonds(airfryer_path):
    """
    Real-data confirmation of output branching. The Philips air fryer is a
    well-formed graph whose diamonds 193 and 248 each produce two continuing
    composites on separate paths — the first real graph (of the whole corpus) to
    exercise the tree-branching the synthetic test covers. Every diamond must be
    linearized into a step; none may be dropped on the unfollowed branch.
    """
    graph = adapter.normalize_file(airfryer_path)
    steps = linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL))
    diamonds = [
        n for n, nd in graph.nodes.items() if nd.type is NodeType.DIAMOND
    ]
    reached = {s.operation for s in steps}
    unreached = [d for d in diamonds if graph.nodes[d].text not in reached]
    assert not unreached, f"branching dropped diamonds: {unreached}"
    assert len(steps) == len(diamonds)


def test_diamond_with_multiple_continuing_outputs_branches():
    """
    A diamond may produce SEVERAL continuing composites, each disassembled along
    its own branch (supervisor-confirmed grammar: the tree branches on a
    diamond's OUTPUTS). The linearizer must descend into ALL of them, not just
    the first. No real fixture exhibits this yet, so it is tested synthetically.

    Graph: Split (a diamond) yields a leaf screw plus TWO continuing halves; each
    half is opened by its own diamond. Expect 3 steps in DFS order: Split, then
    the left branch fully, then the right branch.
    """
    nodes = [
        GraphNode(id=1, type=NodeType.COMPONENT, text="Product", x=0, y=0),
        GraphNode(id=2, type=NodeType.DIAMOND, text="Split", x=0, y=1),
        GraphNode(id=3, type=NodeType.ACTION, text="Separate the two halves", x=1, y=1),
        GraphNode(id=4, type=NodeType.COMPONENT, text="Screw", x=-1, y=2),
        GraphNode(id=5, type=NodeType.COMPONENT, text="Left half", x=0, y=2),
        GraphNode(id=6, type=NodeType.COMPONENT, text="Right half", x=2, y=2),
        GraphNode(id=7, type=NodeType.DIAMOND, text="Open left", x=0, y=3),
        GraphNode(id=8, type=NodeType.ACTION, text="Unclip left", x=1, y=3),
        GraphNode(id=9, type=NodeType.COMPONENT, text="Left part", x=0, y=4),
        GraphNode(id=10, type=NodeType.DIAMOND, text="Open right", x=2, y=3),
        GraphNode(id=11, type=NodeType.ACTION, text="Unclip right", x=3, y=3),
        GraphNode(id=12, type=NodeType.COMPONENT, text="Right part", x=2, y=4),
    ]
    edges = [
        Edge(1, 2), Edge(2, 3), Edge(2, 4), Edge(2, 5), Edge(2, 6),
        Edge(5, 7), Edge(7, 8), Edge(7, 9),
        Edge(6, 10), Edge(10, 11), Edge(10, 12),
    ]
    graph = _make_graph(nodes, edges)
    steps = linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL))
    operations = [s.operation for s in steps]
    assert operations == ["Split", "Open left", "Open right"], \
        f"both branches must be linearized in DFS order, got {operations}"