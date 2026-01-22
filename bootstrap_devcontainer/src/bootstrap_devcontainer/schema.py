from pydantic import BaseModel


class TokenSpending(BaseModel):
    input: int = 0
    cached: int = 0
    output: int = 0
    cache_creation: int = 0


class PythonTestSummary(BaseModel):
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    passed_tests: list[str] = []


class BootstrapResult(BaseModel):
    success: bool
    agent_work_time: float
    verification_wall_time: float | None = None
    model: str = ""
    token_spending: TokenSpending
    cost_usd: float
    agent_exit_code: int
    python_test_summary: PythonTestSummary | None = None
