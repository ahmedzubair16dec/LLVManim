"""Generate LLVManim metrics charts and save them to docs/metrics/.

Run from the repository root:
    uv run python docs/metrics/generate_metrics.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

OUT = Path(__file__).parent

# ── Palette ────────────────────────────────────────────────────────────────────
LAYER_COLORS = {
    "cli": "#e67e22",
    "ingest": "#2980b9",
    "transform": "#8e44ad",
    "render": "#27ae60",
}
COVERAGE_COLORS = {
    "high": "#27ae60",  # >= 95 %
    "medium": "#f39c12",  # 80-94 %
    "low": "#e74c3c",  # < 80 %
}
BG = "#f8f9fa"


def _layer(path: str) -> str:
    for layer in ("cli", "ingest", "transform", "render"):
        if f"/{layer}/" in path or path.endswith(f"/{layer}"):
            return layer
    return "other"


def _cov_color(pct: int) -> str:
    if pct >= 95:
        return COVERAGE_COLORS["high"]
    if pct >= 80:
        return COVERAGE_COLORS["medium"]
    return COVERAGE_COLORS["low"]


# ── Raw data ───────────────────────────────────────────────────────────────────

# (module_short_name, layer, stmts, missed, coverage_pct)
COVERAGE_DATA = [
    ("cli/main", "cli", 212, 16, 92),
    ("ingest/analysis_metadata", "ingest", 53, 0, 100),
    ("ingest/cfg_edge_io", "ingest", 52, 1, 98),
    ("ingest/display_lines", "ingest", 39, 0, 100),
    ("ingest/dot_layout", "ingest", 96, 1, 99),
    ("ingest/llvm_events", "ingest", 54, 0, 100),
    ("ingest/trace_io", "ingest", 52, 0, 100),
    ("render/cfg_animation_scene", "render", 110, 8, 93),
    ("render/cfg_renderer", "render", 95, 36, 62),
    ("render/command_driven", "render", 33, 0, 100),
    ("render/graphviz_export", "render", 81, 1, 99),
    ("render/json_export", "render", 20, 1, 95),
    ("render/ssa_formatting", "render", 40, 0, 100),
    ("render/stack_renderer", "render", 273, 143, 48),
    ("transform/models", "transform", 85, 0, 100),
    ("transform/scene", "transform", 136, 1, 99),
    ("transform/trace", "transform", 39, 1, 97),
]

# (test_file_short, layer, count)
TEST_DATA = [
    ("cli/test_main", "cli", 43),
    ("render/test_ssa_formatting", "render", 30),
    ("transform/test_scene_graph", "transform", 29),
    ("ingest/test_llvm_events", "ingest", 23),
    ("render/test_stack_renderer", "render", 21),
    ("ingest/test_dot_layout", "ingest", 20),
    ("render/test_exports", "render", 18),
    ("ingest/test_trace_io", "ingest", 18),
    ("render/test_cmd_driven", "render", 15),
    ("ingest/test_cfg_edge_io", "ingest", 13),
    ("ingest/test_analysis_meta", "ingest", 13),
    ("render/test_rich_ssa", "render", 12),
    ("ingest/test_display_lines", "ingest", 11),
    ("render/test_cfg_animation", "render", 10),
    ("render/test_cfg_renderer", "render", 7),
    ("transform/test_trace", "transform", 6),
    ("test_entrypoints", "cli", 4),
    ("render/test_rich_helpers", "render", 3),
    ("test_pipeline", "transform", 1),
    ("cli/test_import_fallback", "cli", 1),
]

# (module_short_name, layer, total_lines)
LOC_DATA = [
    ("stack_renderer", "render", 504),
    ("cli/main", "cli", 461),
    ("transform/scene", "transform", 349),
    ("cfg_animation", "render", 224),
    ("ingest/dot_layout", "ingest", 208),
    ("cfg_renderer", "render", 188),
    ("transform/models", "transform", 174),
    ("graphviz_export", "render", 139),
    ("ingest/llvm_events", "ingest", 139),
    ("ssa_formatting", "render", 134),
    ("analysis_metadata", "ingest", 126),
    ("cfg_edge_io", "ingest", 124),
    ("trace_io", "ingest", 115),
    ("cmd_driven_scene", "render", 85),
    ("json_export", "render", 75),
    ("transform/trace", "transform", 72),
    ("display_lines", "ingest", 72),
]


# ══════════════════════════════════════════════════════════════════════════════
# Chart 1 — Coverage per module (horizontal bar)
# ══════════════════════════════════════════════════════════════════════════════
def chart_coverage() -> None:
    data = sorted(COVERAGE_DATA, key=lambda r: r[2])  # sort by stmts
    names = [r[0] for r in data]
    pcts = [r[4] for r in data]
    colors = [_cov_color(p) for p in pcts]
    lcolors = [LAYER_COLORS[r[1]] for r in data]

    fig, ax = plt.subplots(figsize=(11, 8), facecolor=BG)
    ax.set_facecolor(BG)

    bars = ax.barh(names, pcts, color=colors, edgecolor="white", linewidth=0.6, height=0.65)

    # Layer-colored left spine strips
    for i, lc in enumerate(lcolors):
        ax.barh(i, 2, left=-2, color=lc, height=0.65, clip_on=False)

    for bar, pct in zip(bars, pcts, strict=False):
        ax.text(
            min(pct + 1, 97),
            bar.get_y() + bar.get_height() / 2,
            f"{pct}%",
            va="center",
            ha="left",
            fontsize=9,
            color="#333",
        )

    ax.set_xlim(0, 105)
    ax.set_xlabel("Coverage (%)", fontsize=11)
    ax.set_title("LLVManim — Test Coverage by Module", fontsize=13, fontweight="bold", pad=12)
    ax.axvline(80, color="#c0392b", linewidth=1.2, linestyle="--", alpha=0.7, label="80% threshold")
    ax.axvline(95, color="#f39c12", linewidth=1.0, linestyle=":", alpha=0.7, label="95% threshold")

    patches = [
        mpatches.Patch(color=LAYER_COLORS[label], label=label)
        for label in ("cli", "ingest", "transform", "render")
    ]
    patches += [
        mpatches.Patch(color=COVERAGE_COLORS["high"], label=">= 95%"),
        mpatches.Patch(color=COVERAGE_COLORS["medium"], label="80-94%"),
        mpatches.Patch(color=COVERAGE_COLORS["low"], label="< 80%"),
    ]
    ax.legend(
        handles=patches,
        loc="lower right",
        fontsize=9,
        framealpha=0.9,
        title="Layer / Coverage",
        title_fontsize=9,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=9)
    ax.set_xlim(-2, 108)
    fig.tight_layout()
    fig.savefig(OUT / "01_coverage_by_module.png", dpi=150)
    plt.close(fig)
    print("Wrote 01_coverage_by_module.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 2 — Tests per file (horizontal bar, grouped by layer)
# ══════════════════════════════════════════════════════════════════════════════
def chart_tests() -> None:
    data = sorted(TEST_DATA, key=lambda r: r[2])
    names = [r[0] for r in data]
    counts = [r[2] for r in data]
    colors = [LAYER_COLORS[r[1]] for r in data]

    fig, ax = plt.subplots(figsize=(11, 8), facecolor=BG)
    ax.set_facecolor(BG)

    bars = ax.barh(names, counts, color=colors, edgecolor="white", linewidth=0.6, height=0.65)
    for bar, n in zip(bars, counts, strict=False):
        ax.text(
            bar.get_width() + 0.4,
            bar.get_y() + bar.get_height() / 2,
            str(n),
            va="center",
            fontsize=9,
            color="#333",
        )

    total = sum(counts)
    ax.set_title(
        f"LLVManim — Tests per Module  (total: {total})", fontsize=13, fontweight="bold", pad=12
    )
    ax.set_xlabel("Test count", fontsize=11)

    patches = [
        mpatches.Patch(color=LAYER_COLORS[label], label=label)
        for label in ("cli", "ingest", "transform", "render")
    ]
    ax.legend(handles=patches, loc="lower right", fontsize=9, framealpha=0.9, title="Layer")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "02_tests_per_module.png", dpi=150)
    plt.close(fig)
    print("Wrote 02_tests_per_module.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 3 — Source lines of code distribution (pie + horizontal bar side-by-side)
# ══════════════════════════════════════════════════════════════════════════════
def chart_loc() -> None:
    # Layer aggregates for pie
    layer_totals: dict[str, int] = {}
    for _, layer, lines in LOC_DATA:
        layer_totals[layer] = layer_totals.get(layer, 0) + lines

    fig, (ax_pie, ax_bar) = plt.subplots(1, 2, figsize=(13, 6), facecolor=BG)
    fig.patch.set_facecolor(BG)

    # Pie — layer breakdown
    labels = list(layer_totals.keys())
    sizes = list(layer_totals.values())
    pie_colors = [LAYER_COLORS[label] for label in labels]
    wedges, texts, autotexts = ax_pie.pie(
        sizes,
        labels=labels,
        colors=pie_colors,
        autopct="%1.0f%%",
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=1.5),
    )
    for t in autotexts:
        t.set_fontsize(11)
        t.set_fontweight("bold")
        t.set_color("white")
    for t in texts:
        t.set_fontsize(11)
    total_lines = sum(sizes)
    ax_pie.set_title(
        f"Lines of Code by Layer\n(total: {total_lines})", fontsize=12, fontweight="bold", pad=10
    )

    # Bar — per-module breakdown
    data = sorted(LOC_DATA, key=lambda r: r[2])
    names = [r[0] for r in data]
    counts = [r[2] for r in data]
    bar_colors = [LAYER_COLORS[r[1]] for r in data]

    ax_bar.set_facecolor(BG)
    bars = ax_bar.barh(
        names, counts, color=bar_colors, edgecolor="white", linewidth=0.6, height=0.65
    )
    for bar, n in zip(bars, counts, strict=False):
        ax_bar.text(
            bar.get_width() + 3,
            bar.get_y() + bar.get_height() / 2,
            str(n),
            va="center",
            fontsize=8.5,
            color="#333",
        )

    ax_bar.set_xlabel("Lines of Code", fontsize=11)
    ax_bar.set_title("Source Lines per Module", fontsize=12, fontweight="bold", pad=10)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.tick_params(axis="y", labelsize=8.5)

    patches = [
        mpatches.Patch(color=LAYER_COLORS[label], label=label)
        for label in ("cli", "ingest", "transform", "render")
    ]
    ax_bar.legend(handles=patches, loc="lower right", fontsize=9, framealpha=0.9)

    fig.tight_layout(pad=2)
    fig.savefig(OUT / "03_lines_of_code.png", dpi=150)
    plt.close(fig)
    print("Wrote 03_lines_of_code.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 4 — Module size vs. coverage scatter
# ══════════════════════════════════════════════════════════════════════════════
def chart_size_vs_coverage() -> None:
    fig, ax = plt.subplots(figsize=(10, 7), facecolor=BG)
    ax.set_facecolor(BG)

    for name, layer, stmts, _missed, pct in COVERAGE_DATA:
        color = LAYER_COLORS[layer]
        ax.scatter(
            stmts,
            pct,
            s=stmts * 1.4,
            color=color,
            alpha=0.70,
            edgecolors="white",
            linewidths=1.0,
            zorder=3,
        )
        # Only label points that are notable (large or low coverage)
        if stmts > 100 or pct < 70:
            ax.annotate(
                name.split("/")[-1],
                (stmts, pct),
                textcoords="offset points",
                xytext=(6, 4),
                fontsize=8.5,
                color="#333",
            )

    ax.axhline(80, color="#c0392b", linewidth=1.2, linestyle="--", alpha=0.7, label="80% threshold")
    ax.axhline(95, color="#f39c12", linewidth=1.0, linestyle=":", alpha=0.7, label="95% threshold")

    ax.set_xlabel("Executable Statements", fontsize=11)
    ax.set_ylabel("Coverage (%)", fontsize=11)
    ax.set_title(
        "LLVManim — Module Size vs. Test Coverage\n(bubble area proportional to statement count)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.set_ylim(40, 105)
    ax.set_xlim(-10, 310)

    layer_patches = [
        mpatches.Patch(color=LAYER_COLORS[label], label=label, alpha=0.8)
        for label in ("cli", "ingest", "transform", "render")
    ]
    threshold_lines = [
        plt.Line2D([0], [0], color="#c0392b", linestyle="--", label="80% threshold"),
        plt.Line2D([0], [0], color="#f39c12", linestyle=":", label="95% threshold"),
    ]
    ax.legend(
        handles=layer_patches + threshold_lines,
        fontsize=9,
        framealpha=0.9,
        title="Layer",
        title_fontsize=9,
        loc="lower right",
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "04_size_vs_coverage.png", dpi=150)
    plt.close(fig)
    print("Wrote 04_size_vs_coverage.png")


if __name__ == "__main__":
    chart_coverage()
    chart_tests()
    chart_loc()
    chart_size_vs_coverage()
    print("Done — all charts written to docs/metrics/")
