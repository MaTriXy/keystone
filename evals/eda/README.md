# Repo Explorer – EDA tools for sampling GitHub repos

Interactive tools for fetching GitHub repository metrics and exploring them
with a Plotly parallel coordinates plot to select evaluation candidates.

## Quick Start

```bash
# 1. Install dependencies (including pyarrow for parquet)
uv sync              # pyarrow is a core dependency
uv pip install plotly ipywidgets numpy  # for the notebook

# 2. Fetch repo metrics (needs a GitHub token with public repo access)
export GITHUB_TOKEN=ghp_...
uv run python evals/eda/fetch_repos.py      # writes repos.parquet; cached to .api_cache/

# 3. Open the notebook
jupyter lab evals/eda/repo_explorer.ipynb
```

API responses are cached to `evals/eda/.api_cache/` so reruns are instant.
Use `--no-cache` to force fresh fetches.

## What it does

**`fetch_repos.py`** queries the GitHub GraphQL API, sampling repos stratified
by language (12 languages) × star-count bucket (6 ranges from 10→500k stars).
This avoids the bias of only picking top-starred repos. For each repo it
collects:

| Metric | Description |
|---|---|
| `stars` | Stargazer count |
| `forks` | Fork count |
| `size_mb` | Disk usage in MB |
| `total_commits` | Total commits on default branch |
| `recent_commits_90d` | Commits in the last 90 days |
| `open_issues` | Open issue count |
| `open_prs` | Open PR count |
| `language` | Primary language |
| `license` | SPDX license ID |
| `topics` | Top 5 repo topics |

**`repo_explorer.ipynb`** renders an interactive Plotly parallel coordinates
plot colored by language. Drag ranges on any axis to filter, and the table
below updates live showing selected repo names. An "Export selected → JSONL"
button writes `selected_repos.jsonl` in the same format as
`evals/examples/repos.jsonl`.

## Options

```
uv run python evals/eda/fetch_repos.py --help

  --per-query N       Repos per GitHub search query (default: 10)
  --max-size-mb N     Skip repos larger than N MB (default: 500)
  --recent-days N     Window for recent commit count (default: 90)
  --csv               Also write CSV alongside parquet
  --out PATH          Output path (default: evals/eda/repos.parquet)
```

---

## Investigating Test Winner Discrepancies

When a model is a "test winner" for a repo but another isn't, it's worth
understanding *why*. Here's a recipe using the parquet files and eval_schema.

### Setup

```bash
# Fetch a run to local parquet (if not cached)
uv run python evals/eda/eval_to_parquet_cli.py \
    s3://int8-datasets/keystone/evals/2026-04-01_thad_eval_v1 \
    /tmp/2026-04-01_thad_eval_v1.parquet
```

### Investigation recipe

```python
import polars as pl
from eval_schema import KeystoneRepoResult
import sys
sys.path.insert(0, "evals")

df = pl.read_parquet("/tmp/2026-04-01_thad_eval_v1.parquet")

REPO = "numpy"  # or "sqlite", etc.

for config in ["claude-opus", "gpt-5.4"]:
    row = df.filter(
        (pl.col("repo_id") == REPO) & (pl.col("config_name") == config)
    ).row(0, named=True)
    r = KeystoneRepoResult.model_validate_json(row["raw_json"])
    br = r.bootstrap_result
    gf = br.generated_files

    # 1. High-level stats
    print(f"=== {config} ===")
    print(f"success: {r.success}")
    print(f"tests_passed: {br.verification.tests_passed}")
    print(f"tests_failed: {br.verification.tests_failed}")
    print(f"unexpected_broken_commit_passes: {br.unexpected_broken_commit_passes}")

    # 2. Per-branch mutation results
    for branch, v in sorted(br.broken_commit_verifications.items(),
                            key=lambda x: int(x[0].split("-")[1])):
        print(f"  {branch}: success={v.success} "
              f"passed={v.tests_passed} failed={v.tests_failed} "
              f"time={v.test_execution_seconds:.0f}s "
              f"err={v.error_message or ''}")

    # 3. The generated test script and Dockerfile
    print(gf.run_all_tests_sh)
    print(gf.dockerfile[-500:])  # tail of Dockerfile
```

### Key things to look at

1. **run_all_tests.sh** — Does it rebuild from source, or run tests against
   a stale cached build? Mutations change source files, so if the test script
   doesn't trigger a rebuild, mutations go undetected.

2. **Build approach** — Compare how each model builds the project:
   - `pip install -e .` may reuse cached build artifacts
   - `spin build --clean` or `meson setup --wipe` forces a full rebuild
   - `make` will rebuild changed files but may miss header-only changes

3. **Test scope** — One model may run a shallow smoke test (e.g. SQLite's
   `test/main.test`) while another runs the full suite (e.g. `veryquick.test`).

4. **Failure mode** — Check `success`, `error_message`, and timing:
   - `success=False` with `passed=0, failed=0` and short time → build failure
     (good — mutation was caught at build time)
   - `success=True` with `passed=0, failed=0` → tests ran but produced no
     JUnit XML, or the script didn't propagate the exit code
   - `success=True` with many passes → mutation didn't affect tested code paths

### Case Studies

#### numpy — claude-opus misses 14/20 mutations despite 48,968 tests

**claude-opus**: Runs `pip install --no-build-isolation -e .` then
`pytest numpy/`. The `pip install -e .` in the test script reuses the
*already-compiled C extensions from the Docker layer* because editable
installs with meson-python only rebuild if the build directory is stale.
When a mutation modifies a `.c` or `.py` file, the editable install
doesn't notice the source changed (the meson build directory from the
Docker build step still exists), so pytest runs against the original
(un-mutated) compiled code. Result: 48,968 tests pass, mutation undetected.

**gpt-5.4**: Uses `spin test` which invokes `spin build` before running
pytest. `spin build` uses meson under the hood and properly detects source
changes, triggering a recompile. When the mutation breaks compilation or
changes behavior, the tests catch it. For broken-1 through broken-14, the
mutations cause build failures (exit code 1 in ~9-10s), which `spin test`
correctly propagates as `success=False`. All 20 mutations caught.

**Root cause**: claude-opus's `pip install -e .` doesn't force a rebuild of
C extensions when source files change in an already-built tree.

#### sqlite — claude-opus misses 1/20 mutations despite 87 tests

**claude-opus**: Runs only `test/main.test` (87 TCL smoke-test assertions
like `main-1.1`). The mutation in `broken-16` doesn't affect any of these
shallow checks. All 87 pass, giving 1 unexpected broken commit pass.

**gpt-5.4**: Runs a broader suite via CTest: source tree checks, fuzz tests
(`fuzzdata1`–`fuzzdata8`), `sessionfuzz`, and the full `veryquick.test`
(thousands of TCL tests). On broken-16, the test run fails (`success=False`,
`passed=0, failed=0` — likely a build or hard crash). All 20 caught.

**Root cause**: claude-opus's test script has too narrow coverage —
`test/main.test` is a quick smoke test, not a comprehensive suite.
