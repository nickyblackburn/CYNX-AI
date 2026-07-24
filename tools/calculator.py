"""
Simple calculator tool that evaluates arithmetic expressions safely using ast.
"""
import ast
from typing import Dict
from tools.base import BaseTool, ToolResult


class CalculatorTool(BaseTool):
    name = 'calculator'
    description = 'Evaluate arithmetic expressions safely.'

    def _safe_eval(self, expr: str) -> float:
        node = ast.parse(expr, mode='eval')
        for n in ast.walk(node):
            if not isinstance(n, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Load,
                                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
                                   ast.USub, ast.UAdd, ast.FloorDiv, ast.Call, ast.Constant)):
                raise ValueError(f"Unsupported expression element: {type(n).__name__}")
        # Evaluate in a restricted namespace
        return eval(compile(node, '<ast>', 'eval'), {'__builtins__': {}}, {})

    def call(self, args: Dict) -> ToolResult:
        expr = args.get('expression') or args.get('expr') or ''
        if not expr:
            return ToolResult(False, 'No expression provided')
        try:
            value = self._safe_eval(expr)
            return ToolResult(True, str(value))
        except Exception as e:
            return ToolResult(False, f'Error evaluating expression: {e}')
