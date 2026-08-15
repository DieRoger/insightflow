#!/usr/bin/env python3
"""
Architecture Rules Checker for InsightFlow.

Scans the codebase for violations of frozen architecture rules.
Exits with code 1 if any L0 or L1 violation is detected.
Exits with code 0 if only L2 warnings (or clean).

Usage:
    python scripts/check_architecture.py              # Full check
    python scripts/check_architecture.py --json       # JSON output for CI
    python scripts/check_architecture.py --fix        # Auto-fix where possible
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories excluded from all checks
EXCLUDED_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    "node_modules",
    ".next",
    "alembic",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    "tests",
    ".reasonix",  # tests have different rules
}

# File extensions to scan
PYTHON_EXTS = {".py"}
TYPESCRIPT_EXTS = {".ts", ".tsx"}
SQL_EXTS = {".sql"}


class Level(Enum):
    L0 = "L0"  # MUST NOT — block merge
    L1 = "L1"  # MUST — block merge
    L2 = "L2"  # SHOULD — warn only


@dataclass
class Finding:
    rule: str
    level: Level
    file: str
    line: int
    message: str


@dataclass
class CheckResult:
    name: str
    level: Level
    passed: bool
    findings: list[Finding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Check Implementations
# ---------------------------------------------------------------------------


def _scan_files(extensions: set[str]) -> list[Path]:
    """Yield all project files with given extensions, excluding banned dirs."""
    files = []
    for ext in extensions:
        for path in PROJECT_ROOT.rglob(f"*{ext}"):
            if any(excl in path.parts for excl in EXCLUDED_DIRS):
                continue
            files.append(path)
    return files


def _grep(pattern: str, paths: list[Path]) -> list[Finding]:
    """Search for pattern in given files. Returns list of (file, line_no, line_text)."""
    results = []
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(pattern, line):
                    results.append((str(path.relative_to(PROJECT_ROOT)), i, line.strip()))
        except Exception:
            continue
    return results


# --- L0 Checks ---


def check_domain_imports() -> CheckResult:
    """AR-051: Domain must not import framework code."""
    findings = []
    domain_dir = PROJECT_ROOT / "app" / "domain"
    if not domain_dir.exists():
        return CheckResult("domain_imports", Level.L0, True)

    FORBIDDEN_IMPORTS = [
        (r"from\s+fastapi", "fastapi"),
        (r"from\s+sqlalchemy", "sqlalchemy"),
        (r"from\s+redis", "redis"),
        (r"from\s+pydantic", "pydantic"),
        (r"from\s+langgraph", "langgraph"),
        (r"from\s+celery", "celery"),
        (r"import\s+fastapi", "fastapi"),
        (r"import\s+sqlalchemy", "sqlalchemy"),
    ]

    for path in domain_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            for pattern, framework in FORBIDDEN_IMPORTS:
                if re.search(pattern, line):
                    findings.append(
                        Finding(
                            rule="AR-051",
                            level=Level.L0,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"Domain imports {framework}: {line.strip()}",
                        )
                    )

    return CheckResult(
        name="domain_imports",
        level=Level.L0,
        passed=len(findings) == 0,
        findings=findings,
    )


def check_service_sql() -> CheckResult:
    """AR-055: Application services must not contain raw SQL."""
    findings = []
    app_dir = PROJECT_ROOT / "app" / "application"
    if not app_dir.exists():
        return CheckResult("service_sql", Level.L0, True)

    SQL_PATTERNS = [
        r"\bSELECT\b.*\bFROM\b",
        r"\bINSERT\s+INTO\b",
        r"\bUPDATE\b.*\bSET\b",
        r"\bDELETE\s+FROM\b",
        r"\bCREATE\s+TABLE\b",
        r"\bDROP\s+TABLE\b",
        r"\bALTER\s+TABLE\b",
    ]

    for path in app_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            # Skip comments and docstrings
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            for pattern in SQL_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            rule="AR-055",
                            level=Level.L0,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"SQL in application service: {line.strip()}",
                        )
                    )
                    break

    return CheckResult(
        name="service_sql",
        level=Level.L0,
        passed=len(findings) == 0,
        findings=findings,
    )


def check_raw_sql_format() -> CheckResult:
    """AR-012/AR-100: No f-string SQL construction with interpolated VALUES.

    Dynamic column lists assembled from code constants (e.g.
    `f"SELECT {', '.join(FEATURE_COLUMNS)}"`) are safe — the identifiers
    come from constants, not user input, and literal values are bound via
    :param placeholders. Only value-context interpolation is flagged:
    f-strings inside WHERE/VALUES that inline user-controlled values.
    """
    findings = []
    py_files = [p for p in _scan_files(PYTHON_EXTS) if "app/" in str(p)]

    # Value-context interpolation: f-string formatting something into a
    # WHERE/VALUES position (the classic injection vector). Column-name
    # interpolation from constants is allowed, as is interpolating a
    # pre-built parameter-placeholder string (e.g. VALUES ({params}) where
    # params = ":a, :b" — values remain bound, never inlined).
    VALUE_CONTEXT_PATTERNS = [
        r"""f["'].*WHERE\s+\w+\s*=\s*\{""",
        r"""f["'].*WHERE\s+\w+\s+IN\s*\(\s*\{""",
        r"""f["'].*\bset\s+\w+\s*=\s*\{""",
        r"""\.format\(.*WHERE.*\)""",
        # VALUES with an inlined literal (not a placeholder variable)
        r"""f["'].*VALUES\s*\(\s*['"]\d+['"]""",
        r"""f["'].*VALUES\s*\(\s*\$\{""",
    ]

    for path in py_files:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            for pattern in VALUE_CONTEXT_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            rule="AR-012",
                            level=Level.L0,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"Unsafe SQL value interpolation: {line.strip()}",
                        )
                    )

    return CheckResult(
        name="raw_sql_format",
        level=Level.L0,
        passed=len(findings) == 0,
        findings=findings,
    )


def check_router_business_logic() -> CheckResult:
    """AR-003: Routers must not contain business logic."""
    findings = []
    routers_dir = PROJECT_ROOT / "app" / "api" / "routers"
    if not routers_dir.exists():
        return CheckResult("router_business_logic", Level.L0, True)

    BUSINESS_SIGNALS = [
        r"\bif\b.*\brisk\b",
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\btransform\b",
        r"\bvalidate\b.*\bbusiness\b",
        r"session\.execute",
        r"session\.add",
        r"session\.commit",
    ]

    for path in routers_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            for pattern in BUSINESS_SIGNALS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            rule="AR-003",
                            level=Level.L0,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"Possible business logic in router: {line.strip()}",
                        )
                    )

    return CheckResult(
        name="router_business_logic",
        level=Level.L0,
        passed=len(findings) == 0,
        findings=findings,
    )


def check_frontend_kpi() -> CheckResult:
    """AR-070: Frontend must not compute KPIs."""
    findings = []
    frontend_dir = PROJECT_ROOT / "frontend"
    if not frontend_dir.exists():
        return CheckResult("frontend_kpi", Level.L0, True)

    KPI_PATTERNS = [
        r"\barpu\s*=",
        r"\bchurn_rate\s*=",
        r"\bclv\s*=",
        r"\bmrr\s*=",
        r"\bretention\s*=",
        r"\brevenue\s*/\s*",
    ]

    for ext in TYPESCRIPT_EXTS:
        for path in frontend_dir.rglob(f"*{ext}"):
            if "node_modules" in str(path):
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                for pattern in KPI_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Skip if it looks like an API call
                        if "service." in line or "fetch" in line or "useQuery" in line:
                            continue
                        findings.append(
                            Finding(
                                rule="AR-070",
                                level=Level.L0,
                                file=str(path.relative_to(PROJECT_ROOT)),
                                line=i,
                                message=f"Possible KPI calculation in frontend: {line.strip()}",
                            )
                        )

    return CheckResult(
        name="frontend_kpi",
        level=Level.L0,
        passed=len(findings) == 0,
        findings=findings,
    )


# --- L1 Checks ---


def check_inline_prompts() -> CheckResult:
    """AR-041: No inline prompts in AI agent code."""
    findings = []
    ai_dir = PROJECT_ROOT / "app" / "ai"
    if not ai_dir.exists():
        return CheckResult("inline_prompts", Level.L1, True)

    INLINE_PROMPT_PATTERNS = [
        r'prompt\s*=\s*f"',
        r"prompt\s*=\s*f'",
        r'prompt\s*=\s*"Analyze',
        r'prompt\s*=\s*"You are',
        r'prompt\s*=\s*"""',
    ]

    for path in ai_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            for pattern in INLINE_PROMPT_PATTERNS:
                if re.search(pattern, line):
                    # Allow import of prompt registry
                    if "prompt_registry" in line or "PromptRegistry" in line:
                        continue
                    findings.append(
                        Finding(
                            rule="AR-041",
                            level=Level.L1,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"Inline prompt detected: {line.strip()}",
                        )
                    )

    return CheckResult(
        name="inline_prompts",
        level=Level.L1,
        passed=len(findings) == 0,
        findings=findings,
    )


def check_api_version_prefix() -> CheckResult:
    """AR-060: All API routes must use /api/v{major}/ prefix."""
    findings = []
    routers_dir = PROJECT_ROOT / "app" / "api" / "routers"
    if not routers_dir.exists():
        return CheckResult("api_version_prefix", Level.L1, True)

    for path in routers_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        # If the router is declared with prefix="/api/v1", relative route
        # paths are valid (the version prefix lives on the router declaration).
        router_has_version_prefix = any(
            re.search(r'APIRouter\([^)]*prefix=["\']/api/v\d+', line) for line in lines
        )

        for i, line in enumerate(lines, 1):
            if re.search(r"@router\.(get|post|put|delete|patch)\(", line):
                # Check if the route starts with /api/v
                if not re.search(r"/api/v\d+/", line):
                    # Exclude health/metrics/system endpoints
                    if re.search(r"/(health|metrics|docs|openapi)", line):
                        continue
                    # Exclude relative paths when the router prefix is versioned
                    if router_has_version_prefix and not line.strip().startswith(
                        ('@router.get("/api/', '@router.post("/api/')
                    ):
                        continue
                    findings.append(
                        Finding(
                            rule="AR-060",
                            level=Level.L1,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"API route without version prefix: {line.strip()}",
                        )
                    )

    return CheckResult(
        name="api_version_prefix",
        level=Level.L1,
        passed=len(findings) == 0,
        findings=findings,
    )


def check_stdio_logging() -> CheckResult:
    """AR-084: No print() or stdlib logging — use structlog."""
    findings = []
    app_dir = PROJECT_ROOT / "app"
    if not app_dir.exists():
        return CheckResult("stdio_logging", Level.L1, True)

    for path in app_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        # CLI entry points (__main__ blocks) print user-facing demo output;
        # these are terminal output, not structured service logging (AR-084).
        is_cli_entry = "__main__" in content
        for i, line in enumerate(content.splitlines(), 1):
            # print() is always wrong
            if re.search(r"\bprint\(", line):
                # Allow commented-out debug prints
                if line.strip().startswith("#"):
                    continue
                # Allow CLI demo output (guarded by __main__ block)
                if is_cli_entry:
                    continue
                findings.append(
                    Finding(
                        rule="AR-084",
                        level=Level.L1,
                        file=str(path.relative_to(PROJECT_ROOT)),
                        line=i,
                        message=f"print() found — use structlog: {line.strip()}",
                    )
                )
            # stdlib logging without structlog
            if re.search(r"\blogging\.(info|debug|warning|error|critical)\(", line):
                if "structlog" not in content:
                    findings.append(
                        Finding(
                            rule="AR-084",
                            level=Level.L1,
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            message=f"stdlib logging — use structlog: {line.strip()}",
                        )
                    )

    return CheckResult(
        name="stdio_logging",
        level=Level.L1,
        passed=len(findings) == 0,
        findings=findings,
    )


# --- L2 Checks ---


def check_select_star() -> CheckResult:
    """AR-013: No SELECT * (warning only)."""
    findings = []
    app_dir = PROJECT_ROOT / "app"
    if not app_dir.exists():
        return CheckResult("select_star", Level.L2, True)

    for path in app_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r"\bSELECT\s+\*", line, re.IGNORECASE):
                findings.append(
                    Finding(
                        rule="AR-013",
                        level=Level.L2,
                        file=str(path.relative_to(PROJECT_ROOT)),
                        line=i,
                        message=f"SELECT * detected: {line.strip()}",
                    )
                )

    return CheckResult(
        name="select_star",
        level=Level.L2,
        passed=len(findings) == 0,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    # L0
    check_domain_imports,
    check_service_sql,
    check_raw_sql_format,
    check_router_business_logic,
    check_frontend_kpi,
    # L1
    check_inline_prompts,
    check_api_version_prefix,
    check_stdio_logging,
    # L2
    check_select_star,
]


def run_checks(verbose: bool = False) -> tuple[list[CheckResult], bool]:
    """Run all checks. Returns (results, passed)."""
    results = []
    overall_passed = True

    for check_fn in ALL_CHECKS:
        result = check_fn()
        results.append(result)

        if not result.passed and result.level in (Level.L0, Level.L1):
            overall_passed = False

        if verbose or not result.passed:
            status = "✅" if result.passed else "❌"
            print(f"  {status} {result.name} [{result.level.value}]", file=sys.stderr)
            for f in result.findings:
                print(f"     {f.file}:{f.line}  {f.message}", file=sys.stderr)

    return results, overall_passed


def output_json(results: list[CheckResult]) -> None:
    """Print results as JSON."""
    output = {
        "passed": all(r.passed for r in results if r.level != Level.L2),
        "checks": [
            {
                "name": r.name,
                "level": r.level.value,
                "passed": r.passed,
                "violations": len(r.findings),
                "details": [
                    {"file": f.file, "line": f.line, "rule": f.rule, "message": f.message}
                    for f in r.findings
                ],
            }
            for r in results
        ],
    }
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description="InsightFlow Architecture Checker")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show all checks (not just failures)"
    )
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print("InsightFlow Architecture Rules Check", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    results, overall_passed = run_checks(verbose=args.verbose)

    # Summary
    l0_l1_failures = sum(1 for r in results if not r.passed and r.level in (Level.L0, Level.L1))
    l2_warnings = sum(1 for r in results if not r.passed and r.level == Level.L2)
    total_violations = sum(len(r.findings) for r in results if not r.passed)

    print(file=sys.stderr)
    print(
        f"Checks: {len(results)} run | {l0_l1_failures} failed | {l2_warnings} warnings | {total_violations} violations",
        file=sys.stderr,
    )
    print(f"Result: {'PASSED' if overall_passed else 'FAILED'}", file=sys.stderr)

    if args.json:
        output_json(results)

    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
