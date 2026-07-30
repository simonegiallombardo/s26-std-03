"""

conftest.py — shared pytest fixtures for the load-phase test suite.

pytest loads this file automatically. Any function decorated with
`@pytest.fixture` here becomes available to every test in this directory simply
by naming it as a test parameter — no import needed. That is pytest's
dependency-injection mechanism: a test asks for a fixture by parameter name,
pytest runs the fixture and passes in its return value.

We use the five REAL Builder JSON files as fixtures rather than hand-written
toy graphs. They are authoritative: two are well-formed (Bialetti, Maria) and
three are real malformed v1 graphs from teammates (nespresso, capsule,
washing_machine), each broken in a different way. Testing against real inputs
means our tests assert on behaviour that actually has to work, not on cases we
imagined.
"""

from pathlib import Path

import pytest

from disassembly_loader import adapter

# Directory holding the real JSON fixtures, resolved relative to THIS file so
# the suite runs from any working directory.
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# -- Path fixtures: give a test the path to a specific file -------------------
# These are tiny, but having them as fixtures (rather than hard-coded strings in
# each test) means if the fixture layout ever moves, we change it in one place.

@pytest.fixture
def bialetti_path() -> Path:
    """Path to the well-formed Bialetti graph (edges in `connections`)."""
    return FIXTURES_DIR / "BialettiGioia.json"


@pytest.fixture
def maria_path() -> Path:
    """Path to the well-formed Maria graph (edges as `arrow` shapes)."""
    return FIXTURES_DIR / "coffee_machine_maria.json"


@pytest.fixture
def nespresso_path() -> Path:
    """Path to the malformed nespresso graph (action-as-fan-out-hub)."""
    return FIXTURES_DIR / "nespresso.json"


@pytest.fixture
def capsule_path() -> Path:
    """Path to the malformed capsule graph (cycle + multi-degree action)."""
    return FIXTURES_DIR / "capsule-coffee-machine.json"


@pytest.fixture
def washing_machine_path() -> Path:
    """Path to the structurally clean but semantically sparse washing graph."""
    return FIXTURES_DIR / "washing_machine_disassembly.json"


@pytest.fixture
def epson_path() -> Path:
    """Path to the large, well-formed Epson graph (112 nodes; 5 diamond->diamond)."""
    return FIXTURES_DIR / "Epson_Printer.json"


@pytest.fixture
def dishwasher_path() -> Path:
    """Path to the LG dishwasher graph: the only fixture with a fully isolated
    node (an orphan that must NOT be mistaken for a second root)."""
    return FIXTURES_DIR / "Dishwasher_LG_LDF5545ST.json"


@pytest.fixture
def oranfresh_path() -> Path:
    """Path to the Oranfresh juicer group graph: the only fixture whose diamonds
    list their instructions as a FAN-OUT (several action children directly off
    each diamond) instead of a chain."""
    return FIXTURES_DIR / "Oranfresh_gruppo_spremitura_1.json"


@pytest.fixture
def airfryer_path() -> Path:
    """Path to the Philips air fryer graph: the only well-formed fixture that
    exercises real output branching (diamonds with several continuing composites)
    and self-explanatory diamonds (operations with no action instructions)."""
    return FIXTURES_DIR / "Air_fryer_Philips_HD9252.json"


# -- Graph fixtures: give a test an already-normalized DisassemblyGraph --------
# Most tests want the normalized graph, not the raw path. These fixtures depend
# on the path fixtures above (a fixture can request another fixture as a
# parameter, exactly like a test does) and return the adapter's output.

@pytest.fixture
def bialetti_graph(bialetti_path):
    """The Bialetti file, normalized through the adapter."""
    return adapter.normalize_file(bialetti_path)


@pytest.fixture
def maria_graph(maria_path):
    """The Maria file, normalized through the adapter."""
    return adapter.normalize_file(maria_path)


@pytest.fixture
def nespresso_graph(nespresso_path):
    """The nespresso file, normalized through the adapter."""
    return adapter.normalize_file(nespresso_path)
