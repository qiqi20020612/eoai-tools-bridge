"""Run the original calculator only after bounded numeric argument validation."""

from unittest.mock import Mock, patch

import pytest

from custom_components.eoai_tools_bridge.const import DOMAIN

pytestmark = pytest.mark.tools_upstream


@pytest.fixture
def calculator_entry(hass, gateway_entry):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            "enabled": True,
            "allowed_tools": "basic_utilities/calculate",
            "allow_side_effects": False,
        },
    )
    return gateway_entry


async def calculate(hass, context, operation="expression", data=None):
    return await hass.services.async_call(
        DOMAIN,
        "call_tool",
        {
            "api_id": "basic_utilities",
            "tool_name": "calculate",
            "tool_args": {
                "operation": operation,
                "data": data if data is not None else ["1+2"],
            },
        },
        context=context,
        blocking=True,
        return_response=True,
    )


@pytest.mark.parametrize(
    "operation,data,expected",
    [
        ("expression", ["1+2*3"], "7"),
        ("expression", ["2^3"], "8"),
        ("expression", ["(12-4)/2"], "4"),
        ("expression", ["sqrt(9)+Abs(-2)"], "5"),
        ("expression", ["sin(pi/2)+cos(0)"], "2"),
        ("expression", ["log(E)"], "1"),
        ("expression", ["Min(4,2,3)"], "2"),
        ("expression", ["5//2+5%2"], "3"),
        ("expression", ["3.5+2.25"], "5.75"),
        ("min", ["3", "-2", "0"], -2.0),
        ("max", ["3", "-2", "0"], 3.0),
        ("avg", ["1", "2", "3"], 2.0),
    ],
)
async def test_original_calculator_results_without_side_effect_permission(
    hass, calculator_entry, calculator_api, admin_context, operation, data, expected
):
    response = await calculate(hass, admin_context, operation, data)
    assert response["success"] is True, response
    assert response["result"] == {"value": expected}
    assert response["outcome_unknown"] is False
    assert response["truncated"] is False


@pytest.mark.parametrize(
    "operation,data",
    [
        ("expression", []),
        ("min", []),
        ("expression", ["__import__('os').getcwd()"]),
        ("expression", ["open('/tmp/forbidden')"]),
        ("expression", ["(1).__class__"]),
        ("expression", ["[1,2][0]"]),
        ("expression", ["'untrusted'"]),
        ("expression", ["(lambda: 1)()"]),
        ("expression", ["sqrt(9, evaluate=False)"]),
        ("expression", ["factorial(1000000000)"]),
        ("expression", ["10**1000000000"]),
        ("expression", ["10**(10**10)"]),
        ("expression", ["(1e-100)**32"]),
        ("expression", ["1e101"]),
        ("expression", ["1/0"]),
        ("expression", ["sqrt(-1)"]),
        ("expression", ["sin()"]),
        ("expression", ["True"]),
        ("expression", ["+" * 12 + "1"]),
        ("expression", ["1+" * 40 + "1"]),
        ("expression", ["1" * 257]),
        ("expression", ["1", "2"]),
        ("min", ["nan"]),
        ("max", ["inf"]),
        ("avg", ["1e101"]),
        ("avg", ["1"] * 33),
    ],
)
async def test_unsafe_or_unbounded_input_never_reaches_sympy(
    hass,
    calculator_entry,
    calculator_api,
    admin_context,
    release_source,
    operation,
    data,
):
    native = release_source("calculator")
    with patch.object(
        native, "_calculate", side_effect=AssertionError("must not execute")
    ) as invoke:
        response = await calculate(hass, admin_context, operation, data)
    assert response["error_code"] == "invalid_args"
    assert response["outcome_unknown"] is False
    invoke.assert_not_called()


async def test_calculator_public_schema_and_extra_limits(
    hass, calculator_entry, calculator_api, admin_context, release_source
):
    with patch.object(release_source("calculator"), "_calculate", new=Mock()) as invoke:
        for action, data in [
            ("list_tools", {}),
            (
                "describe_tool",
                {
                    "api_id": "basic_utilities",
                    "tool_name": "calculate",
                },
            ),
        ]:
            response = await hass.services.async_call(
                DOMAIN,
                action,
                data,
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            assert response["success"] is True
            metadata = (
                response["tool"] if action == "describe_tool" else response["tools"][0]
            )
            assert metadata["read_only_basis"] == "audited_allowlist"
            schema = metadata["parameters"]
            assert schema["properties"]["operation"]["enum"] == [
                "expression",
                "min",
                "max",
                "avg",
            ]
            assert schema["properties"]["data"]["items"] == {"type": "string"}
            assert metadata["bridge_constraints"]["expression_data_items"] == 1
            assert "sqrt" in metadata["bridge_constraints"]["functions"]
        invoke.assert_not_called()


async def test_original_calculator_context_and_no_duplicate_execution(
    hass, calculator_entry, calculator_api, admin_context, release_source
):
    native = release_source("calculator")
    original = native.CalculatorTool.async_call
    contexts = []

    async def record(tool, hass, tool_input, llm_context):
        contexts.append(llm_context)
        return await original(tool, hass, tool_input, llm_context)

    with (
        patch.object(native.CalculatorTool, "async_call", record),
        patch.object(native, "_calculate", wraps=native._calculate) as invoke,
    ):
        response = await calculate(hass, admin_context)
    assert response["result"] == {"value": "3"}
    assert contexts[0].context is admin_context
    invoke.assert_called_once_with("expression", ["1+2"])


async def test_no_user_cannot_reach_native_calculator(
    hass, calculator_entry, calculator_api, release_source
):
    with patch.object(release_source("calculator"), "_calculate", new=Mock()) as invoke:
        assert (await calculate(hass, None))["error_code"] == "permission_denied"
        invoke.assert_not_called()
