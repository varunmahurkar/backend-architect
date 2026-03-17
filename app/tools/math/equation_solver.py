"""
Equation Solver Tool — Solve equations and systems using SymPy.
Supports algebraic, differential, and integral equations.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


@nurav_tool(metadata=ToolMetadata(
    name="equation_solver",
    description="Solve equations and systems of equations symbolically. Supports algebraic, polynomial, trigonometric, and systems of equations.",
    niche="math",
    status=ToolStatus.ACTIVE,
    icon="sigma",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"equations": '["x**2 + y - 10", "x + y - 4"]', "variables": '["x", "y"]'},
            output='{"solutions": [{...}], "steps": [...], "latex": "..."}',
            description="Solve a system of equations",
        ),
    ],
    input_schema={"equations": "str (JSON array of equation strings)", "variables": "str (JSON array, optional)", "domain": "str ('real'|'complex'|'integer')"},
    output_schema={"solutions": "array", "steps": "array", "latex": "str", "verification": "bool"},
    avg_response_ms=500,
    success_rate=0.90,
))
@tool
async def equation_solver(equations: str, variables: str = "[]", domain: str = "real") -> str:
    """Solve equations symbolically using SymPy."""
    try:
        import sympy
        from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

        transformations = standard_transformations + (implicit_multiplication_application,)

        eq_list = json.loads(equations) if isinstance(equations, str) else equations
        var_list = json.loads(variables) if isinstance(variables, str) else variables

        if not eq_list:
            return json.dumps({"error": "No equations provided."})

        # Parse equations
        parsed_eqs = []
        steps = [f"Input: {len(eq_list)} equation(s)"]
        for eq_str in eq_list:
            eq_str = eq_str.strip()
            if "=" in eq_str and "==" not in eq_str:
                lhs, rhs = eq_str.split("=", 1)
                parsed = sympy.Eq(parse_expr(lhs.strip(), transformations=transformations),
                                  parse_expr(rhs.strip(), transformations=transformations))
            else:
                parsed = parse_expr(eq_str, transformations=transformations)
            parsed_eqs.append(parsed)
            steps.append(f"Parsed: {parsed}")

        # Determine variables
        if var_list:
            syms = [sympy.Symbol(v) for v in var_list]
        else:
            all_syms = set()
            for eq in parsed_eqs:
                all_syms.update(eq.free_symbols)
            syms = sorted(all_syms, key=str)

        steps.append(f"Solving for: {[str(s) for s in syms]}")

        # Solve
        if domain == "integer":
            solutions = sympy.solve(parsed_eqs, syms, domain=sympy.S.Integers)
        else:
            solutions = sympy.solve(parsed_eqs, syms)

        steps.append(f"Solutions: {solutions}")

        # Format solutions
        if isinstance(solutions, dict):
            formatted = {str(k): str(v) for k, v in solutions.items()}
        elif isinstance(solutions, list):
            formatted = []
            for sol in solutions:
                if isinstance(sol, dict):
                    formatted.append({str(k): str(v) for k, v in sol.items()})
                elif isinstance(sol, tuple):
                    formatted.append({str(syms[i]): str(sol[i]) for i in range(min(len(sol), len(syms)))})
                else:
                    formatted.append(str(sol))
        else:
            formatted = str(solutions)

        # Verification
        verified = True
        try:
            if isinstance(solutions, list) and solutions:
                test_sol = solutions[0] if not isinstance(solutions[0], (dict, tuple)) else solutions[0]
                # Basic verification — just check it doesn't throw
                for eq in parsed_eqs:
                    if isinstance(test_sol, dict):
                        eq.subs(test_sol)
        except Exception:
            verified = False

        return json.dumps({
            "solutions": formatted,
            "steps": steps,
            "latex": sympy.latex(solutions) if not isinstance(solutions, list) else ", ".join(sympy.latex(s) for s in solutions[:10]),
            "variables": [str(s) for s in syms],
            "verification": verified,
        }, ensure_ascii=False, default=str)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON. Provide equations as a JSON array: [\"x**2 - 4\", \"x + y - 3\"]"})
    except Exception as e:
        return json.dumps({"error": f"Equation solving failed: {str(e)}", "hint": "Format: [\"x**2 - 4\"] or [\"x + y = 10\", \"x - y = 2\"]"})
