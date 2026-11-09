"""Real Home Assistant script behavior for Multi-Zone Motion Lighting.

Services are mocked, no physical lights or presence devices are accessed.
"""
from datetime import timedelta
from pathlib import Path

import pytest

from homeassistant import loader
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.util import dt as dt_util, yaml as yaml_util

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "blueprints/automation/motion_lighting_multi_zone/motion_lighting_multi_zone.yaml"
HALL = "binary_sensor.hallway_motion"
BATH = "binary_sensor.bathroom_motion"
OCCUPANCY = "binary_sensor.bathroom_occupancy"
HALL_LIGHT = "light.hallway"
BATH_LIGHT = "light.bathroom"


def zone(name, sensor, target, **settings):
    return {
        "name": name,
        "enabled": True,
        "motion_sensors": [sensor],
        "turn_on_entity": target,
        "auto_off": True,
        "off_delay_seconds": 60,
        **settings,
    }


def config(zones, **inputs):
    blueprint = Blueprint(
        yaml_util.load_yaml(str(FILE)), expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    )
    assert blueprint.validate() is None
    instance = BlueprintInputs(blueprint, {
        "use_blueprint": {
            "path": FILE.name,
            "input": {
                "trigger_sensors": [HALL, BATH],
                "zone_entries": zones,
                **inputs,
            },
        },
    })
    instance.validate()
    return instance.async_substitute()


async def environment(tmp_path, zones=None, *, motion_age=200, occupancy_age=200,
                      hall_light_age=250, **inputs):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    now = dt_util.utcnow()
    calls = []

    def state(entity, value, age=200):
        hass.states._states[entity] = State(
            entity, value, last_changed=now - timedelta(seconds=age)
        )

    state(HALL, "off", motion_age)
    state(BATH, "off", motion_age)
    state(OCCUPANCY, "off", occupancy_age)
    state(HALL_LIGHT, "on", hall_light_age)
    state(BATH_LIGHT, "off", hall_light_age)
    state("sun.sun", "below_horizon", 1000)

    async def record(call):
        targets = call.data.get("entity_id", [])
        if isinstance(targets, str):
            targets = [targets]
        calls.append((call.domain, call.service, tuple(targets)))
        for target in targets:
            if call.service == "turn_on":
                hass.states.async_set(target, "on")
            elif call.service == "turn_off":
                hass.states.async_set(target, "off")

    hass.services.async_register("homeassistant", "turn_on", record)
    hass.services.async_register("homeassistant", "turn_off", record)

    if zones is None:
        zones = [
            zone(
                "Hallway", HALL, HALL_LIGHT,
                linked_presence=[OCCUPANCY], linked_behavior="hold",
                linked_seconds=120,
            ),
            zone("Bathroom", BATH, BATH_LIGHT),
        ]

    expanded = config(zones, **inputs)
    actions = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA([
            {"variables": expanded["variables"]}, *expanded["actions"]
        ]),
    )
    script = Script(
        hass, actions, "Multi Zone Motion Lighting real HA test",
        "automation", script_mode="single",
    )

    async def run(trigger_id="off_check", sensor=HALL):
        await script.async_run(
            {
                "trigger": {"id": trigger_id, "entity_id": sensor},
                "this": {"entity_id": "automation.motion_zones"},
            },
            Context(),
        )
        await hass.async_block_till_done()

    return hass, calls, run, state


@pytest.mark.asyncio
async def test_real_blueprint_loads_and_zones_are_independent(tmp_path):
    hass, calls, run, state = await environment(tmp_path)
    try:
        state(HALL_LIGHT, "off", 200)
        await run("motion_on", HALL)
        assert calls == [("homeassistant", "turn_on", (HALL_LIGHT,))]
        calls.clear()
        await run("motion_on", BATH)
        assert calls == [("homeassistant", "turn_on", (BATH_LIGHT,))]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_hold_neighbor_occupancy_blocks_off_then_grace(tmp_path):
    hass, calls, run, state = await environment(tmp_path)
    try:
        state(OCCUPANCY, "on", 200)
        await run()
        assert calls == []
        state(OCCUPANCY, "off", 30)
        await run()
        assert calls == []
        state(OCCUPANCY, "off", 180)
        await run()
        assert calls == [("homeassistant", "turn_off", (HALL_LIGHT,))]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_extend_is_not_a_permanent_hold(tmp_path):
    zones = [zone(
        "Hallway", HALL, HALL_LIGHT,
        linked_presence=[OCCUPANCY], linked_behavior="extend",
        linked_seconds=120,
    )]
    hass, calls, run, state = await environment(tmp_path, zones)
    try:
        state(HALL, "off", 100)
        state(OCCUPANCY, "on", 200)
        await run()
        assert calls == []
        state(HALL, "off", 200)
        await run()
        assert calls == [("homeassistant", "turn_off", (HALL_LIGHT,))]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_motion", ["on", "unknown", "unavailable"])
async def test_motion_active_or_unknown_prevents_off(tmp_path, bad_motion):
    hass, calls, run, state = await environment(
        tmp_path, [zone("Hallway", HALL, HALL_LIGHT)]
    )
    try:
        state(HALL, bad_motion)
        await run()
        assert calls == []
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_presence", ["unknown", "unavailable"])
async def test_unknown_linked_presence_fails_closed(tmp_path, bad_presence):
    hass, calls, run, state = await environment(tmp_path)
    try:
        state(OCCUPANCY, bad_presence)
        await run()
        assert calls == []
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_manually_turned_on_after_motion_ended_is_preserved(tmp_path):
    hass, calls, run, state = await environment(
        tmp_path, [zone("Hallway", HALL, HALL_LIGHT)]
    )
    try:
        state(HALL, "off", 200)
        state(HALL_LIGHT, "on", 100)
        await run()
        assert calls == []
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("lux,expected", [(10, True), (90, False), ("unavailable", False)])
async def test_illuminance_threshold(tmp_path, lux, expected):
    zones = [zone(
        "Hallway", HALL, HALL_LIGHT,
        illuminance_sensor="sensor.hall_lux", illuminance_below=45,
    )]
    hass, calls, run, state = await environment(tmp_path, zones)
    try:
        state(HALL_LIGHT, "off")
        state("sensor.hall_lux", str(lux))
        await run("motion_on", HALL)
        assert bool(calls) == expected
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_sun_and_global_blocker_prevent_on(tmp_path):
    zones = [zone("Hallway", HALL, HALL_LIGHT, sun_mode="above")]
    hass, calls, run, state = await environment(tmp_path, zones)
    try:
        state(HALL_LIGHT, "off")
        await run("motion_on", HALL)
        assert calls == []
        state("sun.sun", "above_horizon")
        await run("motion_on", HALL)
        assert calls == [("homeassistant", "turn_on", (HALL_LIGHT,))]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_scene_and_off_target(tmp_path):
    zones = [zone(
        "Hallway", HALL, "scene.hall",
        turn_off_entities=[HALL_LIGHT],
    )]
    hass, calls, run, state = await environment(tmp_path, zones)
    try:
        state(HALL_LIGHT, "off")
        await run("motion_on", HALL)
        assert calls == [("homeassistant", "turn_on", ("scene.hall",))]
        calls.clear()
        state(HALL_LIGHT, "on", 250)
        await run()
        assert calls == [("homeassistant", "turn_off", (HALL_LIGHT,))]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_no_room_entries_is_inert(tmp_path):
    hass, calls, run, state = await environment(tmp_path, [])
    try:
        await run("motion_on", HALL)
        await run()
        assert calls == []
    finally:
        await hass.async_stop()

@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["zone", "global"])
@pytest.mark.parametrize("blocker_state,expected_on", [
    ("on", False), ("off", True), ("unknown", False), ("unavailable", False),
])
async def test_other_light_blocks_activation_but_not_unrelated_zone(
        tmp_path, scope, blocker_state, expected_on):
    settings = {"on_blocker": "light.manual_lamp"} if scope == "zone" else {}
    inputs = {"on_blocker_global": "light.manual_lamp"} if scope == "global" else {}
    zones = [
        zone("Hallway", HALL, HALL_LIGHT, **settings),
        zone("Bathroom", BATH, BATH_LIGHT),
    ]
    hass, calls, run, state = await environment(tmp_path, zones, **inputs)
    try:
        state(HALL_LIGHT, "off")
        state("light.manual_lamp", blocker_state)
        await run("motion_on", HALL)
        assert calls == (
            [("homeassistant", "turn_on", (HALL_LIGHT,))] if expected_on else []
        )
        calls.clear()
        await run("motion_on", BATH)
        assert calls == (
            [("homeassistant", "turn_on", (BATH_LIGHT,))]
            if scope == "zone" or expected_on else []
        )
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_light_turn_off_blocker_does_not_block_initial_activation(tmp_path):
    zones = [zone("Hallway", HALL, HALL_LIGHT,
                  off_blocker="light.manual_lamp")]
    hass, calls, run, state = await environment(tmp_path, zones)
    try:
        state(HALL_LIGHT, "off")
        state("light.manual_lamp", "on")
        await run("motion_on", HALL)
        assert calls == [("homeassistant", "turn_on", (HALL_LIGHT,))]
    finally:
        await hass.async_stop()
