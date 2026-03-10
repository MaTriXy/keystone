# JUnit XML Output: The Right Way per Framework

Each test in the suite MUST appear as its own `<testcase>` in the JUnit XML.
**Do NOT wrap the entire test suite in a single pytest/subprocess test.**

---

## Python — pytest

```bash
pytest tests/ --junitxml=/test_artifacts/junit/results.xml -v
```

## Ruby — Rails minitest

Install `minitest-reporters` in the Dockerfile, then:

```bash
export MINITEST_REPORTERS_REPORTS_DIR=/test_artifacts/junit
bundle exec rails test
```

## Node.js — built-in test runner (>=18)

```bash
node --test \
  --test-reporter=junit --test-reporter-destination=/test_artifacts/junit/results.xml \
  --test-reporter=spec  --test-reporter-destination=stdout \
  ./test/**/*.test.js
```

## Node.js — mocha

```bash
npm install mocha-junit-reporter
MOCHA_FILE=/test_artifacts/junit/results.xml \
  npx mocha --reporter mocha-junit-reporter --timeout 30000 test/
```

For monorepos, run per-package and set `MOCHA_FILE` to a unique path for each.

## Node.js — mocha (Electron)

```bash
pnpm exec electron-mocha \
  --reporter mocha-junit-reporter \
  --reporter-options mochaFile=/test_artifacts/junit/results.xml \
  --timeout 10000 --recursive test/
```

## Rust — cargo-nextest

```bash
cargo nextest run --workspace
cp target/nextest/default/junit.xml /test_artifacts/junit/results.xml
```

## Go — ginkgo

```bash
ginkgo --junit-report=/test_artifacts/junit/results.xml ./...
```

## Go — go test (via gotestsum)

```bash
gotestsum --junitfile /test_artifacts/junit/results.xml -- ./...
```

**Warning:** Do NOT pipe `go test` output through `go-junit-report` — it aggregates
Ginkgo specs (and other sub-tests) into a single `<testcase>` per package, losing all
per-test granularity. Use `ginkgo --junit-report` or `gotestsum --junitfile` instead.

## C/C++ — ctest

```bash
ctest --test-dir build --output-on-failure \
  --output-junit /test_artifacts/junit/results.xml \
  --parallel $(nproc)
```

## Lua — busted (has native JUnit support)

busted has built-in JUnit output — no custom parsing needed:

```bash
busted --output junit -o /test_artifacts/junit/results.xml
```

Or if using LuaRocks:

```bash
luarocks test --test-type busted -- --output junit -o /test_artifacts/junit/results.xml
```

## Lua — Neovim plenary (no native JUnit support)

Plenary's test harness has no JUnit reporter. Run tests headlessly, capture output,
then parse the `Success || ...` / `Fail || ...` lines into JUnit XML:

```bash
nvim --headless -u tests/minimal_init.lua -c "RunTests tests" 2>&1 | tee /tmp/test_output.txt

python3 <<'PY'
import re, xml.etree.ElementTree as ET

with open("/tmp/test_output.txt") as f:
    lines = [re.sub(r'\x1b\[[0-9;]*m', '', l).strip() for l in f]

suites = ET.Element("testsuites")
suite = ET.SubElement(suites, "testsuite", name="plenary")
tests = failures = 0
for line in lines:
    m = re.match(r'^(Success|Fail)\s*\|\|\s*(.+)', line)
    if not m:
        continue
    tc = ET.SubElement(suite, "testcase", name=m.group(2).strip(), classname="plenary")
    tests += 1
    if m.group(1) == "Fail":
        ET.SubElement(tc, "failure", message="Test failed")
        failures += 1
suite.set("tests", str(tests))
suite.set("failures", str(failures))
ET.ElementTree(suites).write("/test_artifacts/junit/results.xml", xml_declaration=True, encoding="UTF-8")
PY
```

**Note:** Many Neovim plugins use busted, not plenary. Check for a `.busted` file or
`busted` in the rockspec/test config before reaching for the plenary parser — busted's
native `--output junit` is simpler and more reliable.

---

## ❌ Anti-pattern — DO NOT DO THIS

```python
# This hides all individual test results behind a single pass/fail!
def test_entire_suite():
    subprocess.run(["bash", "run_tests.sh"], check=True)
```

Running this with `pytest --junitxml=...` reports **1 test** regardless of how many
tests actually ran. You lose all per-test granularity.
