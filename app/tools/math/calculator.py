"""
Calculator Tool — Symbolic math solver using SymPy.
Handles arithmetic, algebra, calculus, linear algebra, and statistics.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _evaluate(expression: str, show_steps: bool, precision: int) -> dict:
    """Evaluate a math expression using SymPy."""
    import sympy
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor,
    )

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )

    steps = []
    expr_clean = expression.strip()

    # Try to detect and handle different expression types
    steps.append(f"Input: {expr_clean}")

    # Handle "solve" keyword
    if expr_clean.lower().startswith("solve"):
        inner = expr_clean[5:].strip().lstrip("(").rstrip(")")
        # Split on comma for variable specification
        parts = [p.strip() for p in inner.split(",")]
        eq_str = parts[0]
        var = sympy.Symbol(parts[1]) if len(parts) > 1 else None

        # Handle equations with =
        if "=" in eq_str and "==" not in eq_str:
            lhs, rhs = eq_str.split("=", 1)
            eq = sympy.Eq(parse_expr(lhs, transformations=transformations),
                          parse_expr(rhs, transformations=transformations))
        else:
            eq = parse_expr(eq_str, transformations=transformations)

        if var:
            result = sympy.solve(eq, var)
        else:
            result = sympy.solve(eq)

        steps.append(f"Solving: {eq}")
        steps.append(f"Solutions: {result}")

        return {
            "result": str(result),
            "expression": expr_clean,
            "steps": steps,
            "latex": sympy.latex(result) if not isinstance(result, list) else ", ".join(sympy.latex(r) for r in result),
            "numeric_value": None,
        }

    # Handle derivative
    if expr_clean.lower().startswith("diff") or expr_clean.lower().startswith("derivative"):
        inner = expr_clean.split("(", 1)[1].rstrip(")") if "(" in expr_clean else expr_clean.split(" ", 1)[1]
        parts = [p.strip() for p in inner.split(",")]
        expr_parsed = parse_expr(parts[0], transformations=transformations)
        var = sympy.Symbol(parts[1]) if len(parts) > 1 else list(expr_parsed.free_symbols)[0] if expr_parsed.free_symbols else sympy.Symbol("x")

        result = sympy.diff(expr_parsed, var)
        steps.append(f"d/d{var}({expr_parsed}) = {result}")

        return {
            "result": str(result),
            "expression": expr_clean,
            "steps": steps,
            "latex": sympy.latex(result),
            "numeric_value": None,
        }

    # Handle integral
    if expr_clean.lower().startswith("integrate") or expr_clean.lower().startswith("integral"):
        inner = expr_clean.split("(", 1)[1].rstrip(")") if "(" in expr_clean else expr_clean.split(" ", 1)[1]
        parts = [p.strip() for p in inner.split(",")]
        expr_parsed = parse_expr(parts[0], transformations=transformations)
        var = sympy.Symbol(parts[1]) if len(parts) > 1 else list(expr_parsed.free_symbols)[0] if expr_parsed.free_symbols else sympy.Symbol("x")

        result = sympy.integrate(expr_parsed, var)
        steps.append(f"∫({expr_parsed}) d{var} = {result} + C")

        return {
            "result": str(result),
            "expression": expr_clean,
            "steps": steps,
            "latex": sympy.latex(result),
            "numeric_value": None,
        }

    # Handle simplify
    if expr_clean.lower().startswith("simplify"):
        inner = expr_clean.split("(", 1)[1].rstrip(")") if "(" in expr_clean else expr_clean.split(" ", 1)[1]
        expr_parsed = parse_expr(inner, transformations=transformations)
        result = sympy.simplify(expr_parsed)
        steps.append(f"Simplified: {expr_parsed} → {result}")

        return {
            "result": str(result),
            "expression": expr_clean,
            "steps": steps,
            "latex": sympy.latex(result),
            "numeric_value": float(result) if result.is_number else None,
        }

    # Handle factor
    if expr_clean.lower().startswith("factor"):
        inner = expr_clean.split("(", 1)[1].rstrip(")") if "(" in expr_clean else expr_clean.split(" ", 1)[1]
        expr_parsed = parse_expr(inner, transformations=transformations)
        result = sympy.factor(expr_parsed)
        steps.append(f"Factored: {expr_parsed} → {result}")

        return {
            "result": str(result),
            "expression": expr_clean,
            "steps": steps,
            "latex": sympy.latex(result),
            "numeric_value": None,
        }

    # Handle expand
    if expr_clean.lower().startswith("expand"):
        inner = expr_clean.split("(", 1)[1].rstrip(")") if "(" in expr_clean else expr_clean.split(" ", 1)[1]
        expr_parsed = parse_expr(inner, transformations=transformations)
        result = sympy.expand(expr_parsed)
        steps.append(f"Expanded: {expr_parsed} → {result}")

        return {
            "result": str(result),
            "expression": expr_clean,
            "steps": steps,
            "latex": sympy.latex(result),
            "numeric_value": None,
        }

    # Default: evaluate expression
    expr_parsed = parse_expr(expr_clean, transformations=transformations)
    steps.append(f"Parsed: {expr_parsed}")

    # Try to simplify
    simplified = sympy.simplify(expr_parsed)
    if simplified != expr_parsed:
        steps.append(f"Simplified: {simplified}")

    # Try numeric evaluation
    numeric = None
    try:
        numeric = float(simplified.evalf(precision))
        steps.append(f"Numeric: {numeric}")
    except (TypeError, ValueError, AttributeError):
        pass

    return {
        "result": str(simplified),
        "expression": expr_clean,
        "steps": steps,
        "latex": sympy.latex(simplified),
        "numeric_value": numeric,
    }


@nurav_tool(metadata=ToolMetadata(
    name="calculator",
    description="Symbolic math solver with step-by-step solutions. Handles arithmetic, algebra, calculus (derivatives/integrals), simplification, factoring, and equation solving.",
    niche="math",
    status=ToolStatus.ACTIVE,
    icon="calculator",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"expression": "6 * 7 + 3**2"},
            output='{"result": "51", "steps": ["Input: 6 * 7 + 3**2", "Parsed: 51"], "latex": "51", "numeric_value": 51.0}',
            description="Evaluate arithmetic",
        ),
        ToolExample(
            input={"expression": "solve(x**2 - 5*x + 6, x)"},
            output='{"result": "[2, 3]", "steps": ["..."], "latex": "2, 3"}',
            description="Solve a quadratic equation",
        ),
        ToolExample(
            input={"expression": "diff(x**3 + 2*x, x)"},
            output='{"result": "3*x**2 + 2", "steps": ["..."], "latex": "3 x^{2} + 2"}',
            description="Compute a derivative",
        ),
    ],
    input_schema={"expression": "str", "show_steps": "bool (default true)", "precision": "int (default 10)"},
    output_schema={"result": "str", "expression": "str", "steps": "array", "latex": "str", "numeric_value": "float|null"},
    avg_response_ms=200,
    success_rate=0.95,
))
@tool
async def calculator(expression: str, show_steps: bool = True, precision: int = 10) -> str:
    """Solve mathematical expressions with step-by-step solutions. Supports arithmetic, algebra, calculus, and more."""
    try:
        result = _evaluate(expression, show_steps, precision)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to evaluate expression: {str(e)}",
            "expression": expression,
            "hint": "Try formats like: '2+3', 'solve(x**2-4, x)', 'diff(x**3, x)', 'integrate(sin(x), x)', 'factor(x**2-4)'",
        })
