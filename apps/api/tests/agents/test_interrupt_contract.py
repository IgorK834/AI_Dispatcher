"""The approval gate: interrupt() is never caught and only the gate can write (FR-3, FR-14)."""

import ast
from pathlib import Path

AGENTS = Path(__file__).parents[2] / "src/routepilot/agents"


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def calls(tree: ast.AST, name: str) -> list[ast.Call]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if (isinstance(target, ast.Name) and target.id == name) or (
                isinstance(target, ast.Attribute) and target.attr == name
            ):
                found.append(node)
    return found


def inside_try(tree: ast.AST, call: ast.Call) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Try | ast.TryStar):
            guarded = [*node.body, *node.handlers, *node.orelse, *node.finalbody]
            if any(call is inner for item in guarded for inner in ast.walk(item)):
                return True
    return False


def function_of(tree: ast.AST, call: ast.Call) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and any(call is inner for inner in ast.walk(node)):
            return node.name
    return None


def test_interrupt_is_called_once_and_never_inside_a_try_block() -> None:
    sites = {}
    for path in AGENTS.rglob("*.py"):
        found = calls(parse(path), "interrupt")
        if found:
            sites[path.name] = found
    assert list(sites) == ["graph.py"] and len(sites["graph.py"]) == 1
    tree = parse(AGENTS / "graph.py")
    (call,) = calls(tree, "interrupt")
    assert function_of(tree, call) == "approval_gate"
    assert not inside_try(tree, call), "interrupt() must not be wrapped in try/except"


def test_the_write_is_reachable_only_from_the_gate_and_only_after_the_interrupt() -> None:
    callers = {}
    for path in AGENTS.rglob("*.py"):
        tree = parse(path)
        for name in ("assign", "assign_many"):
            for call in calls(tree, name):
                callers.setdefault(name, []).append((path.name, function_of(tree, call)))
    assert callers["assign"] == [("graph.py", "approval_gate")]
    assert callers["assign_many"] == [("registry.py", "assign")]
    tree = parse(AGENTS / "graph.py")
    (interrupt,) = calls(tree, "interrupt")
    (write,) = calls(tree, "assign")
    assert interrupt.lineno < write.lineno, "assign runs only after the interrupt returns"
