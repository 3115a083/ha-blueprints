"""Real Home Assistant blueprint, action schema, and automation-script tests.

All TV, light, helper, and phone endpoints below are fakes. These tests do
not claim to verify physical TV power state or real mobile push delivery.
"""
from pathlib import Path
from time import time
from types import SimpleNamespace

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
PATH = ROOT / "blueprints/automation/tv_ambilight_sync/tv_ambilight_sync.yaml"
TV = "media_player.living_room_tv"
LIGHT = "light.tv_ambilight"
LATCH = "input_boolean.ambilight_timeout_guard"


def expanded(**extra):
    bp = Blueprint(load_yaml(str(PATH)), expected_domain="automation", schema=BLUEPRINT_SCHEMA)
    assert bp.validate() is None
    options = BlueprintInputs(bp, {"use_blueprint": {
        "path": "tv_ambilight_sync.yaml",
        "input": {"tv_entity": TV, "ambilight_entity": LIGHT, **extra},
    }})
    options.validate()
    return options.async_substitute()


async def build(tmp_path, **extra):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    calls = []

    async def receive(call):
        data = dict(call.data)
        calls.append((call.domain, call.service, data))
        if (call.domain, call.service) in {
            ("homeassistant", "turn_on"), ("homeassistant", "turn_off"),
            ("input_boolean", "turn_on"), ("input_boolean", "turn_off"),
        }:
            entity_id = data["entity_id"]
            hass.states.async_set(entity_id, "on" if call.service == "turn_on" else "off")

    for domain, services in (
        ("homeassistant", ("turn_on", "turn_off")),
        ("input_boolean", ("turn_on", "turn_off")),
        ("notify", ("mobile_app_phone",)),
        ("persistent_notification", ("create",)),
    ):
        for service in services:
            hass.services.async_register(domain, service, receive)

    cfg = expanded(**extra)
    steps = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA([{"variables": cfg["variables"]}, *cfg["actions"]])
    )
    runner = Script(hass, steps, "TV Ambilight Sync test", "automation", script_mode="restart")

    async def run(trigger_id="reconcile", **kwargs):
        await runner.async_run(
            {
                "trigger": {"id": trigger_id, **kwargs},
                "this": SimpleNamespace(entity_id="automation.tv_ambilight_sync"),
            },
            Context(),
        )
        await hass.async_block_till_done()

    return hass, calls, run


def changed(calls, domain, service):
    return [data for dom, action, data in calls if (dom, action) == (domain, service)]


@pytest.mark.asyncio
async def test_tv_power_following_and_unavailable_fail_off(tmp_path):
    hass, calls, run = await build(tmp_path)
    try:
        hass.states.async_set(TV, "off")
        hass.states.async_set(LIGHT, "off")
        await run("tv_changed")
        assert not changed(calls, "homeassistant", "turn_on")

        hass.states.async_set(TV, "on")
        await run("tv_changed")
        assert len(changed(calls, "homeassistant", "turn_on")) == 1
        assert hass.states.get(LIGHT).state == "on"

        calls.clear()
        hass.states.async_set(TV, "unavailable")
        await run("tv_changed")
        assert len(changed(calls, "homeassistant", "turn_off")) == 1
        assert hass.states.get(LIGHT).state == "off"

        calls.clear()
        hass.states.async_set(TV, "paused")
        await run("tv_changed")
        assert len(changed(calls, "homeassistant", "turn_on")) == 1
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_arbitrary_and_or_conditions_while_tv_stays_on(tmp_path):
    conditions = [
        {"condition": "numeric_state", "entity_id": "sensor.living_room_lux", "below": 25},
        {"condition": "or", "conditions": [
            {"condition": "state", "entity_id": "binary_sensor.room_occupied", "state": "on"},
            {"condition": "state", "entity_id": "input_boolean.movie_mode", "state": "on"},
        ]},
    ]
    hass, calls, run = await build(
        tmp_path, enable_conditions=conditions,
        watch_entities=["sun.sun", "sensor.living_room_lux", "binary_sensor.room_occupied"],
    )
    try:
        hass.states.async_set(TV, "on")
        hass.states.async_set(LIGHT, "off")
        hass.states.async_set("sensor.living_room_lux", "10")
        hass.states.async_set("binary_sensor.room_occupied", "on")
        hass.states.async_set("input_boolean.movie_mode", "off")
        await run("tv_changed")
        assert hass.states.get(LIGHT).state == "on"

        calls.clear()
        hass.states.async_set("binary_sensor.room_occupied", "off")
        await run("dependency_changed")
        assert changed(calls, "homeassistant", "turn_off")
        assert hass.states.get(LIGHT).state == "off"

        calls.clear()
        hass.states.async_set("input_boolean.movie_mode", "on")
        await run("reconcile")
        assert changed(calls, "homeassistant", "turn_on")

        calls.clear()
        hass.states.async_set("sensor.living_room_lux", "40")
        await run("dependency_changed")
        assert changed(calls, "homeassistant", "turn_off")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_direct_timeout_latches_and_does_not_reactivate(tmp_path):
    hass, calls, run = await build(
        tmp_path, max_on_minutes=5, timeout_lockout=LATCH,
        timeout_behavior="turn_off",
    )
    try:
        hass.states.async_set(TV, "on")
        hass.states.async_set(LATCH, "off")
        hass.states.async_set(LIGHT, "on", timestamp=time() - 360)
        await run("reconcile")
        assert changed(calls, "input_boolean", "turn_on")
        assert changed(calls, "homeassistant", "turn_off")
        assert hass.states.get(LATCH).state == "on"
        assert hass.states.get(LIGHT).state == "off"

        calls.clear()
        await run("reconcile")
        assert not changed(calls, "homeassistant", "turn_on")

        hass.states.async_set(TV, "off")
        await run("tv_changed")
        assert hass.states.get(LATCH).state == "off"

        hass.states.async_set(TV, "on")
        calls.clear()
        await run("tv_changed")
        assert changed(calls, "homeassistant", "turn_on")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_actionable_mobile_timeout_and_button_off(tmp_path):
    hass, calls, run = await build(
        tmp_path, max_on_minutes=5, timeout_lockout=LATCH,
        timeout_behavior="notify", mobile_notify_action="notify.mobile_app_phone",
    )
    try:
        hass.states.async_set(TV, "on")
        hass.states.async_set(LATCH, "off")
        hass.states.async_set(LIGHT, "on", timestamp=time() - 360)
        await run()
        assert hass.states.get(LATCH).state == "on"
        assert hass.states.get(LIGHT).state == "on"
        notices = changed(calls, "notify", "mobile_app_phone")
        assert len(notices) == 1
        button = notices[0]["data"]["actions"][0]
        assert button["title"] == "Turn off Ambilight"
        assert button["action"] == "TV_AMBILIGHT_OFF_automation.tv_ambilight_sync"

        calls.clear()
        await run()
        assert not changed(calls, "notify", "mobile_app_phone")

        await run("notification_action", event=SimpleNamespace(data={"action": "WRONG"}))
        assert hass.states.get(LIGHT).state == "on"

        await run("notification_action", event=SimpleNamespace(data={"action": button["action"]}))
        assert hass.states.get(LIGHT).state == "off"
        assert changed(calls, "homeassistant", "turn_off")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_invalid_mobile_action_falls_back_to_direct_off(tmp_path):
    hass, calls, run = await build(
        tmp_path, max_on_minutes=5, timeout_lockout=LATCH,
        timeout_behavior="notify", mobile_notify_action="notify.some_other_service",
    )
    try:
        hass.states.async_set(TV, "on")
        hass.states.async_set(LATCH, "off")
        hass.states.async_set(LIGHT, "on", timestamp=time() - 360)
        await run()
        assert changed(calls, "homeassistant", "turn_off")
        assert not changed(calls, "notify", "mobile_app_phone")
        assert changed(calls, "persistent_notification", "create")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_timeout_without_helper_keeps_ambilight_off(tmp_path):
    hass, calls, run = await build(tmp_path, max_on_minutes=5)
    try:
        hass.states.async_set(TV, "on")
        hass.states.async_set(LIGHT, "off")
        await run("tv_changed")
        assert not changed(calls, "homeassistant", "turn_on")
        assert changed(calls, "persistent_notification", "create")
        hass.states.async_set(LIGHT, "on")
        calls.clear()
        await run("ambilight_changed")
        assert changed(calls, "homeassistant", "turn_off")
    finally:
        await hass.async_stop()
