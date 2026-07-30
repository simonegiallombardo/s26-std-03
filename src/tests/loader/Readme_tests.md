# Tests

How the loader is tested, and how to check it yourself. You do not need to read
this to *use* the library (see [`README.md`](README.md)) — it is here so anyone
can verify the library behaves as documented. Put Tests_loader in the same space as disassembly_loader of "ModuleNotFound" will araise.

---

## Running the suite

From the folder that contains `disassembly_loader/` and `tests/`:

```bash
pip3 install pytest jsonschema     # once
python3 -m pytest                  # run everything
```

Useful variants:

```bash
python3 -m pytest -v                       # list every test by name
python3 -m pytest tests/test_linearizer.py # just one file
python3 -m pytest -k mass_balance          # just tests matching a keyword
```

A green run currently reports **94 passed**.

Requirements: `pytest` runs the tests; `jsonschema` is used only by the schema
tests (if it is missing, those are skipped, not failed).

---

## How the suite is organized

One test file per module of the library, plus a shared fixtures file:

| File                   | Tests | What it checks                                                        |
|------------------------|-------|----------------------------------------------------------------------|
| `test_adapter.py`      | 12    | Format normalization: edges read from either storage, field-name and weight-type differences absorbed, unparsable inputs rejected cleanly. |
| `test_models.py`       | 9     | The data types: immutability (`frozen`), tuple collections, depth spec rules. |
| `test_validation.py`   | 19    | Every grammar/topology rule fires when it should and stays silent when it should not (no false positives on clean models). |
| `test_linearizer.py`   | 18    | The traversal: one step per operation, action chains and fan-outs collected, depth cuts, output branching, cycles handled. |
| `test_builder.py`      | 7     | The whole pipeline assembles a correct guide; bill of materials is leaf-only and mass-conserving. |
| `test_emitter.py`      | 15    | The JSON contract: exact keys, explicit nulls, images, the 1.1 fields (`input`, `tools`), round-tripping. |
| `test_schema.py`       | 4     | Every produced output validates against the formal `ir_schema.json` — the guard that keeps code and contract from drifting apart. |

The `tests/fixtures/` folder holds real Builder graphs used as inputs (see the
next section). `tests/conftest.py` exposes them to the tests as reusable
fixtures.

---

## The test data (fixtures)

The suite runs against **real disassembly graphs**, not toy data — including
several that were deliberately added to stress specific situations. Each one
exercises something different:

| Fixture                              | What makes it interesting                                        |
|--------------------------------------|------------------------------------------------------------------|
| `BialettiGioia.json`                 | Clean reference: all weights present, mass balances exactly, linear chain. |
| `coffee_machine_maria.json`          | Clean, but no weights at all — mass balance is *not verifiable*.  |
| `Epson_Printer.json`                 | Large (112 nodes); contains forbidden component→two-diamonds anomalies. |
| `nespresso.json`                     | Malformed: actions used as hubs; the root never reaches an operation → empty-but-warned guide. |
| `capsule-coffee-machine.json`        | Contains a cycle and an over-connected action.                   |
| `washing_machine_disassembly.json`   | Operations wired without instructions and without outputs (genuinely empty diamonds). |
| `Dishwasher_LG_LDF5545ST.json`       | Has a fully isolated node — an orphan that must not be mistaken for a second root. |
| `Oranfresh_gruppo_spremitura_1.json` | Diamonds whose instructions are a **fan-out** (several actions directly under each diamond). |
| `Air_fryer_Philips_HD9252.json`      | Well-formed, with real **output branching** and **self-explanatory** diamonds (no instructions). |
| `NespressoMini_fixed_v2.json`        | A corrected model where every operation is properly formed.       |

---

## What the tests prove (in plain terms)

Beyond "the code runs", the suite pins down the behaviors the library promises:

- **It never crashes on a readable model.** Even the malformed fixtures produce a
  guide plus warnings; only truly unparsable input raises an error.
- **It never silently loses information.** Regression tests guard the cases that
  once did — e.g. fan-out instructions that were dropped, or a branch of the
  disassembly that went unfollowed.
- **The output always matches the contract.** Every fixture's output is validated
  against `ir_schema.json`, so the code cannot drift from the documented format
  without a test turning red.
- **Clean models stay clean.** Rules that flag anomalies are checked to *not*
  fire on well-formed graphs, so warnings mean something.

---

## The demo scripts

`tests/try.py` and `tests/make_ir.py` are not tests — they are small runnable
demos kept next to the tests:

```bash
python3 tests/try.py tests/fixtures/BialettiGioia.json     # prints the guide
python3 tests/make_ir.py tests/fixtures/BialettiGioia.json # writes the JSON output
```

Run them from the project root (the folder containing `disassembly_loader/`).