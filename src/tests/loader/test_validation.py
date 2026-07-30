"""
test_validation.py — tests for the validation rule engine (validation.py).

These tests are the payoff of using REAL broken graphs as fixtures: each
malformed teammate file exercises a different rule, so the suite proves the
validator behaves correctly on inputs that actually occur, not invented ones.

New pytest mechanic shown here: parametrize with `ids=`, which gives each
generated case a readable name in the test report instead of an index.
"""

import pytest

from disassembly_loader import NodeType, Severity
from disassembly_loader import adapter, validation
from disassembly_loader.models import (
    DisassemblyGraph,
    Edge,
    GraphNode,
)


# =============================================================================
# Clean graphs must produce no ERROR/WARNING findings (no false positives).
# =============================================================================
# INFO findings (e.g. root_declaration coherence) are acceptable on clean
# graphs; we assert specifically that nothing of WARNING or ERROR severity fires.

@pytest.mark.parametrize(
    "fixture_name",
    ["bialetti_graph", "maria_graph"],
    ids=["bialetti", "maria"],
)
def test_clean_graphs_have_no_serious_findings(fixture_name, request):
    """
    A well-formed graph must not raise WARNING/ERROR findings.

    Mechanic: `request.getfixturevalue(name)` resolves a fixture BY NAME at
    runtime. We parametrize over fixture *names* (strings) and ask pytest for
    each graph dynamically — handy when you want one test body to run over
    several existing fixtures without writing a wrapper for each.
    """
    graph = request.getfixturevalue(fixture_name)
    findings = validation.validate(graph)
    serious = [f for f in findings if f.severity in (Severity.WARNING, Severity.ERROR)]
    assert serious == [], f"unexpected serious findings: {[f.rule for f in serious]}"


# =============================================================================
# Each broken graph must trigger exactly its expected rule set.
# =============================================================================
# We assert on rule NAMES (stable identifiers), not on message prose, so the
# tests do not break when wording changes.

def _rules_fired(graph) -> set[str]:
    return {f.rule for f in validation.validate(graph)}


def test_nespresso_triggers_action_hub_rules(nespresso_graph):
    """
    nespresso models actions as fan-out hubs (an action with several component
    children). That must trigger action_degree (the action's out-degree) and
    diamond_grammar (a diamond left without its action child).
    """
    fired = _rules_fired(nespresso_graph)
    assert "action_degree" in fired
    assert "diamond_grammar" in fired
    # no cycle in this file
    assert "no_cycles" not in fired


def test_capsule_triggers_cycle_rule(capsule_path):
    """
    capsule contains a real cycle plus a multi-degree action. It must trigger
    no_cycles AND action_degree. (We take the path fixture and normalize here to
    show the alternative to a graph fixture.)
    """
    graph = adapter.normalize_file(capsule_path)
    fired = _rules_fired(graph)
    assert "no_cycles" in fired
    assert "action_degree" in fired


def test_washing_triggers_diamond_grammar(washing_machine_path):
    """
    washing_machine is structurally clean of cycles and action-degree problems
    but semantically broken: diamonds chained without their action sub-steps.
    diamond_grammar (no action chain) must fire; cycles/action_degree must not.
    """
    graph = adapter.normalize_file(washing_machine_path)
    fired = _rules_fired(graph)
    assert "diamond_grammar" in fired
    assert "no_cycles" not in fired
    assert "action_degree" not in fired


def test_epson_triggers_only_diamond_continuation(request):
    """
    Epson is large (112 nodes) and well-formed EXCEPT for 5 direct
    diamond->diamond edges. After correcting the grammar rules, the only serious
    finding on Epson must be diamond_continuation — no cycles, no action-degree
    problems, no missing action chains. This pins the discovery that motivated
    splitting the grammar rules.
    """
    graph = adapter.normalize_file(request.getfixturevalue("epson_path"))
    fired = _rules_fired(graph)
    assert "diamond_continuation" in fired
    assert "no_cycles" not in fired
    assert "action_degree" not in fired
    assert "diamond_grammar" not in fired  # every Epson diamond has its action chain


def test_diamond_continuation_names_both_diamonds():
    """
    A direct diamond->diamond edge must be reported with BOTH diamond ids so the
    user can locate the missing intermediate component (FR 2.2).
    """
    graph = _make_graph(
        nodes=[
            GraphNode(id=1, type=NodeType.COMPONENT, text="Root"),
            GraphNode(id=2, type=NodeType.DIAMOND, text="Op A"),
            GraphNode(id=3, type=NodeType.ACTION, text="do"),
            GraphNode(id=4, type=NodeType.DIAMOND, text="Op B"),
            GraphNode(id=5, type=NodeType.ACTION, text="do2"),
        ],
        edges=[
            Edge(src=1, dst=2), Edge(src=2, dst=3),
            Edge(src=2, dst=4),  # diamond 2 -> diamond 4 directly (anomaly)
            Edge(src=4, dst=5),
        ],
    )
    findings = [f for f in validation.validate(graph) if f.rule == "diamond_continuation"]
    assert findings, "expected a diamond_continuation finding"
    assert 2 in findings[0].node_ids and 4 in findings[0].node_ids


def test_clean_reference_files_have_no_diamond_continuation(bialetti_graph, maria_graph):
    """
    The well-formed reference files must NOT trigger diamond_continuation:
    diamond->diamond is an Epson-specific anomaly, not present in clean models.
    Guards against the new rule producing false positives.
    """
    for graph in (bialetti_graph, maria_graph):
        fired = _rules_fired(graph)
        assert "diamond_continuation" not in fired


def test_action_fanout_is_info_on_fanout_only(oranfresh_path, bialetti_graph, maria_graph):
    """
    action_fanout is an INFO note that fires once per diamond using the fan-out
    layout. It must fire on Oranfresh (every diamond fans out) and must NOT fire
    on the chained reference files (no false positives on the normal layout).
    """
    g = adapter.normalize_file(oranfresh_path)
    fan = [w for w in validation.validate(g) if w.rule == "action_fanout"]
    assert fan, "Oranfresh diamonds use fan-out; the note must fire"
    assert all(w.severity is Severity.INFO for w in fan), "must be INFO, not an anomaly"

    for graph in (bialetti_graph, maria_graph):
        chained = [w for w in validation.validate(graph) if w.rule == "action_fanout"]
        assert chained == [], "chained layout must not trigger the fan-out note"


def test_self_explanatory_diamonds_are_not_flagged(airfryer_path, washing_machine_path):
    """
    A diamond with no action but a name and outputs is self-explanatory and valid
    (the operation name is the instruction) — it must NOT trigger diamond_grammar.
    The air fryer has 12 such diamonds and must be clean on this rule.

    But a diamond with no action AND no output (does nothing) is still a genuine
    gap and must still be flagged — washing_machine's empty 'Unscrew' diamonds.
    This pins the relaxed rule against over- and under-firing at once.
    """
    airfryer = adapter.normalize_file(airfryer_path)
    af = [w for w in validation.validate(airfryer) if w.rule == "diamond_grammar"]
    assert af == [], "self-explanatory diamonds must not be flagged"

    washing = adapter.normalize_file(washing_machine_path)
    wm = [w for w in validation.validate(washing) if w.rule == "diamond_grammar"]
    assert wm, "empty diamonds (no action, no output) must still be flagged"


def test_dishwasher_isolated_node_is_orphan_not_root(dishwasher_path):
    """
    Real-data regression for the orphan-vs-root fix. The dishwasher model has a
    fully isolated action node (id 60). It must be reported as an orphan and must
    NOT inflate the root count: with one real root present, single_root must not
    fire a spurious multiple-roots warning naming the isolated node.

    This is the only fixture exercising a real isolated node, which is why it
    earns a permanent place in the suite.
    """
    graph = adapter.normalize_file(dishwasher_path)
    findings = validation.validate(graph)
    orphan = [f for f in findings if f.rule == "no_orphans"]
    single_root = [f for f in findings if f.rule == "single_root"]
    assert orphan and 60 in orphan[0].node_ids, "isolated node 60 must be an orphan"
    assert single_root == [], "isolated node must not be counted as a second root"


def test_cycle_finding_names_the_offending_nodes(capsule_path):
    """
    FR 2.2 requires point-by-point reporting. The cycle finding must carry the
    id(s) of the node(s) involved, not just a generic message.
    """
    graph = adapter.normalize_file(capsule_path)
    cycle_findings = [f for f in validation.validate(graph) if f.rule == "no_cycles"]
    assert cycle_findings, "expected a cycle finding"
    assert cycle_findings[0].node_ids, "cycle finding must localize the node(s)"


# -- Cycle-detection edge cases (synthetic: no real file exhibits these) -------
# The cycle detector is the most intricate piece of logic in validation.py, and
# the single real cycle (capsule) only exercises the common case. These pin two
# boundary cases so a future refactor of the detector cannot silently break them.

def test_self_loop_is_detected():
    """
    A node with an edge to itself (1 -> 1) is the smallest possible cycle. The
    detector must flag it and name the node.
    """
    graph = _make_graph(
        nodes=[
            GraphNode(id=1, type=NodeType.COMPONENT, text="Root"),
            GraphNode(id=2, type=NodeType.DIAMOND, text="Op"),
        ],
        edges=[Edge(src=1, dst=2), Edge(src=2, dst=2)],  # 2 points to itself
    )
    findings = [f for f in validation.validate(graph) if f.rule == "no_cycles"]
    assert len(findings) == 1
    assert 2 in findings[0].node_ids


def test_two_independent_cycles_are_both_detected():
    """
    Two disjoint cycles (2<->3 and 5<->6) hanging off one root must BOTH be
    reported. This checks the detector keeps scanning after finding the first
    cycle rather than stopping early.
    """
    graph = _make_graph(
        nodes=[
            GraphNode(id=1, type=NodeType.COMPONENT, text="Root"),
            GraphNode(id=2, type=NodeType.DIAMOND, text="A"),
            GraphNode(id=3, type=NodeType.COMPONENT, text="B"),
            GraphNode(id=5, type=NodeType.DIAMOND, text="C"),
            GraphNode(id=6, type=NodeType.COMPONENT, text="D"),
        ],
        edges=[
            Edge(src=1, dst=2), Edge(src=2, dst=3), Edge(src=3, dst=2),  # cycle 2<->3
            Edge(src=1, dst=5), Edge(src=5, dst=6), Edge(src=6, dst=5),  # cycle 5<->6
        ],
    )
    findings = [f for f in validation.validate(graph) if f.rule == "no_cycles"]
    assert findings, "expected a cycle finding"
    # both cycles' back-edge targets must be reported
    reported = set(findings[0].node_ids)
    assert {2, 5}.issubset(reported), f"both cycles should be named, got {reported}"


# =============================================================================
# single_root: the one rule with VARIABLE severity. Test both branches with
# small synthetic graphs (no real file has zero or multiple roots).
# =============================================================================
# A hand-built graph is justified here because none of the six real files
# exhibits these conditions; we must construct them to test the rule.

def _make_graph(nodes: list[GraphNode], edges: list[Edge]) -> DisassemblyGraph:
    """Build a minimal DisassemblyGraph with adjacency, like the adapter does."""
    node_map = {n.id: n for n in nodes}
    out_acc: dict[int, list[int]] = {}
    inc_acc: dict[int, list[int]] = {}
    for e in edges:
        out_acc.setdefault(e.src, []).append(e.dst)
        inc_acc.setdefault(e.dst, []).append(e.src)
    out_adj = {nid: tuple(out_acc.get(nid, ())) for nid in node_map}
    inc_adj = {nid: tuple(inc_acc.get(nid, ())) for nid in node_map}
    return DisassemblyGraph(
        nodes=node_map, edges=tuple(edges), out_adj=out_adj, inc_adj=inc_adj,
    )


def test_single_root_multiple_roots_is_warning():
    """
    Two nodes that each start a disassembly path (no incoming edge but with an
    outgoing edge) -> single_root fires at WARNING. (Isolated nodes with no edges
    at all are orphans, not roots — see test below.)
    """
    graph = _make_graph(
        nodes=[
            GraphNode(id=1, type=NodeType.COMPONENT, text="Root A"),
            GraphNode(id=2, type=NodeType.DIAMOND, text="Op A"),
            GraphNode(id=3, type=NodeType.COMPONENT, text="Root B"),
            GraphNode(id=4, type=NodeType.DIAMOND, text="Op B"),
        ],
        edges=[Edge(src=1, dst=2), Edge(src=3, dst=4)],  # two separate start paths
    )
    findings = [f for f in validation.validate(graph) if f.rule == "single_root"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING
    assert set(findings[0].node_ids) == {1, 3}


def test_isolated_node_is_orphan_not_root():
    """
    A fully isolated node (no edges at all) must be reported as an orphan, NOT as
    a spurious extra root. Pins the dishwasher fix: one real root + one isolated
    node should yield an orphan finding and NO multiple-roots warning.
    """
    graph = _make_graph(
        nodes=[
            GraphNode(id=1, type=NodeType.COMPONENT, text="Root"),
            GraphNode(id=2, type=NodeType.DIAMOND, text="Op"),
            GraphNode(id=9, type=NodeType.ACTION, text="Isolated instruction"),
        ],
        edges=[Edge(src=1, dst=2)],  # node 9 has no edges at all
    )
    rules = {f.rule for f in validation.validate(graph)}
    assert "no_orphans" in rules          # 9 is flagged as orphan
    single_root = [f for f in validation.validate(graph) if f.rule == "single_root"]
    assert single_root == []              # 1 is the only root; no false multi-root


def test_single_root_zero_roots_is_error():
    """
    A 2-node cycle (1->2->1) has no node without an incoming edge -> zero roots
    -> single_root fires at ERROR.
    """
    graph = _make_graph(
        nodes=[
            GraphNode(id=1, type=NodeType.COMPONENT, text="A"),
            GraphNode(id=2, type=NodeType.COMPONENT, text="B"),
        ],
        edges=[Edge(src=1, dst=2), Edge(src=2, dst=1)],
    )
    findings = [f for f in validation.validate(graph) if f.rule == "single_root"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR


# =============================================================================
# Empty graph: the one case no real file covers. Synthetic by necessity.
# =============================================================================

def test_empty_graph_triggers_non_empty_error():
    """
    A graph with zero nodes is parsable (shapes: []) but degenerate. non_empty
    must fire at ERROR, and single_root must stay silent (emptiness is not its
    job).
    """
    graph = _make_graph(nodes=[], edges=[])
    findings = validation.validate(graph)
    rules = {f.rule for f in findings}
    assert "non_empty" in rules
    non_empty = [f for f in findings if f.rule == "non_empty"][0]
    assert non_empty.severity is Severity.ERROR
    assert "single_root" not in rules


# =============================================================================
# The engine never raises and never mutates (FR 2.3, NFR 2.1).
# =============================================================================

def test_validate_never_raises_on_broken_graphs(capsule_path, nespresso_path):
    """Validation must complete on broken graphs without raising."""
    for path in (capsule_path, nespresso_path):
        graph = adapter.normalize_file(path)
        validation.validate(graph)  # must not raise


def test_validate_does_not_mutate_graph(bialetti_graph):
    """Validation must not change the graph (NFR 2.1: non-destructive)."""
    before_nodes = len(bialetti_graph.nodes)
    before_edges = len(bialetti_graph.edges)
    validation.validate(bialetti_graph)
    assert len(bialetti_graph.nodes) == before_nodes
    assert len(bialetti_graph.edges) == before_edges