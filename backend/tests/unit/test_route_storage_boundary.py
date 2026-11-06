
import ast
from pathlib import Path


def test_api_routes_do_not_import_database_report_store():
    routes_dir = Path(__file__).resolve().parents[2] / "app" / "api" / "routes"

    offenders = []
    for path in routes_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "app.database.report_store":
                    offenders.append(path.name)

    assert offenders == []
