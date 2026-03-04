from __future__ import annotations

from typing import Any


def test_tool_spec_has_required_top_keys(tool_modules_with_spec: list[Any]) -> None:
    for mod in tool_modules_with_spec:
        spec: dict[str, Any] = mod.TOOL_SPEC
        assert isinstance(spec, dict)
        assert spec.get("type")
        assert isinstance(spec.get("function"), dict)
        assert spec["function"].get("name")
        assert spec["function"].get("description")
        assert isinstance(spec["function"].get("parameters"), dict)


def test_tool_spec_parameters_is_json_schema_object(
    tool_modules_with_spec: list[Any],
) -> None:
    for mod in tool_modules_with_spec:
        spec: dict[str, Any] = mod.TOOL_SPEC
        params = spec["function"]["parameters"]
        assert isinstance(params, dict)
        assert params.get("type") == "object"
        assert isinstance(params.get("properties"), dict)

        required = params.get("required", [])
        assert isinstance(required, list)
        for r in required:
            assert isinstance(r, str)
            assert (
                r in params["properties"]
            ), f"{mod.__name__}: required '{r}' not in properties"


def test_tool_spec_defaults_match_declared_types(
    tool_modules_with_spec: list[Any],
) -> None:
    for mod in tool_modules_with_spec:
        spec: dict[str, Any] = mod.TOOL_SPEC
        props: dict[str, Any] = spec["function"]["parameters"].get("properties", {})

        for name, sch in props.items():
            if not isinstance(sch, dict):
                continue
            if "default" not in sch:
                continue

            default = sch["default"]
            t = sch.get("type")

            if t == "boolean":
                assert isinstance(
                    default, bool
                ), f"{mod.__name__}.{name}: default must be bool"
            elif t == "integer":
                assert isinstance(default, int) and not isinstance(
                    default, bool
                ), f"{mod.__name__}.{name}: default must be int"
            elif t == "number":
                assert isinstance(default, (int, float)) and not isinstance(
                    default, bool
                ), f"{mod.__name__}.{name}: default must be number"
            elif t == "string":
                assert isinstance(
                    default, str
                ), f"{mod.__name__}.{name}: default must be str"
            elif isinstance(t, list):
                # allow None if 'null' present
                if default is None:
                    assert (
                        "null" in t
                    ), f"{mod.__name__}.{name}: default None but null not allowed"


def test_tool_spec_enum_defaults_are_in_enum(tool_modules_with_spec: list[Any]) -> None:
    for mod in tool_modules_with_spec:
        spec: dict[str, Any] = mod.TOOL_SPEC
        props: dict[str, Any] = spec["function"]["parameters"].get("properties", {})

        for name, sch in props.items():
            if not isinstance(sch, dict):
                continue
            enum = sch.get("enum")
            if not isinstance(enum, list) or not enum:
                continue
            if "default" in sch:
                assert (
                    sch["default"] in enum
                ), f"{mod.__name__}.{name}: default not in enum"
