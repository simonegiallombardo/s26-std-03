"""
test_emitter.py — tests for IR JSON serialization (emitter.py).

These assert the JSON contract the 7 generators depend on: the fixed top-level
keys, explicit nulls (never omitted fields), the image {path, is_url} shape with
correct URL classification, ascii-safety, and round-trippability. Image flow is
tested with a SYNTHETIC graph because no real fixture has both images AND
produced steps (nespresso has images but yields no steps; the others produce
steps but carry no images).
"""

import json

import pytest

from disassembly_loader import (
    DepthMode,
    DepthSpec,
    build_guide,
    emit_json,
    guide_to_dict,
)
from disassembly_loader import adapter, builder
from disassembly_loader.models import (
    DisassemblyGraph, Edge, GraphNode, NodeType,
)


# =============================================================================
# Top-level schema shape.
# =============================================================================

def test_ir_has_expected_top_level_keys(bialetti_path):
    """The IR JSON must expose exactly the documented top-level keys."""
    d = guide_to_dict(build_guide(str(bialetti_path), include_bom=True))
    assert set(d.keys()) == {
        "schema_version", "product", "depth", "tools", "steps", "warnings",
        "bill_of_materials",
    }


def test_step_has_expected_keys(bialetti_path):
    """Each step must expose the documented keys in the contract."""
    d = guide_to_dict(build_guide(str(bialetti_path)))
    step = d["steps"][0]
    assert set(step.keys()) == {
        "index", "operation", "input", "actions", "outputs", "continues_as",
        "tools_required",
    }


# =============================================================================
# Explicit-null policy.
# =============================================================================

def test_bom_is_null_when_not_requested(bialetti_path):
    """bill_of_materials is present but null when include_bom is False."""
    d = guide_to_dict(build_guide(str(bialetti_path)))
    assert "bill_of_materials" in d
    assert d["bill_of_materials"] is None


def test_bom_is_list_when_requested(bialetti_path):
    """bill_of_materials is a list when include_bom is True."""
    d = guide_to_dict(build_guide(str(bialetti_path), include_bom=True))
    assert isinstance(d["bill_of_materials"], list)


def test_optional_fields_present_as_null_not_omitted(bialetti_path):
    """
    An optional field with no value must be present as null, not omitted.
    Bialetti's actions have no image -> the 'image' key exists and is null.
    """
    d = guide_to_dict(build_guide(str(bialetti_path)))
    action = d["steps"][0]["actions"][0]
    assert "image" in action
    assert action["image"] is None


def test_terminal_step_continues_as_is_empty_list(bialetti_path):
    """
    Schema 1.1: continues_as is a LIST of continuing composites. The final step
    continues into nothing -> an empty list (not null, not a scalar). Bialetti is
    a linear chain, so its last step is terminal.
    """
    d = guide_to_dict(build_guide(str(bialetti_path)))
    last = d["steps"][-1]["continues_as"]
    assert isinstance(last, list)
    assert last == []


# =============================================================================
# Image shape and URL classification (synthetic graph: needs images + steps).
# =============================================================================

def _graph_with_images() -> DisassemblyGraph:
    """A minimal grammatical graph carrying both a local path and an http URL."""
    nodes = [
        GraphNode(id=1, type=NodeType.COMPONENT, text="Product", x=0, y=0,
                  weight="100", image_path="images/product.jpg"),
        GraphNode(id=2, type=NodeType.DIAMOND, text="Open", x=0, y=1),
        GraphNode(id=3, type=NodeType.ACTION, text="Unscrew the panel", x=1, y=1,
                  image_path="https://example.com/step.jpg"),
        GraphNode(id=4, type=NodeType.COMPONENT, text="Panel", x=0, y=2,
                  weight="100", image_path="images/panel.jpg"),
    ]
    edges = [Edge(src=1, dst=2), Edge(src=2, dst=3), Edge(src=2, dst=4)]
    node_map = {n.id: n for n in nodes}
    out_acc, inc_acc = {}, {}
    for e in edges:
        out_acc.setdefault(e.src, []).append(e.dst)
        inc_acc.setdefault(e.dst, []).append(e.src)
    return DisassemblyGraph(
        nodes=node_map, edges=tuple(edges),
        out_adj={n: tuple(out_acc.get(n, ())) for n in node_map},
        inc_adj={n: tuple(inc_acc.get(n, ())) for n in node_map},
    )


def test_image_local_path_classified_not_url(monkeypatch, tmp_path):
    """A local/relative image path must serialize as {path, is_url: False}."""
    guide = _guide_from_graph(_graph_with_images())
    d = guide_to_dict(guide)
    action_img = d["steps"][0]["actions"][0]["image"]
    assert action_img == {"path": "https://example.com/step.jpg", "is_url": True}
    output_img = d["steps"][0]["outputs"][0]["image"]
    assert output_img == {"path": "images/panel.jpg", "is_url": False}


def _guide_from_graph(graph):
    """Assemble a Guide from an in-memory graph (bypassing file load)."""
    from disassembly_loader import linearizer, validation
    from disassembly_loader.models import Guide
    steps = linearizer.linearize(graph, DepthSpec(mode=DepthMode.FULL))
    product = builder._build_product(graph)
    return Guide(product=product, steps=steps,
                 warnings=tuple(validation.validate(graph)),
                 depth=DepthSpec(mode=DepthMode.FULL))


def test_product_image_serialized(bialetti_path):
    """The product image field is present (null for Bialetti, which has none)."""
    d = guide_to_dict(build_guide(str(bialetti_path)))
    assert "image" in d["product"]


# =============================================================================
# Serialization properties: ascii-safe, valid JSON, round-trippable.
# =============================================================================

def test_emit_json_is_valid_and_roundtrips(bialetti_path):
    """emit_json must produce valid JSON that parses back to the same dict."""
    guide = build_guide(str(bialetti_path), include_bom=True)
    text = emit_json(guide)
    parsed = json.loads(text)
    assert parsed == guide_to_dict(guide)


def test_emit_json_is_ascii_safe(bialetti_path):
    """Output must be ASCII-safe (ensure_ascii) for downstream tooling safety."""
    text = emit_json(build_guide(str(bialetti_path)))
    assert text == text.encode("ascii", "ignore").decode("ascii")


def test_warning_severity_serialized_as_string(nespresso_path):
    """Warnings must serialize severity as its string value, with node_ids list."""
    d = guide_to_dict(build_guide(str(nespresso_path)))
    assert d["warnings"], "nespresso should have warnings"
    w = d["warnings"][0]
    assert w["severity"] in ("info", "warning", "error")
    assert isinstance(w["node_ids"], list)


def test_write_json_creates_readable_file(bialetti_path, tmp_path):
    """write_json must create a file that reads back as the same IR."""
    from disassembly_loader import write_json
    out = tmp_path / "ir.json"
    guide = build_guide(str(bialetti_path), include_bom=True)
    write_json(guide, str(out))
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == guide.schema_version
    assert len(parsed["steps"]) == len(guide.steps)

# =============================================================================
# Schema 1.1 fields: input links steps, tools is the guide-level union.
# =============================================================================

def test_step_input_links_the_chain(bialetti_path):
    """
    Schema 1.1: step.input is the component the operation is performed on. On a
    linear chain each step's input must equal the previous step's single
    continuation — this is what lets a generator narrate "now disassembling X"
    and what makes a branched guide reconstructable by node_id (not list order).
    """
    d = guide_to_dict(build_guide(str(bialetti_path)))
    steps = d["steps"]
    for k in range(1, len(steps)):
        prev_cont = steps[k - 1]["continues_as"]
        assert prev_cont, "a non-terminal step must have a continuation"
        assert steps[k]["input"]["node_id"] == prev_cont[0]["node_id"]


def test_top_level_tools_is_union_of_step_tools(bialetti_path):
    """
    Schema 1.1: the guide-level `tools` is the case-insensitive union of every
    step's tools_required, computed once so the 7 generators need not. Bialetti
    models tools, so the union is non-empty.
    """
    d = guide_to_dict(build_guide(str(bialetti_path)))
    top = {t.casefold() for t in d["tools"]}
    from_steps = {t.casefold() for s in d["steps"] for t in s["tools_required"]}
    assert top == from_steps
    assert top, "Bialetti models tools; the union must be non-empty"


def test_branched_input_comes_from_an_earlier_continuation(airfryer_path):
    """
    Schema 1.1 on a BRANCHED model (air fryer): every step after the first must
    take as input a component that appeared as a continuation of some earlier
    step. This pins that the branch structure is reconstructable purely from the
    input.node_id <-> continues_as.node_id relation, without relying on list
    adjacency.
    """
    d = guide_to_dict(build_guide(str(airfryer_path)))
    steps = d["steps"]
    continuations = {c["node_id"] for s in steps for c in s["continues_as"]}
    root_input = steps[0]["input"]["node_id"]
    for s in steps[1:]:
        assert s["input"]["node_id"] in continuations or s["input"]["node_id"] == root_input