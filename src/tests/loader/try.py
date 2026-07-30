"""
try.py — a small script to see the loader in action (schema 1.1).

Run it from the project root (the folder that contains `disassembly_loader/`):

    python try.py                          # uses default fixtures
    python try.py path/to/your_model.json  # try your own model

It runs the full pipeline on a model and prints the guide in a readable form:
the product, the guide-level tools, every step (what it acts on, its
instructions, the parts obtained and the ones that continue), any warnings, and
the bill of materials.
"""

import sys

from disassembly_loader import build_guide, DepthSpec, DepthMode, UnparsableModelError


def show(path: str) -> None:
    print(f"\nLoading: {path}")
    print("=" * 70)

    try:
        guide = build_guide(path, include_bom=True)
    except UnparsableModelError as exc:
        print(f"Could not read this model: {exc}")
        return

    # --- product -------------------------------------------------------------
    p = guide.product
    weight = f"{p.weight} {p.weight_unit or ''}".strip() if p.weight else "unknown weight"
    print(f"PRODUCT: {p.name}  ({weight})")
    print(f"SCHEMA VERSION: {guide.schema_version}")
    print(f"DEPTH: {guide.depth.mode.value}")
    if guide.tools:
        print(f"TOOLS (whole guide): {', '.join(guide.tools)}")

    # --- steps ---------------------------------------------------------------
    print(f"\nSTEPS: {len(guide.steps)}")
    for s in guide.steps:
        print(f"\n  {s.index}. {s.operation}")
        # schema 1.1: the component the operation is performed on
        print(f"       on: {s.input.name}")
        if s.actions:
            for a in s.actions:
                tool = f"  [tool: {a.tools}]" if a.tools else ""
                print(f"       - {a.text}{tool}")
        else:
            print("       (no separate instructions — the operation name is the step)")
        if s.outputs:
            parts = []
            for o in s.outputs:
                tag = f" (kept whole, {o.contained_leaf_count} parts inside)" if o.kept_whole else ""
                parts.append(o.name + tag)
            print(f"       => produces: {', '.join(parts)}")
        # schema 1.1: continues_as is a LIST of continuing components (possibly
        # several, on a branched model; empty on a terminal step)
        if s.continues_as:
            names = ", ".join(c.name for c in s.continues_as)
            print(f"       .. continues as: {names}")

    # --- warnings ------------------------------------------------------------
    print(f"\nWARNINGS: {len(guide.warnings)}")
    for w in guide.warnings:
        ids = ", ".join(str(i) for i in w.node_ids)
        where = f" (nodes {ids})" if ids else ""
        print(f"  [{w.severity.value.upper()}] {w.rule}{where}")
        print(f"        {w.message}")

    # --- bill of materials ---------------------------------------------------
    if guide.bill_of_materials:
        print(f"\nBILL OF MATERIALS: {len(guide.bill_of_materials)} leaf parts")
        total = 0.0
        for c in guide.bill_of_materials:
            w = f"{c.weight} {c.weight_unit or ''}".strip() if c.weight else "?"
            print(f"  - {c.name}: {w}")
            if c.weight:
                total += c.weight
        if total:
            print(f"  total: {total:g}")

    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show(sys.argv[1])
    else:
        # no argument: run a couple of contrasting fixtures so you see variety
        defaults = [
            "tests/fixtures/BialettiGioia.json",              # clean, linear chain
            "tests/fixtures/Air_fryer_Philips_HD9252.json",  # branching + no-action diamonds
        ]
        for d in defaults:
            show(d)
        print("\nTip: pass your own file  ->  python try.py path/to/model.json")