"""Metadata views preserve validation constraints without running defaults."""

from unittest.mock import Mock

import probatio as vol
import pytest
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.catalog import serialize_parameters
from custom_components.eoai_tools_bridge.const import (
    API_ID,
    AUDITED_READ_ONLY_TOOLS,
    CATALOG_ALLOWLIST,
)
from custom_components.eoai_tools_bridge.policy import read_only_basis
from custom_components.eoai_tools_bridge.schema import parameters_without_defaults


def serialize(parameters, custom=None):
    tool = Mock(parameters=parameters)
    instance = Mock(custom_serializer=custom)
    return serialize_parameters(instance, tool)


@pytest.mark.parametrize("wrapper", [vol.Schema, vol.All, vol.Any])
def test_optional_defaults_in_nested_containers(wrapper):
    factory = Mock(return_value="private-default")
    native = vol.Schema(
        {
            vol.Required("nested"): [
                wrapper({vol.Optional("value", default=factory): str})
            ],
        }
    )
    result = serialize(native)
    assert result["required"] == ["nested"]
    assert result["properties"]["nested"]["type"] == "array"
    assert "default" not in str(result)
    factory.assert_not_called()
    assert native({"nested": [{}]}) == {"nested": [{"value": "private-default"}]}
    factory.assert_called_once()


def test_native_required_extra_enum_and_ranges_remain_intact():
    factory = Mock(return_value=1)
    native = vol.Schema(
        {
            "mode": vol.In(["walk", "drive"]),
            vol.Optional("count", default=factory): vol.All(
                int, vol.Range(min=1, max=25)
            ),
            vol.Required("nested"): vol.Schema({"value": str}, required=True),
        },
        required=True,
        extra=vol.ALLOW_EXTRA,
    )
    result = serialize(native)
    assert result["required"] == ["mode", "nested"]
    assert result["additionalProperties"] is True
    assert result["properties"]["mode"]["enum"] == ["walk", "drive"]
    assert result["properties"]["count"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 25,
    }
    nested = result["properties"]["nested"]
    assert nested["required"] == ["value"]
    assert nested["additionalProperties"] is False
    factory.assert_not_called()


@pytest.mark.parametrize(
    "marker",
    [
        lambda factory: vol.Required("value", default=factory),
        lambda factory: vol.Exclusive("value", "group", required=True, default=factory),
        lambda factory: vol.Inclusive("value", "group", default=factory),
    ],
)
def test_presence_and_group_defaults_are_rejected_without_evaluation(marker):
    factory = Mock(return_value=vol.UNDEFINED)
    native = vol.Schema({marker(factory): str})
    with pytest.raises(ValueError, match="presence default"):
        serialize(native)
    factory.assert_not_called()


def test_group_constraints_without_defaults_survive():
    native = vol.Schema(
        {
            vol.Inclusive("a", "together"): str,
            vol.Inclusive("b", "together"): str,
            vol.Exclusive("x", "one", required=True): str,
            vol.Exclusive("y", "one", required=True): str,
        }
    )
    # Compare the public codec's full constraint tree, not a widened substitute.
    assert serialize(native) == vol.to_openapi(
        native, openapi_version="3.1.0", strict=True
    )


def test_metadata_view_does_not_recompile_custom_validators():
    class Validator:
        def __voluptuous_compile__(self, schema):
            compilation()
            return lambda path, value: value

    compilation = Mock()
    validator = Validator()
    factory = Mock(return_value="private-default")
    native = vol.Schema({vol.Optional("value", default=factory): validator})
    compilation.reset_mock()
    result = serialize(
        native,
        lambda node: {"type": "string"} if node is validator else vol.UNSUPPORTED,
    )
    assert result["properties"]["value"] == {"type": "string"}
    compilation.assert_not_called()
    factory.assert_not_called()


@pytest.mark.parametrize("kind", ["cycle", "nodes", "depth"])
def test_input_definition_budget_precedes_codec(kind):
    node = {}
    if kind == "cycle":
        node["value"] = node
    elif kind == "nodes":
        node = {f"value{i}": str for i in range(300)}
    else:
        for _ in range(30):
            node = {"value": node}
    with pytest.raises(ValueError, match="Oversized"):
        parameters_without_defaults(node)


def test_unknown_marker_subclasses_fail_closed():
    class Marker(vol.Optional):
        pass

    factory = Mock(return_value="private-default")
    with pytest.raises(ValueError, match="marker"):
        parameters_without_defaults({Marker("value", default=factory): str})
    factory.assert_not_called()


@pytest.mark.parametrize("pair", sorted(AUDITED_READ_ONLY_TOOLS - CATALOG_ALLOWLIST))
def test_audited_classification_requires_tools_for_assist_integration(pair):
    api_id, name = pair
    tool = Mock(name=name)
    tool.name = name
    tool.annotations = llm.Tool.annotations
    tool.integration = "unrelated_integration"
    assert read_only_basis(api_id, tool) is None
    tool.integration = API_ID
    assert read_only_basis(api_id, tool) == "audited_allowlist"
    tool.annotations = llm.ToolAnnotations(read_only=False, destructive=False)
    assert read_only_basis(api_id, tool) is None
    tool.annotations = llm.ToolAnnotations(read_only=True, destructive=True)
    assert read_only_basis(api_id, tool) is None


@pytest.mark.parametrize(
    "pair",
    [
        ("basic_utilities", "calculate"),
        ("media_services", "play_video"),
        ("HomeControl", "intent__HassTurnOn"),
        ("HomeControl", "script__example"),
    ],
)
def test_unaudited_tools_keep_separate_side_effect_permission(pair):
    api_id, name = pair
    tool = Mock()
    tool.name = name
    tool.integration = API_ID
    tool.annotations = llm.Tool.annotations
    assert read_only_basis(api_id, tool) is None
