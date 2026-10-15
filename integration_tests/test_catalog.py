"""Verify every published blueprint's metadata with the real HA blueprint schema."""
from pathlib import Path

import pytest
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.util.yaml import load_yaml

ROOT=Path(__file__).resolve().parents[1]
PATHS=sorted((ROOT/'blueprints/automation').rglob('*.yaml'))


@pytest.mark.parametrize('path',PATHS,ids=[p.stem for p in PATHS])
def test_published_blueprint_schema_and_source_url(path):
    blueprint=Blueprint(load_yaml(str(path)),expected_domain='automation',schema=BLUEPRINT_SCHEMA)
    assert blueprint.validate() is None
    assert blueprint.metadata['source_url']=='https://github.com/3115a083/ha-blueprints/blob/main/'+path.relative_to(ROOT).as_posix()
