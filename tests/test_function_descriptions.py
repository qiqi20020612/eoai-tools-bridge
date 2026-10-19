"""Keep the description-only patch compatible and its unit list source-backed."""

import hashlib
import json
import re

import pytest
import yaml
from test_function_examples import ROOT

# Parsed static YAML from v0.7.1, commit b411d5520a48189a99c39b592e7e282715c0f76e,
# with description fields removed recursively. Includes every schema keyword,
# model name, fixed identity and the complete original Jinja/script strings.
# CI needs neither git history nor another upstream/repository dependency.
V071_CONTRACT_SHA256 = {
    "calculate": "86457a0c7030dbe8582ba74d12ef31907bc40eaf65e0d8f5305cd2eb7ef67ba1",
    "calendar_day_info": (
        "50a28cbdb710efb59add2324a75ae763eef5511b06561cce77e317ef744c7b80"
    ),
    "find_places_amap": (
        "730c391bac03c5728d3397244e03ea01b44f38a380187f8e3e843f4ae84aeb4a"
    ),
    "find_places_google": (
        "dff5c98b0b859f99d82bdfe766590d918c9813ef33d56d2886967fd153499c03"
    ),
    "geocode": "03fbb15d42fabfe8c5b73ed3385cfed100c86207cf1d7d5860d81ce55484d599",
    "get_route": "3605e0dc569ff888500b20db2b0967963ddaceeaf8ce51ca0e4819e9839783a9",
    "get_weather_forecast": (
        "4f12c4305c00ac5bbb827bd51dd31529d747077100fa052b550360fd64cae790"
    ),
    "play_video": "4d410027eeaffd3c56e917fd9fead70b5f09d1661a599815e2b8f47d7d390f59",
    "search_web": "248691c8bf270c2803f338e8d33c81507f3a492c4b2e0bab50ec4b983aae97d2",
    "search_web_brave_llm_context": (
        "69325c7790b3cc0f9a078c06be174184795052d3102c4654cb54d0016d74f3d2"
    ),
    "search_web_tavily": (
        "0d42b1ab6e6d0cf6ee2c0aacaaf3c01cadb146f9c50518c75e4c61c2d3f511d7"
    ),
    "search_wikipedia": (
        "02c5368b3827593dd599bc6d87b68100db383453f1779b9369b9316956dc36ff"
    ),
    "search_youtube": (
        "7f85f0ef8a266739683a98e72181817c8a6c544d12a297c1a28ffacbf19418a2"
    ),
    "unit_convert": "323f752acb9a455498ce0646e600ca55134d144e239ca49cd571f16626859b42",
}


def without_descriptions(value):
    if isinstance(value, dict):
        return {
            key: without_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }
    if isinstance(value, list):
        return [without_descriptions(item) for item in value]
    return value


@pytest.mark.parametrize("file", V071_CONTRACT_SHA256)
def test_description_patch_preserves_v071_schema_and_script(file):
    example = yaml.safe_load((ROOT / "examples" / f"eoaic2_{file}.yaml").read_text())
    serialized = json.dumps(
        without_descriptions(example), sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(serialized.encode()).hexdigest() == V071_CONTRACT_SHA256[file]


@pytest.mark.parametrize("file", [*V071_CONTRACT_SHA256, "get_route_amap"])
def test_all_model_descriptions_are_present_and_bounded(file):
    spec = yaml.safe_load((ROOT / "examples" / f"eoaic2_{file}.yaml").read_text())[0][
        "spec"
    ]
    # Keep tool guidance concise; detailed numeric grammar belongs to data.
    assert isinstance(spec["description"], str)
    assert 1 <= len(spec["description"].split()) <= 140
    for parameter in spec["parameters"]["properties"].values():
        assert isinstance(parameter.get("description"), str)
        assert 1 <= len(parameter["description"].split()) <= 130


@pytest.mark.tools_upstream
def test_documented_english_unit_groups_match_original_converter(release_source):
    native = release_source("unit_converter")
    spec = yaml.safe_load((ROOT / "examples/eoaic2_unit_convert.yaml").read_text())[0][
        "spec"
    ]
    description = spec["parameters"]["properties"]["from_unit"]["description"]
    for label, units in (
        ("Volume", native.VOLUME_UNITS),
        ("Weight", native.WEIGHT_UNITS),
        ("Temperature", native.TEMPERATURE_UNITS),
    ):
        group = re.search(rf"{label}: ([a-z_, ]+)\.", description)
        assert group is not None
        assert {unit.strip() for unit in group[1].split(",")} == set(units)
