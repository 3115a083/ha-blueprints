"""Real Home Assistant action-schema and motion-flow tests with mocked services.

Physical devices are not accessed; independent state/timer guards are also covered
in tests/test_multi_zone_motion_lights.py.
"""
from pathlib import Path

import pytest

from homeassistant import loader
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.util.yaml import load_yaml


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/automation/multi_zone_motion_lights/multi_zone_motion_lights.yaml"


def zone(name, motion, light, **extra):
    return {
        "name": name, "enabled": True,
        "motion_sensors": [motion], "on_entities": [light],
        "off_entities": [light], "off_delay_seconds": 60,
        "cross_room_grace_seconds": 180, "sun_mode": "any",
        "start_time": "00:00:00", "end_time": "23:59:59", **extra,
    }


def expanded(zones):
    source = Blueprint(load_yaml(str(PATH)), expected_domain="automation",
                       schema=BLUEPRINT_SCHEMA)
    assert source.validate() is None
    config = BlueprintInputs(source, {"use_blueprint": {
        "path": "multi_zone_motion_lights.yaml",
        "input": {
            "monitored_motion_sensors": [
                "binary_sensor.hall_motion", "binary_sensor.bath_motion"
            ],
            "lighting_zones": zones,
        },
    }})
    config.validate()
    return config.async_substitute()


async def make_runner(tmp_path, zones, *, bath_state="off", lux="10"):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    hass.states.async_set("binary_sensor.hall_motion", "on")
    hass.states.async_set("binary_sensor.bath_motion", bath_state)
    hass.states.async_set("binary_sensor.bath_occupied", bath_state)
    hass.states.async_set("sensor.hall_lux", lux)
    hass.states.async_set("light.hall", "off")
    hass.states.async_set("light.bath", "off")
    calls = []

    async def record(call):
        target = call.data.get("entity_id")
        if isinstance(target, list) and len(target) == 1:
            target = target[0]
        calls.append((f"{call.domain}.{call.service}", target))
        if call.domain == "homeassistant":
            hass.states.async_set(target, "on" if call.service == "turn_on" else "off")

    hass.services.async_register("homeassistant", "turn_on", record)
    hass.services.async_register("homeassistant", "turn_off", record)
    hass.services.async_register("input_boolean", "turn_on", record)
    hass.services.async_register("input_boolean", "turn_off", record)
    hass.services.async_register("system_log", "write", record)

    values = expanded(zones)
    actions = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA([{"variables": values["variables"]}, *values["actions"]])
    )
    script = Script(hass, actions, "Multi-zone motion real HA test", "automation",
                    script_mode="queued")

    async def trigger(id="motion_on", entity_id="binary_sensor.hall_motion"):
        await script.async_run({"trigger": {"id": id, "entity_id": entity_id}}, Context())
        await hass.async_block_till_done()

    return hass, calls, trigger


@pytest.mark.asyncio
async def test_movement_activates_only_its_configured_zone(tmp_path):
    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall"),
        zone("Bath", "binary_sensor.bath_motion", "light.bath"),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones)
    try:
        await trigger()
        assert calls == [("homeassistant.turn_on", "light.hall")]
        await trigger(entity_id="binary_sensor.bath_motion")
        assert calls == [("homeassistant.turn_on", "light.hall"),
                         ("homeassistant.turn_on", "light.bath")]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_lux_and_blocker_prevent_activation_without_affecting_other_zone(tmp_path):
    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             lux_sensor="sensor.hall_lux", lux_threshold=30),
        zone("Bath", "binary_sensor.bath_motion", "light.bath"),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones, lux="80")
    try:
        await trigger()
        assert calls == []
        await trigger(entity_id="binary_sensor.bath_motion")
        assert calls == [("homeassistant.turn_on", "light.bath")]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_cross_room_active_presence_cannot_switch_hall_off(tmp_path):
    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             linked_presence=["binary_sensor.bath_occupied"]),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones, bath_state="on")
    try:
        hass.states.async_set("binary_sensor.hall_motion", "off")
        hass.states.async_set("light.hall", "on")
        await trigger(id="off_reconcile")
        assert not calls
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_script_or_scene_with_no_off_target_does_not_send_off(tmp_path):
    zones = [{
        "name": "Scene zone", "motion_sensors": ["binary_sensor.hall_motion"],
        "on_entities": ["scene.hall_night"],
        "off_delay_seconds": 30,
    }]
    hass, calls, trigger = await make_runner(tmp_path, zones)
    try:
        await trigger()
        assert calls == [("homeassistant.turn_on", "scene.hall_night")]
        await trigger(id="off_reconcile")
        assert not any(service == "homeassistant.turn_off" for service, _ in calls)
    finally:
        await hass.async_stop()
