"""
test_schema.py — the IR output must conform to the documented JSON Schema.

This is the anti-drift guard. The IR exists in three places that must agree: the
dataclasses (models.py), the emitter's JSON (emitter.py), and the documented
contract (ir_schema.json). If any drifts — a field added to a dataclass but not
the schema, or vice versa — these tests go red. The schema stops being
documentation that rots and becomes a verified constraint.

Requires the `jsonschema` package (a dev/test dependency, not needed at runtime).
"""

import json
from pathlib import Path

import pytest

import disassembly_loader as dl
from disassembly_loader import DepthMode, DepthSpec

jsonschema = pytest.importorskip("jsonschema")  # skip cleanly if not installed

SCHEMA_PATH = Path(dl.__file__).parent / "ir_schema.json"


@pytest.fixture(scope="module")
def schema():
    """Load the JSON Schema once for the module."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_itself_valid(schema):
    """The schema document must be a valid Draft 2020-12 schema."""
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    "fixture_name",
    ["bialetti_path", "maria_path", "nespresso_path", "capsule_path",
     "washing_machine_path", "epson_path", "dishwasher_path", "oranfresh_path",
     "airfryer_path"],
)
def test_ir_output_conforms_to_schema(fixture_name, request, schema):
    """
    Every fixture's IR output (with BoM) must validate against the schema. This
    runs the full pipeline and checks the contract end to end, for clean and
    malformed graphs alike.
    """
    path = request.getfixturevalue(fixture_name)
    guide = dl.build_guide(str(path), include_bom=True)
    instance = dl.guide_to_dict(guide)
    jsonschema.validate(instance, schema)


def test_ir_conforms_under_each_depth_mode(bialetti_path, schema):
    """The contract must hold under every depth mode, not just the default."""
    for spec in (
        DepthSpec(mode=DepthMode.FULL),
        DepthSpec(mode=DepthMode.KEEP_MAIN),
    ):
        guide = dl.build_guide(str(bialetti_path), depth=spec, include_bom=True)
        jsonschema.validate(dl.guide_to_dict(guide), schema)


def test_ir_conforms_without_bom(bialetti_path, schema):
    """The contract must hold when the BoM is null (not requested)."""
    guide = dl.build_guide(str(bialetti_path), include_bom=False)
    instance = dl.guide_to_dict(guide)
    assert instance["bill_of_materials"] is None
    jsonschema.validate(instance, schema)