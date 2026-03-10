#!/bin/bash
# guardrail.sh — Agent self-check tool for validating devcontainer work.
#
# Run this script from the project root to get structured feedback about
# common mistakes *before* the final verification step. It checks:
#   1. Required files exist (.devcontainer/devcontainer.json, Dockerfile, run_all_tests.sh)
#   2. Docker image builds successfully (from a clean copy of the project)
#   3. Tests pass and produce JUnit XML + final_result.json
#
# Exit code 0 = all checks pass, non-zero = at least one check failed.
# Output is structured feedback the agent can act on.

set -uo pipefail

ERRORS=0
WARNINGS=0
BUILT_IMAGE=""

pass() {
    echo "  PASS: $1"
}

fail() {
    echo "  FAIL: $1"
    ERRORS=$((ERRORS + 1))
}

warn() {
    echo "  WARN: $1"
    WARNINGS=$((WARNINGS + 1))
}

echo "========================================"
echo "GUARDRAIL CHECK — Validating your work"
echo "========================================"
echo ""

# ------------------------------------------------------------------
# 1. Required files exist
# ------------------------------------------------------------------
echo "[1/3] Checking required files..."

if [ -d ".devcontainer" ]; then
    pass ".devcontainer/ directory exists"
else
    fail ".devcontainer/ directory is MISSING. Create it with: mkdir -p .devcontainer"
fi

if [ -f ".devcontainer/devcontainer.json" ]; then
    pass ".devcontainer/devcontainer.json exists"
else
    fail ".devcontainer/devcontainer.json is MISSING. Copy the pre-generated one: cp ./devcontainer.json .devcontainer/devcontainer.json"
fi

if [ -f ".devcontainer/Dockerfile" ]; then
    pass ".devcontainer/Dockerfile exists"
else
    fail ".devcontainer/Dockerfile is MISSING. You must create a Dockerfile inside .devcontainer/"
fi

if [ -f ".devcontainer/run_all_tests.sh" ]; then
    pass ".devcontainer/run_all_tests.sh exists"
    if [ -x ".devcontainer/run_all_tests.sh" ]; then
        pass ".devcontainer/run_all_tests.sh is executable"
    else
        fail ".devcontainer/run_all_tests.sh is NOT executable. Run: chmod +x .devcontainer/run_all_tests.sh"
    fi
else
    fail ".devcontainer/run_all_tests.sh is MISSING. You must create a test runner script."
fi

echo ""

# ------------------------------------------------------------------
# 2. Docker build check
# ------------------------------------------------------------------
echo "[2/3] Attempting Docker build..."

if [ -f ".devcontainer/Dockerfile" ] && [ -f ".devcontainer/devcontainer.json" ]; then
    # Build from a clean copy of the project with only .devcontainer/ overlaid.
    # This verifies the agent didn't modify source files outside .devcontainer/.
    if [ -d "/project_clean" ]; then
        CLEAN_SRC="/project_clean"
    elif [ -d ".project_clean" ]; then
        CLEAN_SRC=".project_clean"
    else
        CLEAN_SRC=""
    fi

    if [ -z "$CLEAN_SRC" ]; then
        fail "No clean project copy found (expected /project_clean or .project_clean). Cannot verify build isolation."
    else
        BUILD_DIR=$(mktemp -d)
        cp -r "$CLEAN_SRC/." "$BUILD_DIR/"
        rm -rf "$BUILD_DIR/.devcontainer"
        cp -r .devcontainer/ "$BUILD_DIR/.devcontainer"

        IMAGE_NAME="guardrail-check-$(date +%s)"
        devcontainer build \
            --image-name "$IMAGE_NAME" \
            --workspace-folder "$BUILD_DIR" 2>&1
        BUILD_EXIT=$?

        rm -rf "$BUILD_DIR"

        if [ $BUILD_EXIT -eq 0 ]; then
            pass "Docker image built successfully"
            BUILT_IMAGE="$IMAGE_NAME"
        else
            fail "Docker build FAILED (exit code $BUILD_EXIT)."
            echo ""
            echo "  Hints:"
            echo "  - Check that all COPY source paths exist relative to the project root"
            echo "  - Check that all package names in apt-get/pip/npm install are correct"
            echo "  - Check that the base image in FROM is valid and accessible"
        fi
    fi
else
    fail "Dockerfile or devcontainer.json is missing — cannot attempt Docker build."
fi

echo ""

# ------------------------------------------------------------------
# 3. Test run check
# ------------------------------------------------------------------
echo "[3/3] Running tests..."

if [ -n "$BUILT_IMAGE" ]; then
    ARTIFACTS_DIR=$(mktemp -d)
    CONTAINER_NAME="guardrail-run-$(date +%s)"

    docker run --network=host --name "$CONTAINER_NAME" "$BUILT_IMAGE" /run_all_tests.sh
    RUN_EXIT=$?

    docker cp "$CONTAINER_NAME:/test_artifacts/." "$ARTIFACTS_DIR/" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rmi "$BUILT_IMAGE" >/dev/null 2>&1 || true

    if [ $RUN_EXIT -eq 0 ]; then
        pass "Tests passed (exit 0)"
    else
        fail "Tests FAILED (exit code $RUN_EXIT)"
    fi

    if ls "$ARTIFACTS_DIR/junit/"*.xml >/dev/null 2>&1; then
        pass "JUnit XML found in /test_artifacts/junit/"

        # Count total tests across all JUnit XML files using xmlstarlet
        TOTAL_TESTS=0
        for xml_file in "$ARTIFACTS_DIR/junit/"*.xml; do
            # Sum tests= attribute from the root element (testsuites or testsuite)
            FILE_TESTS=$(xmlstarlet sel -t -v '/*/@tests' "$xml_file" 2>/dev/null || echo "0")
            if [ -n "$FILE_TESTS" ] && [ "$FILE_TESTS" -gt 0 ] 2>/dev/null; then
                TOTAL_TESTS=$((TOTAL_TESTS + FILE_TESTS))
            fi
        done

        if [ "$TOTAL_TESTS" -le 1 ]; then
            fail "JUnit XML reports only $TOTAL_TESTS test(s). Each test in the suite MUST appear as its own <testcase>. Do NOT wrap the entire suite in a single pytest/subprocess test."
            echo ""
            echo "  ============================================================"
            echo "  REFERENCE: JUnit XML Output — The Right Way per Framework"
            echo "  ============================================================"
            echo ""
            echo "  Python — pytest:"
            echo "    pytest tests/ --junitxml=/test_artifacts/junit/results.xml -v"
            echo ""
            echo "  Ruby — Rails minitest:"
            echo "    export MINITEST_REPORTERS_REPORTS_DIR=/test_artifacts/junit"
            echo "    bundle exec rails test"
            echo ""
            echo "  Node.js — built-in test runner (>=18):"
            echo "    node --test \\"
            echo "      --test-reporter=junit --test-reporter-destination=/test_artifacts/junit/results.xml \\"
            echo "      --test-reporter=spec  --test-reporter-destination=stdout \\"
            echo "      ./test/**/*.test.js"
            echo ""
            echo "  Node.js — mocha:"
            echo "    npm install mocha-junit-reporter"
            echo "    MOCHA_FILE=/test_artifacts/junit/results.xml \\"
            echo "      npx mocha --reporter mocha-junit-reporter --timeout 30000 test/"
            echo ""
            echo "  Node.js — mocha (Electron):"
            echo "    pnpm exec electron-mocha \\"
            echo "      --reporter mocha-junit-reporter \\"
            echo "      --reporter-options mochaFile=/test_artifacts/junit/results.xml \\"
            echo "      --timeout 10000 --recursive test/"
            echo ""
            echo "  Rust — cargo-nextest:"
            echo "    cargo nextest run --workspace"
            echo "    cp target/nextest/default/junit.xml /test_artifacts/junit/results.xml"
            echo ""
            echo "  Go — ginkgo:"
            echo "    ginkgo --junit-report=/test_artifacts/junit/results.xml ./..."
            echo ""
            echo "  Go — go test (via gotestsum):"
            echo "    gotestsum --junitfile /test_artifacts/junit/results.xml -- ./..."
            echo "    WARNING: Do NOT pipe go test through go-junit-report — it"
            echo "    aggregates sub-tests into a single <testcase> per package."
            echo ""
            echo "  C/C++ — ctest:"
            echo "    ctest --test-dir build --output-on-failure \\"
            echo "      --output-junit /test_artifacts/junit/results.xml \\"
            echo '      --parallel $(nproc)'
            echo ""
            echo "  Lua — busted:"
            echo "    busted --output junit -o /test_artifacts/junit/results.xml"
            echo ""
            echo "  Lua — Neovim plenary:"
            echo '    nvim --headless -u tests/minimal_init.lua -c "RunTests tests" 2>&1 | tee /tmp/test_output.txt'
            echo "    Then parse Success/Fail lines into JUnit XML with a Python script."
            echo "    NOTE: Many Neovim plugins use busted, not plenary. Check first."
            echo ""
            echo "  ❌ Anti-pattern — DO NOT DO THIS:"
            echo "    def test_entire_suite():"
            echo '        subprocess.run(["bash", "run_tests.sh"], check=True)'
            echo "    This reports 1 test regardless of how many actually ran."
            echo "  ============================================================"
            echo ""
        else
            pass "JUnit XML reports $TOTAL_TESTS tests"
        fi
    else
        fail "No JUnit XML found in /test_artifacts/junit/*.xml"
    fi

    if [ -f "$ARTIFACTS_DIR/final_result.json" ]; then
        pass "final_result.json found in /test_artifacts/"
    else
        fail "final_result.json not found in /test_artifacts/"
    fi

    rm -rf "$ARTIFACTS_DIR"
else
    fail "Docker image was not built — cannot run tests."
fi

echo ""

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo "========================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    echo "========================================"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "PASSED with $WARNINGS warning(s)"
    echo "========================================"
    exit 0
else
    echo "FAILED: $ERRORS error(s), $WARNINGS warning(s)"
    echo "Fix the errors above and run this script again."
    echo "========================================"
    exit 1
fi
