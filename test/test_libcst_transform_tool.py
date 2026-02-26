"""Tests for libcst_transform_tool."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

# Import the tool
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uagent.tools.libcst_transform_tool import (
    TOOL_SPEC,
    RenameImportTransformer,
    RenameSymbolTransformer,
    ReplaceCallTransformer,
    _build_transformers,
    _extract_error_location,
    _json_err,
    _json_ok,
    _matches_any_glob,
    run_tool,
)


class TestJsonHelpers:
    """Tests for JSON helper functions."""

    def test_json_ok_basic(self):
        """Test _json_ok returns valid JSON with ok=True."""
        result = _json_ok({"data": "test"})
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert parsed["data"] == "test"

    def test_json_ok_preserves_existing_ok(self):
        """Test _json_ok preserves existing ok value."""
        result = _json_ok({"ok": False, "data": "test"})
        parsed = json.loads(result)
        assert parsed["ok"] is False  # Preserved, not overwritten

    def test_json_err_basic(self):
        """Test _json_err returns error JSON."""
        result = _json_err("Something went wrong")
        parsed = json.loads(result)
        assert parsed["ok"] is False
        assert parsed["error"] == "Something went wrong"

    def test_json_err_with_details(self):
        """Test _json_err with details parameter."""
        result = _json_err("Error", details={"file": "test.py"})
        parsed = json.loads(result)
        assert parsed["ok"] is False
        assert parsed["error"] == "Error"
        assert parsed["details"]["file"] == "test.py"

    def test_json_err_with_location(self):
        """Test _json_err with file, line, column parameters."""
        result = _json_err("Syntax error", file="test.py", line=10, column=5)
        parsed = json.loads(result)
        assert parsed["ok"] is False
        assert parsed["error"] == "Syntax error"
        assert parsed["file"] == "test.py"
        assert parsed["line"] == 10
        assert parsed["column"] == 5


class TestExtractErrorLocation:
    """Tests for _extract_error_location function."""

    def test_extract_from_libcst_error(self):
        """Test extracting location from libcst ParserSyntaxError."""
        import libcst as cst

        code = "def foo():\n    x = \n"
        try:
            cst.parse_module(code)
        except Exception as e:
            line, column = _extract_error_location(e)
            # libcst should provide editor_line and editor_column
            assert line is not None or column is not None

    def test_extract_from_generic_error(self):
        """Test that generic exceptions return None for location."""
        exc = ValueError("Generic error")
        line, column = _extract_error_location(exc)
        assert line is None
        assert column is None


class TestMatchesAnyGlob:
    """Tests for _matches_any_glob function."""

    def test_match_simple_glob(self):
        """Test matching simple glob pattern."""
        assert _matches_any_glob("test.py", ["*.py"]) is True
        assert _matches_any_glob("test.txt", ["*.py"]) is False

    def test_match_multiple_globs(self):
        """Test matching against multiple glob patterns."""
        globs = ["*.py", "*.txt", "*.md"]
        assert _matches_any_glob("test.py", globs) is True
        assert _matches_any_glob("test.txt", globs) is True
        assert _matches_any_glob("test.md", globs) is True
        assert _matches_any_glob("test.json", globs) is False

    def test_match_directory_glob(self):
        """Test matching directory glob patterns."""
        assert _matches_any_glob(".git/config", [".git/**"]) is True
        assert _matches_any_glob("src/main.py", [".git/**"]) is False


class TestBuildTransformers:
    """Tests for _build_transformers function."""

    def test_build_rename_symbol(self):
        """Test building rename_symbol transformer."""
        ops = [{"op": "rename_symbol", "old": "foo", "new": "bar"}]
        transformers, errors = _build_transformers(ops)
        assert len(transformers) == 1
        assert isinstance(transformers[0].transformer, RenameSymbolTransformer)
        assert len(errors) == 0

    def test_build_replace_call(self):
        """Test building replace_call transformer."""
        ops = [{"op": "replace_call", "old": "old_func", "new": "new_func"}]
        transformers, errors = _build_transformers(ops)
        assert len(transformers) == 1
        assert isinstance(transformers[0].transformer, ReplaceCallTransformer)
        assert len(errors) == 0

    def test_build_rename_import(self):
        """Test building rename_import transformer."""
        ops = [{"op": "rename_import", "old": "OldClass", "new": "NewClass"}]
        transformers, errors = _build_transformers(ops)
        assert len(transformers) == 1
        assert isinstance(transformers[0].transformer, RenameImportTransformer)
        assert len(errors) == 0

    def test_build_missing_required_params(self):
        """Test that missing required parameters cause errors."""
        ops = [{"op": "rename_symbol", "old": "foo"}]  # missing "new"
        transformers, errors = _build_transformers(ops)
        assert len(transformers) == 0
        assert len(errors) == 1
        assert "rename_symbol requires old/new" in errors[0]

    def test_build_unknown_op(self):
        """Test that unknown operations cause errors."""
        ops = [{"op": "unknown_op", "param": "value"}]
        transformers, errors = _build_transformers(ops)
        assert len(transformers) == 0
        assert len(errors) == 1
        assert "unknown op" in errors[0]

    def test_build_invalid_op_type(self):
        """Test that non-dict operations cause errors."""
        ops = ["not a dict"]
        transformers, errors = _build_transformers(ops)
        assert len(transformers) == 0
        assert len(errors) == 1
        assert "invalid operation" in errors[0]


class TestRenameSymbolTransformer:
    """Tests for RenameSymbolTransformer."""

    def test_rename_simple_name(self):
        """Test renaming a simple name."""
        import libcst as cst

        code = "foo = 1\nbar = foo + 1"
        module = cst.parse_module(code)
        transformer = RenameSymbolTransformer("foo", "baz")
        new_module = module.visit(transformer)
        assert "baz = 1" in new_module.code
        assert "bar = baz + 1" in new_module.code

    def test_rename_standalone_only(self):
        """Test that only standalone names are renamed (not attributes)."""
        import libcst as cst

        code = "foo = 1\nobj.foo = 2"
        module = cst.parse_module(code)
        transformer = RenameSymbolTransformer("foo", "baz", include_attributes=False)
        new_module = module.visit(transformer)

        # 'foo = 1' should become 'baz = 1' (standalone name)
        assert "baz = 1" in new_module.code

    def test_rename_with_attributes_true(self):
        """Test that attribute access is renamed when include_attributes=True."""
        import libcst as cst

        code = "obj.foo = 1\nbar = obj.foo"
        module = cst.parse_module(code)
        transformer = RenameSymbolTransformer("foo", "baz", include_attributes=True)
        new_module = module.visit(transformer)
        assert "obj.baz" in new_module.code


class TestReplaceCallTransformer:
    """Tests for ReplaceCallTransformer."""

    def test_replace_simple_call(self):
        """Test replacing a simple function call."""
        import libcst as cst

        code = "result = old_func(a, b)"
        module = cst.parse_module(code)
        transformer = ReplaceCallTransformer("old_func", "new_func")
        new_module = module.visit(transformer)
        assert "new_func(a, b)" in new_module.code

    def test_replace_method_call(self):
        """Test replacing a method call."""
        import libcst as cst

        code = "result = obj.old_method(a, b)"
        module = cst.parse_module(code)
        transformer = ReplaceCallTransformer("old_method", "new_method")
        new_module = module.visit(transformer)
        assert "obj.new_method(a, b)" in new_module.code

    def test_replace_with_receiver_filter(self):
        """Test replacing only calls with specific receiver."""
        import libcst as cst

        code = "result = obj1.old_func(a)\nresult2 = obj2.old_func(b)"
        module = cst.parse_module(code)
        transformer = ReplaceCallTransformer("old_func", "new_func", receiver="obj1")
        new_module = module.visit(transformer)
        assert "obj1.new_func(a)" in new_module.code
        assert "obj2.old_func(b)" in new_module.code  # Not changed


class TestRenameImportTransformer:
    """Tests for RenameImportTransformer."""

    def test_rename_import_without_module(self):
        """Test renaming an import without module filter."""
        import libcst as cst

        code = "from module import OldClass"
        module = cst.parse_module(code)
        transformer = RenameImportTransformer(None, "OldClass", "NewClass")
        new_module = module.visit(transformer)
        assert "import NewClass" in new_module.code

    def test_rename_import_with_module(self):
        """Test renaming an import with module filter."""
        import libcst as cst

        code = "from target_module import OldClass\nfrom other_module import OldClass"
        module = cst.parse_module(code)
        transformer = RenameImportTransformer("target_module", "OldClass", "NewClass")
        new_module = module.visit(transformer)
        lines = new_module.code.strip().split("\n")
        assert "import NewClass" in lines[0]
        assert "import OldClass" in lines[1]


class TestRunToolAnalyze:
    """Tests for run_tool in analyze mode."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_analyze_single_file(self, temp_dir):
        """Test analyzing a single Python file."""
        test_file = temp_dir / "test.py"
        test_file.write_text(
            """
import os
from typing import List

def foo():
    pass

class Bar:
    def method(self):
        pass
""".lstrip()
        )

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool({"mode": "analyze", "paths": [str(test_file)]})

        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert parsed["mode"] == "analyze"
        assert str(test_file) in parsed["analyze"]["files"]

        file_info = parsed["analyze"]["files"][str(test_file)]
        assert "import os" in file_info["imports"]
        assert "foo" in file_info["functions"]
        assert "Bar" in file_info["classes"]

    def test_analyze_directory(self, temp_dir):
        """Test analyzing a directory."""
        (temp_dir / "file1.py").write_text("def func1(): pass")
        (temp_dir / "file2.py").write_text("def func2(): pass")

        def mock_ensure_within_workdir(path):
            return str(path)

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            side_effect=mock_ensure_within_workdir,
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool(
                    {"mode": "analyze", "paths": [str(temp_dir)], "include_glob": "*.py"}
                )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert parsed["files_total"] == 2

    def test_analyze_syntax_error(self, temp_dir):
        """Test analyzing a file with syntax errors."""
        test_file = temp_dir / "broken.py"
        test_file.write_text("def foo(\n")

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool({"mode": "analyze", "paths": [str(test_file)]})
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert str(test_file) in parsed["analyze"]["errors"]

        error_info = parsed["analyze"]["errors"][str(test_file)]
        assert "message" in error_info
        assert "line" in error_info

    def test_analyze_exclude_patterns(self, temp_dir):
        """Test that exclude patterns work."""
        (temp_dir / "include.py").write_text("def func(): pass")
        (temp_dir / "exclude.py").write_text("def excluded(): pass")

        def mock_ensure_within_workdir(path):
            return str(path)

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            side_effect=mock_ensure_within_workdir,
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool(
                    {
                        "mode": "analyze",
                        "paths": [str(temp_dir)],
                        "include_glob": "*.py",
                        "exclude_globs": ["exclude.py"],
                    }
                )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert parsed["files_total"] == 1


class TestRunToolTransform:
    """Tests for run_tool in transform mode."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_transform_rename_symbol(self, temp_dir):
        """Test renaming a symbol."""
        test_file = temp_dir / "test.py"
        test_file.write_text("foo = 1\nbar = foo + 1")

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                with patch(
                    "uagent.tools.libcst_transform_tool.make_backup_before_overwrite",
                    return_value=str(test_file) + ".org",
                ):
                    result = run_tool(
                        {
                            "mode": "transform",
                            "paths": [str(test_file)],
                            "operations": [
                                {"op": "rename_symbol", "old": "foo", "new": "baz"}
                            ],
                        }
                    )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert str(test_file) in parsed["transform"]["changed_files"]

        content = test_file.read_text()
        assert "baz = 1" in content
        assert "bar = baz + 1" in content

    def test_transform_preview_mode(self, temp_dir):
        """Test preview mode doesn't modify files."""
        test_file = temp_dir / "test.py"
        original_content = "foo = 1"
        test_file.write_text(original_content)

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool(
                    {
                        "mode": "transform",
                        "paths": [str(test_file)],
                        "operations": [
                            {"op": "rename_symbol", "old": "foo", "new": "bar"}
                        ],
                        "preview": True,
                    }
                )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert parsed["transform"]["preview"] is True
        assert str(test_file) in parsed["transform"]["changed_files"]

        assert test_file.read_text() == original_content

        assert "previews" in parsed["transform"]
        preview = parsed["transform"]["previews"][str(test_file)]
        assert "diff" in preview
        assert "bar = 1" in preview["diff"]

    def test_transform_creates_backup(self, temp_dir):
        """Test that transform creates backup files."""
        test_file = temp_dir / "test.py"
        test_file.write_text("foo = 1")
        backup_path = str(test_file) + ".org"

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                with patch(
                    "uagent.tools.libcst_transform_tool.make_backup_before_overwrite",
                    return_value=backup_path,
                ) as mock_backup:
                    result = run_tool(
                        {
                            "mode": "transform",
                            "paths": [str(test_file)],
                            "operations": [
                                {"op": "rename_symbol", "old": "foo", "new": "bar"}
                            ],
                        }
                    )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert "backups" in parsed["transform"]
        mock_backup.assert_called_once()

    def test_transform_unchanged_file(self, temp_dir):
        """Test that unchanged files are not modified."""
        test_file = temp_dir / "test.py"
        test_file.write_text("x = 1")

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool(
                    {
                        "mode": "transform",
                        "paths": [str(test_file)],
                        "operations": [
                            {"op": "rename_symbol", "old": "foo", "new": "bar"}
                        ],
                    }
                )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert str(test_file) in parsed["transform"]["unchanged_files"]
        assert str(test_file) not in parsed["transform"]["changed_files"]

    def test_transform_invalid_operations(self, temp_dir):
        """Test handling of invalid operations."""
        test_file = temp_dir / "test.py"
        test_file.write_text("x = 1")

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            return_value=str(test_file),
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool(
                    {
                        "mode": "transform",
                        "paths": [str(test_file)],
                        "operations": [{"op": "rename_symbol"}],
                    }
                )
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert len(parsed["transform"]["op_errors"]) > 0


class TestToolSpec:
    """Tests for TOOL_SPEC structure."""

    def test_tool_spec_has_required_keys(self):
        """Test that TOOL_SPEC has all required keys."""
        assert "type" in TOOL_SPEC
        assert "function" in TOOL_SPEC
        assert "name" in TOOL_SPEC["function"]
        assert "description" in TOOL_SPEC["function"]
        assert "parameters" in TOOL_SPEC["function"]

    def test_tool_spec_parameters(self):
        """Test that TOOL_SPEC has all expected parameters."""
        props = TOOL_SPEC["function"]["parameters"]["properties"]

        assert "mode" in props
        assert "paths" in props
        assert "include_glob" in props
        assert "exclude_globs" in props
        assert "max_files" in props
        assert "max_bytes" in props
        assert "operations" in props
        assert "preview" in props

    def test_tool_spec_required_params(self):
        """Test that required parameters are specified."""
        required = TOOL_SPEC["function"]["parameters"]["required"]
        assert "mode" in required
        assert "paths" in required

    def test_tool_spec_preview_default(self):
        """Test that preview parameter has correct default."""
        props = TOOL_SPEC["function"]["parameters"]["properties"]
        assert props["preview"]["default"] is False


class TestSafety:
    """Tests for safety features."""

    def test_reject_path_outside_workdir(self):
        """Test that paths outside workdir are rejected."""
        result = run_tool({"mode": "analyze", "paths": ["/etc/passwd"]})
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert len(parsed["walk_errors"]) > 0

    def test_dangerous_path_rejected(self):
        """Test that dangerous paths are rejected."""
        result = run_tool({"mode": "analyze", "paths": ["../../../etc/passwd"]})
        parsed = json.loads(result)

        assert parsed["ok"] is True
        assert len(parsed["walk_errors"]) > 0

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_max_files_limit(self, temp_dir):
        """Test that max_files limit is enforced."""
        for i in range(5):
            (temp_dir / f"file{i}.py").write_text("x = 1")

        def mock_ensure_within_workdir(path):
            return str(path)

        with patch(
            "uagent.tools.libcst_transform_tool.ensure_within_workdir",
            side_effect=mock_ensure_within_workdir,
        ):
            with patch(
                "uagent.tools.libcst_transform_tool.is_path_dangerous", return_value=False
            ):
                result = run_tool(
                    {
                        "mode": "analyze",
                        "paths": [str(temp_dir)],
                        "include_glob": "*.py",
                        "max_files": 2,
                    }
                )
        parsed = json.loads(result)

        assert "max_files exceeded" in str(parsed["walk_errors"]) or parsed[
            "files_total"
        ] <= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
