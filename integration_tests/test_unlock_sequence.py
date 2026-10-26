"""Live Home Assistant action-schema and safe one-step execution checks.

No physical devices are controlled; all service effects are mocked.
"""
from pathlib import Path
import asyncio

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, HomeAssistant
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.util.yaml import load_yaml

PATH = Path(__file__).resolve().parents[1] / (
    "blueprints/automation/unlock_sequence/unlock_sequence.yaml"
)


def substitute(**inputs):
    blueprint = Blueprint(
        load_yaml(str(PATH)), expected_domain="automation",
        schema=BLUEPRINT_SCHEMA
    )
    assert blueprint.validate() is None
    obj = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "unlock_sequence.yaml",
                "input": {
                    "configuration_mode": "simple",
                    "simple_triggers": [
                        {"trigger": "event", "event_type": "unlock_test_press"}
                    ],
                    "simple_repeats": 1,
                    "success_cooldown_seconds": 0,
                    "success_actions": [
                        {"action": "persistent_notification.create",
                         "data": {"title": "Test", "message": "Validated"}}
                    ],
                    **inputs,
                }
            }
        },
    )
    obj.validate()
    return obj.async_substitute()


@pytest.mark.asyncio
async def test_expanded_unlock_actions_validate_with_real_ha(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    try:
        config = substitute()
        actions = await async_validate_actions_config(
            hass,
            cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]]),
        )
        assert actions
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_one_event_can_execute_safe_action_once(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    seen = []

    async def record(call):
        seen.append(dict(call.data))

    hass.services.async_register("persistent_notification", "create", record)
    try:
        config = substitute()
        actions = await async_validate_actions_config(
            hass,
            cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]]),
        )
        script = Script(
            hass, actions, "Unlock sequence test", "automation",
            script_mode="single",
        )
        await script.async_run(
            {"this": {"entity_id": "automation.test_unlock"},
             "trigger": {"id": "0"}},
            Context(),
        )
        await hass.async_block_till_done()
        assert seen == [{"title": "Test", "message": "Validated"}]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_second_input_advances_only_once(tmp_path):
    """A real event must advance the active wait and execute one safe action."""
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    seen = []

    async def record(call):
        seen.append(dict(call.data))

    hass.services.async_register("persistent_notification", "create", record)
    try:
        config = substitute(simple_repeats=2, debounce_ms=0)
        actions = await async_validate_actions_config(
            hass,
            cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]]),
        )
        script = Script(
            hass, actions, "Unlock two-press sequence", "automation",
            script_mode="single",
        )
        task = asyncio.create_task(
            script.async_run(
                {"this": {"entity_id": "automation.test_unlock"},
                 "trigger": {"id": "0"}},
                Context(),
            )
        )
        await asyncio.sleep(0.05)
        assert seen == [], "A single input must not unlock a two-input code"
        hass.bus.async_fire("unlock_test_press")
        await asyncio.wait_for(task, timeout=3)
        await hass.async_block_till_done()
        assert seen == [{"title": "Test", "message": "Validated"}]
    finally:
        await hass.async_stop()
