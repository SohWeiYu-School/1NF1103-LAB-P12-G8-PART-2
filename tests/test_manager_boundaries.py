"""The design rules the marking checks, tested on the source code itself.

1. The four managers (interface, ai, logic, data) never import each other or the
   Application folder. All coordination is in app/application. Any of them may use
   app/model. The one exception is WebApp, which calls App.
2. Only ConsoleUI prints or reads from the terminal.
3. The Logic Manager does no file access and no network calls.
"""

import ast
import os

import pytest

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
MANAGERS = ("interface", "ai", "logic", "data")
ALLOWED_EXCEPTIONS = {("interface/web_app.py", "app.application.app")}


def _python_files(folder: str) -> list[str]:
    found = []
    for root, _, names in os.walk(os.path.join(APP_DIR, folder)):
        found += [os.path.join(root, name) for name in names if name.endswith(".py")]
    return sorted(found)


def _imports(path: str) -> list[str]:
    """Every module a file imports, including imports inside functions."""
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _relative(path: str) -> str:
    return os.path.relpath(path, APP_DIR).replace(os.sep, "/")


@pytest.mark.parametrize("manager", MANAGERS)
def test_a_manager_never_imports_another_manager_or_the_application(manager):
    others = [f"app.{other}" for other in MANAGERS if other != manager] + ["app.application"]
    problems = []
    for path in _python_files(manager):
        for module in _imports(path):
            if (_relative(path), module) in ALLOWED_EXCEPTIONS:
                continue
            if any(module == other or module.startswith(other + ".") for other in others):
                problems.append(f"{_relative(path)} imports {module}")
    assert problems == []


def test_the_domain_model_imports_no_manager():
    problems = [f"{_relative(path)} imports {module}" for path in _python_files("model")
                for module in _imports(path)
                if module.startswith("app.") and not module.startswith("app.model")]
    assert problems == []


def test_no_old_procedural_manager_files_are_left():
    for name in ("data_manager.py", "ai_manager.py", "logic_manager.py", "io_manager.py", "utilities.py",
                 "web_app.py"):
        assert not os.path.exists(os.path.join(APP_DIR, name)), name


def _calls(path: str, names: set[str]) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return [f"{_relative(path)}:{node.lineno} {node.func.id}()" for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names]


def test_only_console_ui_prints_or_reads_the_terminal():
    problems = []
    for folder in ("application",) + MANAGERS + ("model",):
        for path in _python_files(folder):
            if _relative(path) != "interface/console_ui.py":
                problems += _calls(path, {"print", "input"})
    assert problems == []


def test_the_logic_manager_opens_no_files_and_makes_no_network_calls():
    problems = []
    for path in _python_files("logic"):
        problems += _calls(path, {"open"})
        problems += [f"{_relative(path)} imports {module}" for module in _imports(path)
                     if module.split(".")[0] in ("requests", "urllib", "http", "socket", "openai", "google",
                                                 "pymongo", "os")]
    assert problems == []
