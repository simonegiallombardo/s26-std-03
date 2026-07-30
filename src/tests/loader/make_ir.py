"""
make_ir.py — produce the IR JSON file (the loader's real output).

Run from the project root:

    python make_ir.py tests/fixtures/BialettiGioia.json
    python make_ir.py tests/fixtures/BialettiGioia.json out/bialetti.json

The first argument is the input model. The second (optional) is where to write
the IR JSON; if omitted, it writes <inputname>_ir.json next to this script.
Unlike try_loader.py (which only prints), this WRITES A FILE and tells you where.
"""

import os
import sys

from disassembly_loader import build_ir_file, UnparsableModelError


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python make_ir.py <input_model.json> [output_ir.json]")
        return

    source = sys.argv[1]

    # Decide the output path: given as arg 2, or derived from the input name.
    if len(sys.argv) >= 3:
        out_path = sys.argv[2]
    else:
        base = os.path.splitext(os.path.basename(source))[0]
        out_path = f"{base}_ir.json"

    # Make sure the target folder exists (if an output folder was given).
    folder = os.path.dirname(out_path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    try:
        build_ir_file(source, out_path, include_bom=True)
    except UnparsableModelError as exc:
        print(f"Could not read the model: {exc}")
        return

    full = os.path.abspath(out_path)
    size = os.path.getsize(full)
    print(f"IR written to: {full}  ({size} bytes)")


if __name__ == "__main__":
    main()