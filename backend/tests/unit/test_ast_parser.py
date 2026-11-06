
from app.modules.architecture_recovery.ast_parser import (
    PythonASTParser,
    DependencyGraphBuilder,
)


def create_project(tmp_path):
    """Create a small Python project with internal imports."""

    app_dir = tmp_path / "backend" / "app"

    (app_dir / "api" / "routes").mkdir(parents=True)
    (app_dir / "services").mkdir(parents=True)

    (app_dir / "__init__.py").write_text("")
    (app_dir / "api" / "__init__.py").write_text("")
    (app_dir / "api" / "routes" / "__init__.py").write_text("")
    (app_dir / "services" / "__init__.py").write_text("")

    (app_dir / "services" / "user_service.py").write_text(
        "class UserService:\n    pass\n"
    )

    (app_dir / "api" / "routes" / "users.py").write_text(
        "from app.services.user_service import UserService\n"
    )

    return tmp_path


def test_module_names_use_app_root(tmp_path):
    project = create_project(tmp_path)

    parser = PythonASTParser()
    parsed = parser.parse_directory(str(project))

    builder = DependencyGraphBuilder()
    graph = builder.build_from_python(parsed, str(project))

    component_ids = {
        component["id"] for component in graph["components"]
    }

    assert "app.api.routes.users" in component_ids
    assert "app.services.user_service" in component_ids
    assert "backend.app.api.routes.users" not in component_ids


def test_internal_import_creates_dependency(tmp_path):
    project = create_project(tmp_path)

    parser = PythonASTParser()
    parsed = parser.parse_directory(str(project))

    builder = DependencyGraphBuilder()
    graph = builder.build_from_python(parsed, str(project))

    relationships = graph["relationships"]

    assert any(
        edge["source"] == "app.api.routes.users"
        and edge["target"] == "app.services.user_service"
        and edge["type"] == "depends_on"
        for edge in relationships
    )


def test_relationship_count_matches_metadata(tmp_path):
    project = create_project(tmp_path)

    parser = PythonASTParser()
    parsed = parser.parse_directory(str(project))

    builder = DependencyGraphBuilder()
    graph = builder.build_from_python(parsed, str(project))

    assert len(graph["relationships"]) > 0
    assert (
        graph["metadata"]["relationship_count"]
        == len(graph["relationships"])
    )
