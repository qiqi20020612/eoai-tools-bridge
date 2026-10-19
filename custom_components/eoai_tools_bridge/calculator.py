"""Bound numeric inputs before the upstream SymPy-backed calculator runs."""

import ast
import math
import operator
import re
from typing import Any

import probatio as vol
from homeassistant.helpers import llm

from .const import API_ID

CALCULATOR_PAIR = ("basic_utilities", "calculate")
MAX_ITEMS = 32
MAX_EXPRESSION_CHARS = 256
MAX_EXPRESSION_NODES = 64
MAX_EXPRESSION_DEPTH = 8
MAX_NUMBER = 1e100
MIN_NONZERO = 1e-100
MAX_EXPONENT = 32
_CHARACTERS = re.compile(r"[0-9A-Za-z_+\-*/%^().,\s]+\Z", re.ASCII)
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: math.pow,
}
_FUNCTIONS = {
    "sqrt": (math.sqrt, 1, 1),
    "sin": (math.sin, 1, 1),
    "cos": (math.cos, 1, 1),
    "tan": (math.tan, 1, 1),
    "exp": (math.exp, 1, 1),
    "log": (math.log, 1, 2),
    "Abs": (abs, 1, 1),
    "abs": (abs, 1, 1),
    "floor": (math.floor, 1, 1),
    "ceiling": (math.ceil, 1, 1),
    "Min": (min, 2, 8),
    "Max": (max, 2, 8),
}
_CONSTANTS = {"pi": math.pi, "E": math.e}


def is_calculator(api_id: str, tool: llm.Tool) -> bool:
    """Use public identity only; do not import the provider in production."""
    return (api_id, tool.name) == CALCULATOR_PAIR and tool.integration == API_ID


def calculator_constraints() -> dict[str, Any]:
    """Advertise extra input limits without widening the native schema."""
    return {
        "max_data_items": MAX_ITEMS,
        "expression_data_items": 1,
        "max_expression_characters": MAX_EXPRESSION_CHARS,
        "max_expression_nodes": MAX_EXPRESSION_NODES,
        "max_expression_depth": MAX_EXPRESSION_DEPTH,
        "max_absolute_number": MAX_NUMBER,
        "min_nonzero_absolute_number": MIN_NONZERO,
        "max_absolute_exponent": MAX_EXPONENT,
        "functions": sorted(_FUNCTIONS),
        "constants": sorted(_CONSTANTS),
        "operators": ["+", "-", "*", "/", "//", "%", "**", "^"],
    }


def _number(value: Any) -> float:
    if type(value) not in {int, float}:
        raise ValueError
    result = float(value)
    if (
        not math.isfinite(result)
        or abs(result) > MAX_NUMBER
        or (result and abs(result) < MIN_NONZERO)
    ):
        raise ValueError
    return result


def _validate_expression(expression: str) -> None:
    """Estimate numeric bounds with a small AST grammar, never eval/sympify."""
    if not expression or len(expression) > MAX_EXPRESSION_CHARS:
        raise ValueError
    if not _CHARACTERS.fullmatch(expression):
        raise ValueError
    tree = ast.parse(expression.strip().replace("^", "**"), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_EXPRESSION_NODES:
        raise ValueError

    def visit(node: ast.AST, depth: int = 0) -> float:
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError
        if isinstance(node, ast.Constant):
            return _number(node.value)
        if isinstance(node, ast.Name) and node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in {ast.UAdd, ast.USub}:
            value = visit(node.operand, depth + 1)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
                raise ValueError
            result = _number(_OPERATORS[type(node.op)](left, right))
            if (
                isinstance(node.op, ast.Mult | ast.Div | ast.Pow)
                and left != 0
                and right != 0
                and result == 0
            ):
                raise ValueError
            return result
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in _FUNCTIONS or node.keywords:
                raise ValueError
            function, minimum, maximum = _FUNCTIONS[node.func.id]
            if not minimum <= len(node.args) <= maximum:
                raise ValueError
            values = [visit(arg, depth + 1) for arg in node.args]
            result = _number(function(*values))
            if node.func.id == "exp" and result == 0:
                raise ValueError
            return result
        raise ValueError

    visit(tree.body)


def validate_calculator_args(arguments: dict[str, Any]) -> None:
    """Reject code, unbounded work and non-numeric inputs before dispatch.

    The estimate is discarded. The original upstream calculator produces the
    result from unchanged input; this module is only an argument guard.
    """
    try:
        operation, data = arguments["operation"], arguments["data"]
        if not isinstance(data, list) or not 1 <= len(data) <= MAX_ITEMS:
            raise ValueError
        if not all(isinstance(value, str) for value in data):
            raise ValueError
        if operation == "expression":
            if len(data) != 1:
                raise ValueError
            _validate_expression(data[0])
        elif operation in {"min", "max", "avg"}:
            for value in data:
                if len(value) > 64:
                    raise ValueError
                _number(float(value))
        else:
            raise ValueError
    except (
        KeyError,
        TypeError,
        ValueError,
        SyntaxError,
        ArithmeticError,
        RecursionError,
    ):
        raise vol.Invalid("Calculator requires bounded numeric arguments") from None
