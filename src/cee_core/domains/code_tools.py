"""Real tool implementations for code review domain.

Provides actual code analysis, linting, and code quality tools
that integrate with the CEE tool execution framework.
"""

from __future__ import annotations

import ast
import re
from typing import Any, List, Dict, Optional

from ..tool_executor import ToolExecutionContext, ToolExecutionResult


def _count_complexity(code: str) -> Dict[str, Any]:
    """Calculate code complexity metrics."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"error": f"Syntax error: {str(e)}"}
    
    functions = []
    classes = []
    lines = code.split('\n')
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            complexity = _calculate_function_complexity(node)
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "cyclomatic_complexity": complexity,
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "method_count": sum(
                    1 for n in ast.walk(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ),
            })
    
    return {
        "function_count": len(functions),
        "class_count": len(classes),
        "line_count": len(lines),
        "functions": functions,
        "classes": classes,
        "avg_complexity": (
            round(sum(f["cyclomatic_complexity"] for f in functions) / len(functions), 2)
            if functions else 0
        ),
    }


def _calculate_function_complexity(func_node: ast.FunctionDef) -> int:
    """Calculate cyclomatic complexity for a function."""
    complexity = 1
    for node in ast.walk(func_node):
        if isinstance(node, (ast.If, ast.While, ast.For)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.ExceptHandler):
            complexity += 1
        elif isinstance(node, ast.With):
            complexity += 1
        elif isinstance(node, ast.Assert):
            complexity += 1
        elif isinstance(node, ast.comprehension):
            complexity += 1
            if node.ifs:
                complexity += len(node.ifs)
    return complexity


def _find_code_issues(code: str) -> List[Dict[str, Any]]:
    """Find common code issues using pattern matching and AST analysis."""
    issues = []
    lines = code.split('\n')
    
    try:
        tree = ast.parse(code)
    except SyntaxError:
        issues.append({
            "severity": "error",
            "line": 0,
            "message": "Code has syntax errors",
            "category": "syntax",
        })
        return issues
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if len(node.args.args) > 5:
                issues.append({
                    "severity": "warning",
                    "line": node.lineno,
                    "message": f"Function {node.name} has too many parameters ({len(node.args.args)})",
                    "category": "design",
                })
            docstring = ast.get_docstring(node)
            if not docstring:
                issues.append({
                    "severity": "info",
                    "line": node.lineno,
                    "message": f"Function {node.name} is missing docstring",
                    "category": "documentation",
                })
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if len(stripped) > 120:
            issues.append({
                "severity": "warning",
                "line": i,
                "message": f"Line too long ({len(stripped)} > 120)",
                "category": "style",
            })
        if 'print(' in stripped and not stripped.startswith('#'):
            issues.append({
                "severity": "info",
                "line": i,
                "message": "Consider using logging instead of print",
                "category": "best_practice",
            })
        if stripped.startswith('import ') and stripped.count('.') > 3:
            issues.append({
                "severity": "info",
                "line": i,
                "message": "Deep import path detected",
                "category": "design",
            })
    
    return sorted(issues, key=lambda x: (x["line"], x["severity"]))


def handle_analyze_code(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Analyze code and return structured metrics."""
    code = ctx.arguments.get("code", "")
    if not code:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="code argument is required",
        )

    complexity = _count_complexity(code)
    issues = _find_code_issues(code)
    
    result = {
        "complexity_metrics": complexity,
        "issues": issues,
        "issue_summary": {
            "error": sum(1 for i in issues if i["severity"] == "error"),
            "warning": sum(1 for i in issues if i["severity"] == "warning"),
            "info": sum(1 for i in issues if i["severity"] == "info"),
        },
    }

    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )


def handle_check_code_style(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Check code style and formatting issues."""
    code = ctx.arguments.get("code", "")
    if not code:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="code argument is required",
        )

    style_issues = []
    lines = code.split('\n')
    
    for i, line in enumerate(lines, 1):
        if line != line.rstrip():
            style_issues.append({
                "line": i,
                "message": "Trailing whitespace",
            })
        if '\t' in line:
            style_issues.append({
                "line": i,
                "message": "Tab character detected (use spaces)",
            })
    
    if lines and not lines[-1].endswith('\n'):
        style_issues.append({
            "line": len(lines),
            "message": "File does not end with newline",
        })
    
    blank_lines = 0
    for line in lines:
        if line.strip() == '':
            blank_lines += 1
            if blank_lines > 2:
                style_issues.append({
                    "line": lines.index(line) + 1,
                    "message": "Too many consecutive blank lines",
                })
        else:
            blank_lines = 0
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result={
            "style_issues": style_issues,
            "issue_count": len(style_issues),
        },
    )


def handle_find_code_patterns(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Find specific patterns in code using regex."""
    code = ctx.arguments.get("code", "")
    pattern = ctx.arguments.get("pattern", "")
    
    if not code or not pattern:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="both code and pattern arguments are required",
        )

    try:
        compiled_pattern = re.compile(pattern)
    except re.error as e:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message=f"Invalid regex pattern: {str(e)}",
        )

    matches = []
    for i, line in enumerate(code.split('\n'), 1):
        for m in compiled_pattern.finditer(line):
            matches.append({
                "line": i,
                "match": m.group(),
                "start": m.start(),
                "end": m.end(),
            })
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result={
            "matches": matches,
            "match_count": len(matches),
            "pattern": pattern,
        },
    )
