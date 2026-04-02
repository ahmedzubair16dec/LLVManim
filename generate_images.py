#!/usr/bin/env python3
"""
generate_images.py  —  Regenerate all paper figures from source files.

Sources handled:
  draw.io files →  xvfb-run drawio --export --format pdf  (native, full fidelity)
  PlantUML      →  plantuml -tsvg → PDF via cairosvg
  Plain SVGs    →  cairosvg → PDF  (graphviz, etc.)

Outputs written to images/ (relative to this script's directory):
  01_architecture_overview_vertical.pdf
  05_cli_dispatch.pdf
  04_data_model.pdf
  CFG.pdf
  04a_literal_types.pdf
  04b_ingest_layer.pdf
  04c_transform_layer.pdf
  04d_render_layer.pdf

Usage:
  python3 generate_images.py
"""

import atexit
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import cairosvg  # type: ignore[import-untyped]
except ImportError:
    sys.exit("cairosvg not found. Install with: pip install --break-system-packages cairosvg")

REPO = Path(__file__).parent
IMAGES = REPO / "images"
SVG_NS = "http://www.w3.org/2000/svg"


# ─────────────────────────────────────────────────────────────────────────────
# Virtual display (needed for draw.io headless export)
# ─────────────────────────────────────────────────────────────────────────────

def _start_xvfb() -> str:
    """Start Xvfb on :99 if not already running. Returns the DISPLAY string."""
    import time
    display = ":99"
    proc = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    atexit.register(proc.terminate)
    time.sleep(2)  # give Xvfb time to initialise
    return display


# ─────────────────────────────────────────────────────────────────────────────
# draw.io helper
# ─────────────────────────────────────────────────────────────────────────────

def drawio_to_pdf(src: Path, dst: Path, page_index: int = 0, display: str = ":99") -> None:
    """Export a .drawio file to PDF using the draw.io CLI."""
    env: dict[str, str] = {**os.environ, "DISPLAY": display}
    result = subprocess.run(
        [
            "drawio",
            "--export",
            "--format", "pdf",
            "--page-index", str(page_index),
            "--output", str(dst),
            str(src),
        ],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        sys.exit(f"  ERROR: drawio exited {result.returncode}:\n{result.stderr[:400]}")
    if not dst.exists():
        sys.exit(f"  ERROR: drawio did not produce {dst}")


# ─────────────────────────────────────────────────────────────────────────────
# PlantUML + plain SVG helpers
# ─────────────────────────────────────────────────────────────────────────────

def _remove_watermark(root: ET.Element) -> int:
    removed = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag != f"{{{SVG_NS}}}switch":
                continue
            text_content = "".join(child.itertext())
            if "Text is not SVG" in text_content or "cannot display" in text_content.lower():
                parent.remove(child)
                removed += 1
    return removed


def svg_to_pdf(svg: Path, pdf: Path) -> None:
    cairosvg.svg2pdf(url=str(svg), write_to=str(pdf))  # type: ignore[attr-defined]


def plantuml_to_pdf(puml: Path, pdf: Path) -> None:
    """Run plantuml → SVG, strip watermark (if any), convert to PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["plantuml", "-tsvg", "-o", tmpdir, str(puml)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  WARNING: plantuml exited {result.returncode}: {result.stderr[:200]}")

        svg_out = Path(tmpdir) / (puml.stem + ".svg")
        if not svg_out.exists():
            sys.exit(f"  ERROR: plantuml did not produce {svg_out}")

        ET.register_namespace("", SVG_NS)
        tree = ET.parse(svg_out)
        wm = _remove_watermark(tree.getroot())
        if wm:
            tree.write(svg_out, xml_declaration=True, encoding="unicode")
            print(f"  removed {wm} watermark(s)")

        svg_to_pdf(svg_out, pdf)


# ─────────────────────────────────────────────────────────────────────────────
# Build steps
# ─────────────────────────────────────────────────────────────────────────────

def step(label: str, dst: Path) -> None:
    print(f"\n→ {label}")
    print(f"  out: {dst.relative_to(REPO)}")


def main() -> None:
    arch = IMAGES / "architecture"
    display = _start_xvfb()

    # ── 1. 01_architecture_overview_vertical.pdf ─────────────────────────────
    step("01_architecture_overview_vertical (draw.io → PDF)",
         IMAGES / "01_architecture_overview_vertical.pdf")
    drawio_to_pdf(
        arch / "01_architecture_overview" / "Vertical" / "01_architecture_overview.drawio",
        IMAGES / "01_architecture_overview_vertical.pdf",
        display=display,
    )

    # ── 2. 05_cli_dispatch.pdf ────────────────────────────────────────────────
    step("05_cli_dispatch (draw.io → PDF)",
         IMAGES / "05_cli_dispatch.pdf")
    drawio_to_pdf(
        arch / "05_cli_dispatch" / "05_cli_dispatch.drawio",
        IMAGES / "05_cli_dispatch.pdf",
        display=display,
    )

    # ── 3. 04_data_model.pdf  (page 0 = "04 Core Data Model (UML)") ──────────
    step("04_data_model (draw.io → PDF, page 0)",
         IMAGES / "04_data_model.pdf")
    drawio_to_pdf(
        arch / "04_data_model" / "04_data_model.drawio",
        IMAGES / "04_data_model.pdf",
        page_index=0,
        display=display,
    )

    # ── 4. CFG.pdf  (graphviz SVG) ────────────────────────────────────────────
    step("CFG (graphviz SVG → PDF)", IMAGES / "CFG.pdf")
    svg_to_pdf(IMAGES / "CFG.svg", IMAGES / "CFG.pdf")

    # ── 5–8. PlantUML per-layer diagrams ──────────────────────────────────────
    puml_dir = IMAGES / "plantuml"
    for stem in ("04a_literal_types", "04b_ingest_layer", "04c_transform_layer", "04d_render_layer"):
        step(f"{stem} (PlantUML → SVG → PDF)", IMAGES / f"{stem}.pdf")
        plantuml_to_pdf(puml_dir / f"{stem}.puml", IMAGES / f"{stem}.pdf")

    print("\n✓ All images generated successfully.")


if __name__ == "__main__":
    main()
