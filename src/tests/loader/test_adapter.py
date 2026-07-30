"""
test_adapter.py — tests for format normalization (adapter.py).

This is where pytest FIXTURES earn their keep. Tests below take parameters like
`bialetti_graph` or `nespresso_graph`; pytest matches each name to a fixture in
conftest.py, runs it (which normalizes the real file through the adapter), and
passes the resulting DisassemblyGraph in. The test body never touches the
filesystem or the adapter directly — it just receives a ready graph.

The adapter's contract: absorb every input-format divergence and produce a
uniform DisassemblyGraph, WITHOUT judging validity. The tests assert exactly
that, using the real files that exhibit each divergence.
"""

import json

import pytest

from disassembly_loader import NodeType, UnparsableModelError
from disassembly_loader import adapter


# =============================================================================
# Divergence 1 + 2: edge LOCATION and FIELD NAMES are absorbed.
# =============================================================================
# Bialetti stores edges in a `connections` array with from_id/to_id.
# Maria stores them as `arrow` shapes with from_shape_id/to_shape_id.
# After normalization BOTH must yield a graph with edges as src->dst, and NO
# node of type "arrow" must survive (arrows are edges, not nodes).

def test_bialetti_edges_read_from_connections(bialetti_graph):
    """Bialetti's 62 connections become 62 canonical edges."""
    assert len(bialetti_graph.edges) == 62
    # Every edge has integer src/dst; no edge is missing endpoints.
    for edge in bialetti_graph.edges:
        assert isinstance(edge.src, int)
        assert isinstance(edge.dst, int)


def test_maria_edges_read_from_arrow_shapes(maria_graph):
    """Maria's 63 arrow shapes become 63 canonical edges."""
    assert len(maria_graph.edges) == 63


def test_arrow_shapes_are_not_nodes(maria_graph):
    """
    Arrows are edges, not nodes. After normalization no GraphNode may have a
    type derived from an arrow shape — arrows must have been routed to `edges`,
    not `nodes`. (We check no node id corresponds to an arrow by confirming all
    node types are real node roles.)
    """
    valid_node_types = {NodeType.COMPONENT, NodeType.DIAMOND,
                        NodeType.ACTION, NodeType.UNKNOWN}
    for node in maria_graph.nodes.values():
        assert node.type in valid_node_types
        # No node should literally be an arrow.
        assert node.type is not NodeType.UNKNOWN or "arrow" not in str(node.text).lower()


def test_both_formats_produce_same_shape(bialetti_graph, maria_graph):
    """
    The key uniformity guarantee: a test downstream cannot tell which input
    format produced the graph. Both expose the same attributes with the same
    types. (A test can request TWO fixtures at once — both are injected.)
    """
    for graph in (bialetti_graph, maria_graph):
        assert isinstance(graph.nodes, dict)
        assert isinstance(graph.edges, tuple)
        assert isinstance(graph.out_adj, dict)
        assert isinstance(graph.inc_adj, dict)
        # exactly one root (no incoming edges) in both well-formed graphs
        roots = [nid for nid in graph.nodes if not graph.inc_adj.get(nid)]
        assert len(roots) == 1


# =============================================================================
# Divergence 3: weight type (int in Bialetti, str elsewhere) is absorbed.
# =============================================================================

def test_weight_kept_as_string_when_present(bialetti_graph):
    """
    Bialetti stores weight as int in the source; the adapter keeps it as a
    string (deferring numeric parsing to the IR layer). Bialetti is the file
    that actually carries weights.
    """
    weighted = [n for n in bialetti_graph.nodes.values() if n.weight is not None]
    assert weighted, "Bialetti is expected to carry weights"
    for node in weighted:
        assert isinstance(node.weight, str)


def test_empty_weight_becomes_none(maria_graph):
    """
    Maria's components all carry an empty weight string (""). The adapter must
    normalize "" to None — a real and NORMAL case (FR 4.0 explicitly allows
    weights to be unknown). This pins that the loader/IR must tolerate missing
    weights rather than assume they exist.
    """
    weights = [n.weight for n in maria_graph.nodes.values()]
    assert all(w is None for w in weights), \
        "Maria has no weights; empty strings must normalize to None"


# =============================================================================
# Coordinate preservation: needed to order sibling fan-outs (nespresso).
# =============================================================================

def test_coordinates_preserved_for_fanout_ordering(nespresso_graph):
    """
    nespresso's action id=2 fans out to 4 sibling components. The edges give no
    order among siblings; only x-coordinates do. The adapter must preserve x so
    the loader can sort them left-to-right. Source arrival order is (6,7,5,4);
    sorted by x it must become (4,5,6,7) = Water Tank, Drip Tray, Capsule Bin,
    Main Housing.
    """
    children = nespresso_graph.out_adj[2]
    assert set(children) == {4, 5, 6, 7}
    # coordinates are present (not None) for all four children
    for cid in children:
        assert nespresso_graph.nodes[cid].x is not None
    ordered = sorted(children, key=lambda c: (nespresso_graph.nodes[c].x,
                                              nespresso_graph.nodes[c].y or 0))
    assert ordered == [4, 5, 6, 7]


# =============================================================================
# extra dict: unmodeled source fields are preserved, not dropped.
# =============================================================================

def test_extra_dict_preserves_unmodeled_fields(nespresso_graph):
    """
    The root node carries `root_component_id`, `brand`, `model`, etc. — fields
    we do not model as first-class but must not discard (FR 11.0 / NFR 2.0).
    They must appear in `extra`. `root_component_id` in particular is kept for
    the later topology-vs-declaration coherence check.
    """
    root = nespresso_graph.nodes[1]
    assert "root_component_id" in root.extra
    assert "brand" in root.extra


# =============================================================================
# UnparsableModelError boundary: only un-buildable input raises.
# =============================================================================
# A graph-level defect must NOT raise. Non-buildable input MUST raise.

def test_corrupt_json_raises(tmp_path):
    """
    Syntactically invalid JSON is the canonical 'no graph to build' case.

    Mechanic shown: `tmp_path`. It is a built-in pytest fixture giving a fresh
    temporary directory unique to this test — we write a broken file into it,
    so the test does not depend on or pollute the real fixtures. pytest cleans
    it up automatically.
    """
    bad = tmp_path / "broken.json"
    bad.write_text("{ this is not valid json", encoding="utf-8")
    with pytest.raises(UnparsableModelError):
        adapter.normalize_file(bad)


def test_missing_shapes_key_raises():
    """A dict with no `shapes` key has no graph to build -> raises."""
    with pytest.raises(UnparsableModelError):
        adapter.normalize({"metadata": {}, "connections": []})


def test_shapes_not_a_list_raises():
    """`shapes` present but not a list -> raises with a precise message."""
    with pytest.raises(UnparsableModelError):
        adapter.normalize({"shapes": "not a list"})


def test_dangling_edge_does_not_raise():
    """
    An edge pointing to a non-existent node id is a GRAPH-LEVEL defect, not an
    un-buildable input. The adapter must return a graph (the validator reports
    the dangling edge later), NOT raise. This pins the boundary decision.
    """
    raw = {
        "shapes": [
            {"id": 1, "type": "component", "text": "Root"},
            {"id": 2, "type": "diamond", "text": "Op"},
        ],
        # edge 2 -> 99, where 99 does not exist as a node
        "connections": [
            {"from_id": 1, "to_id": 2},
            {"from_id": 2, "to_id": 99},
        ],
    }
    graph = adapter.normalize(raw)  # must not raise
    assert 99 not in graph.nodes
    # the dangling endpoint still appears as an edge so the validator can find it
    assert any(edge.dst == 99 for edge in graph.edges)