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
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set("input_boolean.hall_occupied", "off")
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

    async def trigger(id="motion_on", entity_id="binary_sensor.hall_motion", **extra):
        await script.async_run(
            {"trigger": {"id": id, "entity_id": entity_id, **extra}}, Context()
        )
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


@pytest.mark.asyncio
async def test_ownership_helper_protects_preexisting_manual_light(tmp_path):
    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             ownership_helper="input_boolean.hall_owned"),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones)
    try:
        hass.states.async_set("input_boolean.hall_owned", "off")
        hass.states.async_set("light.hall", "on")  # Someone turned it on first
        await trigger()
        assert calls == []  # Do not claim or retoggle manually activated lights
        hass.states.async_set("light.hall", "off")
        await trigger()
        assert calls == [
            ("homeassistant.turn_on", "light.hall"),
            ("input_boolean.turn_on", "input_boolean.hall_owned"),
        ]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_sunset_activates_only_occupied_opted_in_zone(tmp_path):
    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             darkness_activation="sunset", sun_mode="night",
             occupancy_sensors=["input_boolean.hall_occupied"]),
        zone("Bath", "binary_sensor.bath_motion", "light.bath",
             darkness_activation="sunset", sun_mode="night"),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones)
    try:
        # Hall motion has ended, but a sustained occupancy helper is still ON.
        hass.states.async_set("binary_sensor.hall_motion", "off")
        hass.states.async_set("binary_sensor.bath_motion", "off")
        hass.states.async_set("input_boolean.hall_occupied", "on")
        await trigger(id="sunset", entity_id="sun.sun")
        assert calls == [("homeassistant.turn_on", "light.hall")]
        # A second sunset-like call cannot retoggle an already-on light.
        await trigger(id="sunset", entity_id="sun.sun")
        assert calls == [("homeassistant.turn_on", "light.hall")]
        # Occupancy also prevents the existing off reconciliation.
        await trigger(id="off_reconcile", entity_id="sun.sun")
        assert not any(c[0] == "homeassistant.turn_off" for c in calls)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_lux_crosses_threshold_in_occupied_zone_only(tmp_path):
    from types import SimpleNamespace

    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             darkness_activation="both", lux_sensor="sensor.hall_lux", lux_threshold=80),
        zone("Bath", "binary_sensor.bath_motion", "light.bath",
             darkness_activation="both", lux_sensor="sensor.bath_lux", lux_threshold=35),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones, lux="79")
    try:
        hass.states.async_set("binary_sensor.bath_motion", "off")
        await trigger(
            id="lux_changed", entity_id="sensor.hall_lux",
            from_state=SimpleNamespace(state="100"), to_state=SimpleNamespace(state="79")
        )
        assert calls == [("homeassistant.turn_on", "light.hall")]
        await trigger(
            id="lux_changed", entity_id="sensor.bath_lux",
            from_state=SimpleNamespace(state="60"), to_state=SimpleNamespace(state="30")
        )
        assert calls == [("homeassistant.turn_on", "light.hall")]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_lux_without_threshold_crossing_is_inert(tmp_path):
    from types import SimpleNamespace

    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             darkness_activation="lux", lux_sensor="sensor.hall_lux", lux_threshold=80),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones, lux="65")
    try:
        for before, after in [("unavailable", "65"), ("70", "65"), ("100", "90")]:
            await trigger(
                id="lux_changed", entity_id="sensor.hall_lux",
                from_state=SimpleNamespace(state=before),
                to_state=SimpleNamespace(state=after)
            )
        assert calls == []
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_sunset_does_not_activate_from_only_other_room_presence(tmp_path):
    zones = [
        zone("Hall", "binary_sensor.hall_motion", "light.hall",
             darkness_activation="sunset", linked_presence=["binary_sensor.bath_occupied"]),
    ]
    hass, calls, trigger = await make_runner(tmp_path, zones, bath_state="on")
    try:
        hass.states.async_set("binary_sensor.hall_motion", "off")
        await trigger(id="sunset", entity_id="sun.sun")
        assert calls == []
    finally:
        await hass.async_stop()
