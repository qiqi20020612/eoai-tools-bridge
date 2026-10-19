"""The shared query validator survives removal of the dedicated search module."""

import probatio as vol
import pytest

from custom_components.eoai_tools_bridge.validation import validate_query


@pytest.mark.parametrize(
    "value", [None, 123, False, {}, [], "", " \t\n", "字" * 501, "\ud800"]
)
def test_invalid_query(value):
    with pytest.raises(vol.Invalid):
        validate_query(value)


@pytest.mark.parametrize(
    "query", ["123", "true", "{}", "{{ states('light.secret') }}", "字" * 500]
)
def test_query_is_trimmed_without_coercion_or_template_evaluation(query):
    assert validate_query(f"  {query} \n") == query
