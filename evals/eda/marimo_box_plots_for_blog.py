"""Box Plot Analysis — marimo notebook.

Generates box plots for agent walltime, inference cost, and normalized tests
passed, comparing selected eval configurations.

Run interactively::

    uv run marimo edit evals/eda/marimo_box_plots_for_blog.py

Render to static HTML::

    uv run marimo export html evals/eda/marimo_box_plots_for_blog.py -o marimo_box_plots_for_blog.html
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # Eval Box Plots

        Box plots comparing agent wall-clock time, inference cost, and fraction
        of max tests passed across selected configurations.
        """
    )
    return (mo,)


@app.cell
def _(mo):
    import sys
    from pathlib import Path

    import pandas as pd
    import plotly.express as px
    import polars as pl

    # Ensure the evals package root is importable
    _evals_root = str(Path(__file__).resolve().parents[1])
    if _evals_root not in sys.path:
        sys.path.insert(0, _evals_root)

    from eval_schema import KeystoneRepoResult

    PARQUET_PATH = Path.home() / "keystone_eval" / "blog.parquet"

    CONFIGS = [
        "gpt-5.4",
        "codex-gpt-5.3",
        "codex-mini-gpt-5.1",
        "opus-4.6",
        "claude-haiku",
    ]

    # Load all data — include raw_json for deduplicated test counting
    all_df = pl.read_parquet(PARQUET_PATH).select(
        "config_name",
        "repo_id",
        "trial_index",
        "success",
        "agent_walltime_seconds",
        "cost_usd",
        "agent_timed_out",
        "raw_json",
    )

    # Deduplicate test counts from raw_json: unique test names only,
    # "passed" = any occurrence of that test name passed (logical OR).
    # This fixes double-counting when an agent runs the test suite twice.
    deduped_passed = []
    deduped_discovered = []
    for row in all_df.iter_rows(named=True):
        try:
            r = KeystoneRepoResult.model_validate_json(row["raw_json"])
            tr = r.bootstrap_result.verification.test_results
        except Exception:
            tr = None
        if not tr:
            deduped_discovered.append(None)
            deduped_passed.append(None)
            continue
        # Build a dict: test_name -> ever passed?
        seen: dict[str, bool] = {}
        for t in tr:
            seen[t.name] = seen.get(t.name, False) or t.passed
        deduped_discovered.append(len(seen))
        deduped_passed.append(sum(1 for v in seen.values() if v))

    all_df = all_df.drop("raw_json").with_columns(
        pl.Series("tests_discovered", deduped_discovered, dtype=pl.Int64),
        pl.Series("tests_passed", deduped_passed, dtype=pl.Int64),
    )

    # Compute repo_max_tests across ALL configs (deduplicated)
    repo_max = all_df.group_by("repo_id").agg(
        pl.col("tests_discovered").max().alias("repo_max_tests")
    )
    all_df = all_df.join(repo_max, on="repo_id")
    all_df = all_df.with_columns(
        pl.when(pl.col("repo_max_tests") > 0)
        .then(pl.col("tests_passed") / pl.col("repo_max_tests"))
        .otherwise(0.0)
        .alias("norm_tests_passed")
    )

    # Filter to target configs
    df = all_df.filter(pl.col("config_name").is_in(CONFIGS)).to_pandas()

    # Enforce config ordering
    df["config_name"] = pd.Categorical(df["config_name"], categories=CONFIGS, ordered=True)

    mo.md(f"Loaded **{len(df)}** rows for {len(CONFIGS)} configs from `{PARQUET_PATH.name}`")
    return CONFIGS, Path, df, px


@app.cell
def _(mo):
    mo.md("""
    ## Agent Wall-clock Time
    """)
    return


@app.cell
def _(CONFIGS, Path, df, mo, px):
    fig_time = px.box(
        df,
        x="config_name",
        y="agent_walltime_seconds",
        color="config_name",
        points="all",
        hover_data=["repo_id", "trial_index", "tests_passed"],
        category_orders={"config_name": CONFIGS},
        title="Agent Wall-clock Time by Config",
        labels={
            "config_name": "Config",
            "agent_walltime_seconds": "Wall-clock Time (s)",
        },
    )
    fig_time.update_layout(showlegend=False)

    _out = Path(__file__).parent / "output" / "box_walltime.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    fig_time.write_html(str(_out), include_plotlyjs="cdn")
    mo.md(f"Saved → `{_out}`")
    return (fig_time,)


@app.cell
def _(fig_time, mo):
    mo.ui.plotly(fig_time)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Inference Cost
    """)
    return


@app.cell
def _(CONFIGS, Path, df, mo, px):
    fig_cost = px.box(
        df,
        x="config_name",
        y="cost_usd",
        color="config_name",
        points="all",
        hover_data=["repo_id", "trial_index", "tests_passed"],
        category_orders={"config_name": CONFIGS},
        title="Inference Cost by Config",
        labels={
            "config_name": "Config",
            "cost_usd": "Cost (USD)",
        },
    )
    fig_cost.update_layout(showlegend=False)

    _out = Path(__file__).parent / "output" / "box_cost.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    fig_cost.write_html(str(_out), include_plotlyjs="cdn")
    mo.md(f"Saved → `{_out}`")
    return (fig_cost,)


@app.cell
def _(fig_cost, mo):
    mo.ui.plotly(fig_cost)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Tests Passed (fraction of max discovered)
    """)
    return


@app.cell
def _(CONFIGS, Path, df, mo, px):
    fig_tests = px.box(
        df,
        x="config_name",
        y="norm_tests_passed",
        color="config_name",
        points="all",
        hover_data=["repo_id", "trial_index", "tests_passed"],
        category_orders={"config_name": CONFIGS},
        title="Tests Passed (fraction of max discovered per repo)",
        labels={
            "config_name": "Config",
            "norm_tests_passed": "Fraction of Max Tests Passed",
        },
    )
    fig_tests.update_layout(showlegend=False, yaxis_tickformat=".0%")

    _out = Path(__file__).parent / "output" / "box_norm_tests.html"
    _out.parent.mkdir(parents=True, exist_ok=True)
    fig_tests.write_html(str(_out), include_plotlyjs="cdn")
    mo.md(f"Saved → `{_out}`")
    return (fig_tests,)


@app.cell
def _(fig_tests, mo):
    mo.ui.plotly(fig_tests)
    return


if __name__ == "__main__":
    app.run()
