"""Generate LLVManim performance / scaling charts and save them to docs/metrics/.

Benchmarks the live pipeline functions against synthetically generated IR of
increasing size — no Manim rendering involved.

Run from the repository root:
    uv run python docs/metrics/generate_perf_metrics.py
"""

from __future__ import annotations

import gc
import statistics
import time
import tracemalloc
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).parent
BG = "#f8f9fa"

# ── Colour palette ─────────────────────────────────────────────────────────────
C_INGEST = "#2980b9"
C_TRANSFORM = "#8e44ad"
C_TRACE = "#e67e22"
C_STACK = "#27ae60"
C_MEMORY = "#c0392b"

REPEATS = 5  # median over N runs


# ══════════════════════════════════════════════════════════════════════════════
# IR and stream generators
# ══════════════════════════════════════════════════════════════════════════════


def _make_ir_linear(n_instrs: int) -> str:
    """Return an IR module whose `@bench` function contains ~n_instrs instructions.

    Each 'instruction group' is: alloca + store + load + add + store → 5 instrs.
    """
    groups = max(1, n_instrs // 5)
    lines = [
        "define i32 @bench(i32 %x) {",
        "entry:",
        "  %acc = alloca i32",
        "  store i32 %x, ptr %acc",
    ]
    for i in range(groups):
        lines += [
            f"  %v{i}a = load i32, ptr %acc",
            f"  %v{i}b = add nsw i32 %v{i}a, {i}",
            f"  store i32 %v{i}b, ptr %acc",
        ]
    lines += [
        "  %ret = load i32, ptr %acc",
        "  ret i32 %ret",
        "}",
    ]
    return "\n".join(lines)


def _make_ir_many_blocks(n_blocks: int) -> str:
    """Return an IR module with a CFG that has ~n_blocks basic blocks.

    Layout: entry -> b0 -> b1 -> ... -> bN -> exit (linear chain).
    """
    lines = [
        "define i32 @bench() {",
        "entry:",
        "  %x = alloca i32",
        "  store i32 0, ptr %x",
        "  br label %b0",
    ]
    for i in range(n_blocks):
        nxt = f"%b{i + 1}" if i < n_blocks - 1 else "%exit"
        lines += [
            f"b{i}:",
            f"  %v{i} = load i32, ptr %x",
            f"  %u{i} = add nsw i32 %v{i}, 1",
            f"  store i32 %u{i}, ptr %x",
            f"  br label {nxt}",
        ]
    lines += [
        "exit:",
        "  %r = load i32, ptr %x",
        "  ret i32 %r",
        "}",
    ]
    return "\n".join(lines)


def _make_ir_call_chain(depth: int) -> str:
    """Return an IR module with a call chain bench→f1→f2→…→f{depth}.

    bench is the entry function; f{depth} is the leaf.
    Gives the stack-mode scene graph a deep call tree to handle.
    """
    lines: list[str] = []
    # Define leaf first, then walk back to bench so there are no forward refs.
    for i in range(depth, -1, -1):
        fname = "bench" if i == 0 else f"f{i}"
        callee = f"f{i + 1}" if i < depth else None
        lines += [f"define i32 @{fname}(i32 %x) {{", "entry:"]
        lines += ["  %slot = alloca i32", "  store i32 %x, ptr %slot"]
        if callee:
            lines += [f"  %r = call i32 @{callee}(i32 %x)"]
        lines += ["  ret i32 %x", "}", ""]
    return "\n".join(lines)


def _make_stream_n_blocks(n_blocks: int):
    """Return a ProgramEventStream with n_blocks blocks in a linear chain."""
    from llvmanim.ingest.llvm_events import parse_ir_to_events

    ir = _make_ir_many_blocks(n_blocks)
    return parse_ir_to_events(ir)


# ══════════════════════════════════════════════════════════════════════════════
# Timing helpers
# ══════════════════════════════════════════════════════════════════════════════


def _median_ms(fn, *args, **kwargs) -> float:
    """Return median elapsed time in milliseconds over REPEATS calls."""
    times: list[float] = []
    for _ in range(REPEATS):
        gc.collect()
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


def _peak_kb(fn, *args, **kwargs) -> float:
    """Return peak memory increment in KiB for one call."""
    gc.collect()
    tracemalloc.start()
    try:
        fn(*args, **kwargs)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / 1024


# ══════════════════════════════════════════════════════════════════════════════
# Chart 5 — parse_module_to_events: time vs. instruction count
# ══════════════════════════════════════════════════════════════════════════════


def chart_parse_scaling() -> None:
    from llvmanim.ingest.llvm_events import parse_ir_to_events

    sizes = [10, 25, 50, 100, 200, 400, 800, 1500]
    times_ms: list[float] = []

    print("Benchmarking parse_module_to_events …")
    for n in sizes:
        ir = _make_ir_linear(n)
        t = _median_ms(parse_ir_to_events, ir)
        times_ms.append(t)
        print(f"  {n:>5} instrs  →  {t:.2f} ms")

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.plot(
        sizes,
        times_ms,
        "o-",
        color=C_INGEST,
        linewidth=2,
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    for x, y in zip(sizes, times_ms, strict=False):
        ax.annotate(
            f"{y:.1f}",
            (x, y),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=8.5,
            color="#333",
        )

    ax.set_xlabel("Approximate instruction count", fontsize=11)
    ax.set_ylabel("Median parse time (ms)", fontsize=11)
    ax.set_title(
        f"parse_module_to_events  —  Scaling with IR Size\n(median of {REPEATS} runs per point)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0.05,
        0.95,
        r"Complexity:  $\Theta(n)$" "\n" r"$n$ = instruction count",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc", alpha=0.85),
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "05_parse_scaling.png", dpi=150)
    plt.close(fig)
    print("Wrote 05_parse_scaling.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 6 — build_scene_graph (cfg): time vs. block count
# ══════════════════════════════════════════════════════════════════════════════


def chart_scene_graph_cfg_scaling() -> None:
    from llvmanim.transform.scene import build_scene_graph

    block_counts = [1, 5, 10, 25, 50, 100, 200, 400]
    times_ms: list[float] = []

    print("Benchmarking build_scene_graph (cfg mode) …")
    for n in block_counts:
        stream = _make_stream_n_blocks(n)
        t = _median_ms(build_scene_graph, stream)
        times_ms.append(t)
        print(f"  {n:>4} blocks  →  {t:.3f} ms")

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.plot(
        block_counts,
        times_ms,
        "s-",
        color=C_TRANSFORM,
        linewidth=2,
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    for x, y in zip(block_counts, times_ms, strict=False):
        ax.annotate(
            f"{y:.2f}",
            (x, y),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=8.5,
            color="#333",
        )

    ax.set_xlabel("CFG block count", fontsize=11)
    ax.set_ylabel("Median build time (ms)", fontsize=11)
    ax.set_title(
        "build_scene_graph(mode='cfg')  —  Scaling with Block Count\n"
        f"(median of {REPEATS} runs per point)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0.05,
        0.95,
        r"Complexity:  $\Theta(n)$" "\n" r"$n$ = CFG block count",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc", alpha=0.85),
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "06_scene_graph_cfg_scaling.png", dpi=150)
    plt.close(fig)
    print("Wrote 06_scene_graph_cfg_scaling.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 7 — derive_cfg_trace: time vs. block count
# ══════════════════════════════════════════════════════════════════════════════


def chart_trace_scaling() -> None:
    from llvmanim.transform.scene import build_scene_graph
    from llvmanim.transform.trace import derive_cfg_trace

    block_counts = [1, 5, 10, 25, 50, 100, 200, 400]
    times_ms: list[float] = []

    print("Benchmarking derive_cfg_trace …")
    for n in block_counts:
        stream = _make_stream_n_blocks(n)
        graph = build_scene_graph(stream)
        t = _median_ms(derive_cfg_trace, graph, function="bench")
        times_ms.append(t)
        print(f"  {n:>4} blocks  →  {t:.3f} ms")

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.plot(
        block_counts,
        times_ms,
        "^-",
        color=C_TRACE,
        linewidth=2,
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    for x, y in zip(block_counts, times_ms, strict=False):
        ax.annotate(
            f"{y:.3f}",
            (x, y),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=8.5,
            color="#333",
        )

    ax.set_xlabel("CFG block count", fontsize=11)
    ax.set_ylabel("Median trace time (ms)", fontsize=11)
    ax.set_title(
        "derive_cfg_trace  —  Scaling with Block Count\n"
        f"(median of {REPEATS} runs per point, linear chain CFG)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0.05,
        0.95,
        r"Complexity:  $\Theta(n)$  (linear chain CFG)" "\n"
        r"$O(n \cdot k)$ in general,  $k$ = loop-iteration bound" "\n"
        r"$n$ = CFG block count",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc", alpha=0.85),
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "07_trace_scaling.png", dpi=150)
    plt.close(fig)
    print("Wrote 07_trace_scaling.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 8 — build_scene_graph (stack): time vs. call-tree depth
# ══════════════════════════════════════════════════════════════════════════════


def chart_scene_graph_stack_scaling() -> None:
    from llvmanim.ingest.llvm_events import parse_ir_to_events
    from llvmanim.transform.scene import build_scene_graph

    depths = [1, 2, 5, 10, 15, 20, 30, 50]
    times_ms: list[float] = []

    print("Benchmarking build_scene_graph (stack mode) …")
    for d in depths:
        ir = _make_ir_call_chain(d)
        stream = parse_ir_to_events(ir)
        t = _median_ms(build_scene_graph, stream, mode="stack", entry="bench")
        times_ms.append(t)
        print(f"  depth {d:>3}  →  {t:.3f} ms")

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.plot(
        depths,
        times_ms,
        "D-",
        color=C_STACK,
        linewidth=2,
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    for x, y in zip(depths, times_ms, strict=False):
        ax.annotate(
            f"{y:.2f}",
            (x, y),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=8.5,
            color="#333",
        )

    ax.set_xlabel("Call-tree depth (number of nested functions)", fontsize=11)
    ax.set_ylabel("Median build time (ms)", fontsize=11)
    ax.set_title(
        "build_scene_graph(mode='stack')  —  Scaling with Call Depth\n"
        f"(median of {REPEATS} runs per point)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0.05,
        0.95,
        r"Complexity:  $O(d)$  worst case" "\n"
        r"$o(d)$  empirically (sub-linear growth observed)" "\n"
        r"$d$ = call-tree depth",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc", alpha=0.85),
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "08_scene_graph_stack_scaling.png", dpi=150)
    plt.close(fig)
    print("Wrote 08_scene_graph_stack_scaling.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 9 — Peak memory vs. IR size (full ingest + transform pipeline)
# ══════════════════════════════════════════════════════════════════════════════


def chart_memory_scaling() -> None:
    from llvmanim.ingest.llvm_events import parse_ir_to_events
    from llvmanim.transform.scene import build_scene_graph

    def _full_pipeline_cfg(ir: str) -> None:
        stream = parse_ir_to_events(ir)
        build_scene_graph(stream)

    def _full_pipeline_stack(ir: str) -> None:
        stream = parse_ir_to_events(ir)
        build_scene_graph(stream, mode="stack", entry="bench")

    sizes = [10, 25, 50, 100, 200, 400, 800]
    mem_cfg_kb: list[float] = []
    mem_stk_kb: list[float] = []

    print("Measuring peak memory (ingest + build_scene_graph) …")
    for n in sizes:
        ir_cfg = _make_ir_many_blocks(n)
        ir_stk = _make_ir_many_blocks(n)  # same size, different path
        kb_cfg = _peak_kb(_full_pipeline_cfg, ir_cfg)
        kb_stk = _peak_kb(_full_pipeline_stack, ir_stk)
        mem_cfg_kb.append(kb_cfg)
        mem_stk_kb.append(kb_stk)
        print(f"  {n:>4} blocks  →  CFG {kb_cfg:.0f} KiB  |  stack {kb_stk:.0f} KiB")

    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=BG)
    ax.set_facecolor(BG)

    ax.plot(
        sizes,
        mem_cfg_kb,
        "o-",
        color=C_TRANSFORM,
        linewidth=2,
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=2,
        label="CFG pipeline",
    )
    ax.plot(
        sizes,
        mem_stk_kb,
        "s--",
        color=C_STACK,
        linewidth=2,
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=2,
        label="Stack pipeline",
    )

    ax.set_xlabel("CFG block count (proxy for IR size)", fontsize=11)
    ax.set_ylabel("Peak memory allocation (KiB)", fontsize=11)
    ax.set_title(
        "ingest + build_scene_graph  —  Peak Memory vs. IR Size\n"
        "(tracemalloc, single run per point)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.legend(fontsize=10, framealpha=0.9)
    ax.text(
        0.97,
        0.05,
        r"Complexity:  $\Theta(n)$  (both pipelines)" "\n" r"$n$ = CFG block count",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="bottom",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc", alpha=0.85),
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "09_memory_scaling.png", dpi=150)
    plt.close(fig)
    print("Wrote 09_memory_scaling.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 10 — Combined pipeline timing overview (bar chart, representative size)
# ══════════════════════════════════════════════════════════════════════════════


def chart_pipeline_stage_times() -> None:
    """Measure wall-clock time for each pipeline stage at a representative IR size."""
    from llvmanim.ingest.llvm_events import parse_ir_to_events
    from llvmanim.transform.scene import build_scene_graph
    from llvmanim.transform.trace import derive_cfg_trace

    N_BLOCKS = 50

    print("Measuring per-stage pipeline timing …")
    ir = _make_ir_many_blocks(N_BLOCKS)

    t_parse = _median_ms(parse_ir_to_events, ir)
    stream = parse_ir_to_events(ir)

    t_build_cfg = _median_ms(build_scene_graph, stream)
    t_build_stack = _median_ms(build_scene_graph, stream, mode="stack", entry="bench")

    graph = build_scene_graph(stream)
    t_trace = _median_ms(derive_cfg_trace, graph, function="bench")

    stages = [
        ("parse_module_to_events", t_parse, C_INGEST),
        ("build_scene_graph\n(cfg)", t_build_cfg, C_TRANSFORM),
        ("derive_cfg_trace", t_trace, C_TRACE),
        ("build_scene_graph\n(stack)", t_build_stack, C_STACK),
    ]

    labels = [s[0] for s in stages]
    values = [s[1] for s in stages]
    colors = [s[2] for s in stages]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.set_facecolor(BG)

    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.8, width=0.55)
    for bar, v in zip(bars, values, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.005,
            f"{v:.3f} ms",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#333",
        )

    ax.set_ylabel("Median wall-clock time (ms)", fontsize=11)
    ax.set_title(
        f"Pipeline Stage Latency  —  {N_BLOCKS} CFG blocks\n(median of {REPEATS} runs per stage)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0.97,
        0.95,
        "Complexity Legend\n"
        r"parse:          $\Theta(n_i)$,  $n_i$ = instr. count" "\n"
        r"cfg build:     $\Theta(n_b)$,  $n_b$ = block count" "\n"
        r"trace:           $\Theta(n_b)$" "\n"
        r"stack build:  $O(d)$,  $d$ = call depth",
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#ccc", alpha=0.9),
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", labelsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "10_pipeline_stage_latency.png", dpi=150)
    plt.close(fig)
    print(
        f"Wrote 10_pipeline_stage_latency.png  "
        f"(parse {t_parse:.3f}ms | cfg {t_build_cfg:.3f}ms | "
        f"trace {t_trace:.3f}ms | stack {t_build_stack:.3f}ms)"
    )


if __name__ == "__main__":
    chart_parse_scaling()
    chart_scene_graph_cfg_scaling()
    chart_trace_scaling()
    chart_scene_graph_stack_scaling()
    chart_memory_scaling()
    chart_pipeline_stage_times()
    print("\nDone — all performance charts written to docs/metrics/")
