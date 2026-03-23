"""Codex Eval CDF Analysis — marimo notebook.

Generates CDF plots for agent walltime and inference cost, saves them as
self-contained HTML files for embedding in blog posts.

Run interactively::

    uv run marimo edit evals/eda/marimo_cdfs_for_blog.py

Render to static HTML::

    uv run marimo export html evals/eda/marimo_cdfs_for_blog.py -o marimo_cdfs_for_blog.html
"""

import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # Codex Eval — CDF Analysis

        CDF plots of agent walltime and inference cost for each codex
        configuration.  Failing / timed-out runs are marked with a red **✕**.

        Hover over a point to highlight the same repo across all configs.

        HTML files for blog embedding are saved alongside this notebook.
        """
    )
    return (mo,)


@app.cell
def _(mo):
    import sys
    from pathlib import Path

    # Ensure the evals package root is importable when run standalone via marimo
    _evals_root = str(Path(__file__).resolve().parents[1])
    if _evals_root not in sys.path:
        sys.path.insert(0, _evals_root)

    import importlib

    import eda.cdf_plot

    # Force re-read from disk so `marimo run --watch` picks up changes to
    # cdf_plot.py (--watch only detects notebook file changes, not imported
    # modules, so without this reload we'd get stale cached code).
    importlib.reload(eda.cdf_plot)

    from eda.cdf_plot import (
        DEFAULT_PARQUET,
        build_claude_cost_figure,
        build_claude_figure,
        build_cost_figure,
        build_figure,
        build_normalized_tests_figure,
        export_html,
        export_xhtml,
        load_all_data,
        load_claude_data,
        load_codex_data,
        prepare_parcoords_data,
    )

    pdf = load_codex_data(DEFAULT_PARQUET)
    claude_pdf = load_claude_data(DEFAULT_PARQUET)
    all_pdf = load_all_data(DEFAULT_PARQUET)

    BLOG_STATIC = Path.home() / "src" / "generallyintelligent.com" / "static" / "keystone"

    mo.md(
        f"Loaded **{len(pdf)}** codex rows and **{len(claude_pdf)}** claude rows "
        f"from `{DEFAULT_PARQUET.name}`"
    )
    return (
        BLOG_STATIC,
        Path,
        all_pdf,
        build_claude_cost_figure,
        build_claude_figure,
        build_cost_figure,
        build_figure,
        build_normalized_tests_figure,
        claude_pdf,
        export_html,
        export_xhtml,
        pdf,
        prepare_parcoords_data,
    )


@app.cell
def _(mo):
    mo.md("""
    ## CDF — Codex Agent Wall-clock Time
    """)
    return


@app.cell
def _(BLOG_STATIC, Path, build_figure, export_html, export_xhtml, mo, pdf):
    fig_time = build_figure(pdf)

    _out = Path(__file__).parent / "output" / "codex_walltime_cdf.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    export_html(fig_time, _out, div_id="walltime-cdf")

    _xhtml = BLOG_STATIC / "codex_walltime_cdf.xhtml"
    export_xhtml(fig_time, _xhtml, title="CDF — Codex Agent Wall-clock Time", div_id="walltime-cdf")
    mo.md(f"Saved → `{_out}`\n\nSaved → `{_xhtml}`")
    return (fig_time,)


@app.cell
def _(fig_time, mo):
    mo.ui.plotly(fig_time)
    return


@app.cell
def _(mo):
    mo.md("""
    ## CDF — Codex Inference Cost
    """)
    return


@app.cell
def _(BLOG_STATIC, Path, build_cost_figure, export_html, export_xhtml, mo, pdf):
    fig_cost = build_cost_figure(pdf)

    _out = Path(__file__).parent / "output" / "codex_cost_cdf.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    export_html(fig_cost, _out, div_id="cost-cdf")

    _xhtml = BLOG_STATIC / "codex_cost_cdf.xhtml"
    export_xhtml(fig_cost, _xhtml, title="CDF — Codex Inference Cost", div_id="cost-cdf")
    mo.md(f"Saved → `{_out}`\n\nSaved → `{_xhtml}`")
    return (fig_cost,)


@app.cell
def _(fig_cost, mo):
    mo.ui.plotly(fig_cost)
    return


@app.cell
def _(mo):
    mo.md("""
    ## CDF — Claude Agent Wall-clock Time
    """)
    return


@app.cell
def _(BLOG_STATIC, Path, build_claude_figure, claude_pdf, export_html, export_xhtml, mo):
    fig_claude_time = build_claude_figure(claude_pdf)

    _out = Path(__file__).parent / "output" / "claude_walltime_cdf.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    export_html(fig_claude_time, _out, div_id="claude-walltime-cdf")

    _xhtml = BLOG_STATIC / "claude_walltime_cdf.xhtml"
    export_xhtml(
        fig_claude_time,
        _xhtml,
        title="CDF — Claude Agent Wall-clock Time",
        div_id="claude-walltime-cdf",
    )
    mo.md(f"Saved → `{_out}`\n\nSaved → `{_xhtml}`")
    return (fig_claude_time,)


@app.cell
def _(fig_claude_time, mo):
    mo.ui.plotly(fig_claude_time)
    return


@app.cell
def _(mo):
    mo.md("""
    ## CDF — Claude Inference Cost
    """)
    return


@app.cell
def _(BLOG_STATIC, Path, build_claude_cost_figure, claude_pdf, export_html, export_xhtml, mo):
    fig_claude_cost = build_claude_cost_figure(claude_pdf)

    _out = Path(__file__).parent / "output" / "claude_cost_cdf.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    export_html(fig_claude_cost, _out, div_id="claude-cost-cdf")

    _xhtml = BLOG_STATIC / "claude_cost_cdf.xhtml"
    export_xhtml(
        fig_claude_cost, _xhtml, title="CDF — Claude Inference Cost", div_id="claude-cost-cdf"
    )
    mo.md(f"Saved → `{_out}`\n\nSaved → `{_xhtml}`")
    return (fig_claude_cost,)


@app.cell
def _(fig_claude_cost, mo):
    mo.ui.plotly(fig_claude_cost)
    return


@app.cell
def _(mo):
    mo.md("""
    ## CDF — Normalized Tests Passed
    Tests passed divided by the maximum tests discovered (passed + failed) for
    each repo across **all** configs.
    """)
    return


@app.cell
def _(build_normalized_tests_figure, mo, all_pdf):
    fig_norm_tests = build_normalized_tests_figure(all_pdf)
    mo.ui.plotly(fig_norm_tests)
    return (fig_norm_tests,)


@app.cell
def _(mo):
    mo.md("""
    ## Eval Results — Parallel Coordinates

    Brush-select ranges on any axis to filter. The AG Grid below updates
    to show only the selected rows.
    """)
    return


@app.cell
def _(Path, all_pdf, mo, prepare_parcoords_data):
    import json as _json

    _records = prepare_parcoords_data(all_pdf)

    _template_path = Path(__file__).parent / "eval_parcoords.html"
    _template = _template_path.read_text()
    parcoords_html = _template.replace('"__DATA_PLACEHOLDER__"', _json.dumps(_records))

    # Save standalone HTML
    _out_path = Path(__file__).parent / "output" / "eval_parcoords.html"
    _out_path.parent.mkdir(parents=True, exist_ok=True)
    _out_path.write_text(parcoords_html)

    mo.md(f"Parcoords: **{len(_records)}** rows across comparison configs → `{_out_path}`")
    return (parcoords_html,)


@app.cell
def _(parcoords_html, mo):
    import base64 as _b64

    _data_uri = "data:text/html;base64," + _b64.b64encode(parcoords_html.encode()).decode()
    mo.Html(
        f'<iframe src="{_data_uri}" '
        f'width="100%" height="1250" style="border:1px solid #ddd; border-radius:4px"></iframe>'
    )
    return


@app.cell
def _(claude_pdf, mo, pdf):
    import pandas as pd
    import polars as pl

    _stats = (
        pl.from_pandas(pd.concat([pdf, claude_pdf], ignore_index=True))
        .group_by("config_name")
        .agg(
            pl.col("agent_walltime_seconds").mean().alias("mean_time_s"),
            pl.col("agent_walltime_seconds").median().alias("median_time_s"),
            pl.col("cost_usd").mean().alias("mean_cost_usd"),
            pl.col("cost_usd").sum().alias("total_cost_usd"),
            pl.col("success").mean().alias("success_rate"),
            pl.len().alias("n"),
        )
        .sort("median_time_s")
    )
    mo.md("## Summary stats by config")
    mo.ui.table(_stats, selection=None)
    return


if __name__ == "__main__":
    app.run()
