"""Real HA 2026.11 schema and simulated garage action regression tests.

Fake devices are used throughout. These tests cannot replace physical
entrapment protection, reverse-function verification or vehicle arrival tests.
"""
from datetime import datetime, timezone
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
PATH = ROOT / "blueprints/automation/garage_automation_manager/garage_automation_manager.yaml"
GARAGE = "cover.test_garage"
CLEAR = "binary_sensor.test_clearance"
DEADLINE = "input_datetime.test_garage_close_deadline"
DOOR = "binary_sensor.test_house_door"
ARRIVAL = "sensor.test_distance"
DIRECTION = "sensor.test_direction"
PHONE = "binary_sensor.test_car_connected"


def expanded(**extra):
    bp = Blueprint(load_yaml(str(PATH)), expected_domain="automation", schema=BLUEPRINT_SCHEMA)
    assert bp.validate() is None
    input_values = {
        "garage_cover": GARAGE,
        "safety_clear_sensor": CLEAR,
        "close_deadline_helper": DEADLINE,
        **extra,
    }
    opts = BlueprintInputs(bp, {"use_blueprint": {
        "path": "garage_automation_manager.yaml", "input": input_values,
    }})
    opts.validate()
    return opts.async_substitute()


async def build(tmp_path, **options):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    calls = []

    async def record(call):
        data = dict(call.data)
        calls.append((call.domain, call.service, data))
        if call.domain == "cover":
            names = data.get("entity_id", [])
            if isinstance(names, str):
                names = [names]
            for entity_id in names:
                # Simulate confirmed cover movement after command.
                hass.states.async_set(entity_id, "open" if call.service == "open_cover" else "closed")
        if (call.domain, call.service) == ("input_datetime", "set_datetime"):
            names = data.get("entity_id", [])
            if isinstance(names, str):
                names = [names]
            stamp = float(data["timestamp"])
            for entity_id in names:
                hass.states.async_set(entity_id, datetime.fromtimestamp(
                    stamp, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    for domain, services in (
        ("cover", ("open_cover", "close_cover")),
        ("input_datetime", ("set_datetime",)),
        ("notify", ("mobile_app_phone",)),
        ("persistent_notification", ("create",)),
        ("test", ("marker",)),
    ):
        for service in services:
            hass.services.async_register(domain, service, record)

    config = expanded(**options)
    actions = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]])
    )
    script = Script(hass, actions, "Garage manager test", "automation", script_mode="queued")

    def setup_states(garage="closed", safety="off"):
        hass.states.async_set(GARAGE, garage)
        hass.states.async_set(CLEAR, safety)
        hass.states.async_set(DEADLINE, "2020-01-01 00:00:00")
        hass.states.async_set(DOOR, "off")

    async def run(kind, **kwargs):
        await script.async_run({
            "trigger": {"id": kind, **kwargs},
            "this": SimpleNamespace(entity_id="automation.garage_manager"),
        }, Context())
        await hass.async_block_till_done()

    return hass, calls, setup_states, run


def actions(calls, domain, service):
    return [data for d, s, data in calls if (d, s) == (domain, service)]


@pytest.mark.asyncio
async def test_calendar_summary_filter_and_all_day_protection(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, calendar_enabled=True, calendar_entity="calendar.test",
        calendar_summary_filter="Garage", calendar_allow_all_day=False,
    )
    try:
        setup()
        def calendar(summary, all_day=False):
            return SimpleNamespace(summary=summary, all_day=all_day)
        await run("calendar_open", calendar_event=calendar("Dentist appointment"))
        assert not actions(calls, "cover", "open_cover")
        await run("calendar_open", calendar_event=calendar("GARAGE service", True))
        assert not actions(calls, "cover", "open_cover")
        await run("calendar_open", calendar_event=calendar("Garage service"))
        assert len(actions(calls, "cover", "open_cover")) == 1
        assert hass.states.get(GARAGE).state == "open"
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_schedule_and_custom_open_request_with_conditions(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, schedule_enabled=True, schedule_entity="schedule.weekly",
        custom_open_enabled=True, custom_open_requests=["input_boolean.garage_request"],
        open_conditions=[{
            "condition": "state", "entity_id": "input_boolean.can_open_garage", "state": "on",
        }],
    )
    try:
        setup()
        hass.states.async_set("input_boolean.can_open_garage", "off")
        await run("schedule_open")
        assert not actions(calls, "cover", "open_cover")
        hass.states.async_set("input_boolean.can_open_garage", "on")
        await run("custom_open")
        assert len(actions(calls, "cover", "open_cover")) == 1
        calls.clear()
        await run("schedule_open")
        assert not actions(calls, "cover", "open_cover")  # already open
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_approach_needs_car_connection_and_towards(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, vehicle_enabled=True,
        vehicle_distance_sensor=ARRIVAL, vehicle_direction_sensor=DIRECTION,
        vehicle_connection_sensors=[PHONE], vehicle_distance_threshold=0.5,
    )
    try:
        setup()
        hass.states.async_set(DIRECTION, "towards")
        hass.states.async_set(PHONE, "off")
        old = hass.states.async_set(ARRIVAL, "0.8")
        previous = hass.states.get(ARRIVAL)
        hass.states.async_set(ARRIVAL, "0.3")
        current = hass.states.get(ARRIVAL)
        await run("vehicle_approach", from_state=previous, to_state=current)
        assert not actions(calls, "cover", "open_cover")
        hass.states.async_set(PHONE, "on")
        await run("vehicle_approach", from_state=previous, to_state=current)
        assert len(actions(calls, "cover", "open_cover")) == 1
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_timer_starts_only_after_observed_open_and_persists_deadline(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True, close_after_minutes=10,
    )
    try:
        setup(garage="open")
        await run("garage_opened", from_state=SimpleNamespace(state="opening"))
        writes = actions(calls, "input_datetime", "set_datetime")
        assert len(writes) == 1
        assert abs(float(writes[0]["timestamp"]) - (time() + 600)) < 8
        assert hass.states.get(DEADLINE).state.startswith(datetime.now(
            timezone.utc).strftime("%Y-%m-%d"))
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_auto_close_requires_current_clearance_and_close_conditions(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
        close_conditions=[{
            "condition": "state", "entity_id": "input_boolean.allow_closing", "state": "on",
        }],
    )
    try:
        setup(garage="open", safety="off")
        # A stored deadline inside the allowed 5-minute overdue safety window.
        hass.states.async_set(DEADLINE, datetime.fromtimestamp(
            time() - 45, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        hass.states.async_set("input_boolean.allow_closing", "off")
        await run("minute_check")
        assert not actions(calls, "cover", "close_cover")
        hass.states.async_set("input_boolean.allow_closing", "on")
        hass.states.async_set(CLEAR, "unavailable")
        await run("minute_check")
        assert not actions(calls, "cover", "close_cover")
        hass.states.async_set(CLEAR, "on")
        await run("minute_check")
        assert not actions(calls, "cover", "close_cover")
        hass.states.async_set(CLEAR, "off")
        await run("minute_check")
        assert len(actions(calls, "cover", "close_cover")) == 1
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_overdue_deadline_is_not_replayed_after_long_outage(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
    )
    try:
        setup(garage="open", safety="off")
        hass.states.async_set(DEADLINE, datetime.fromtimestamp(
            time() - 7200, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        await run("startup")
        await run("minute_check")
        assert not actions(calls, "cover", "close_cover")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_mobile_warning_extension_cancel_and_safe_close_now(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
        mobile_notify_action="notify.mobile_app_phone",
        notify_before_minutes=5, extension_minutes=10,
    )
    try:
        setup(garage="open", safety="off")
        hass.states.async_set(DEADLINE, datetime.fromtimestamp(
            time() + 200, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        await run("deadline_changed")
        alerts = actions(calls, "notify", "mobile_app_phone")
        assert len(alerts) == 1
        buttons = alerts[0]["data"]["actions"]
        keys = {b["title"]: b["action"] for b in buttons}
        assert set(keys) == {"Extend", "Close now", "Cancel automatic closing"}
        calls.clear()
        await run("mobile_action", event=SimpleNamespace(data={"action": keys["Extend"]}))
        extended = actions(calls, "input_datetime", "set_datetime")
        assert extended
        assert float(extended[0]["timestamp"]) > time() + 600

        hass.states.async_set(CLEAR, "unavailable")
        calls.clear()
        await run("mobile_action", event=SimpleNamespace(data={"action": keys["Close now"]}))
        assert not actions(calls, "cover", "close_cover")

        calls.clear()
        await run("mobile_action", event=SimpleNamespace(data={"action": keys["Cancel automatic closing"]}))
        canceled = actions(calls, "input_datetime", "set_datetime")
        assert canceled
        assert float(canceled[0]["timestamp"]) < time() - 80000
        calls.clear()
        hass.states.async_set(CLEAR, "off")
        await run("minute_check")
        assert not actions(calls, "cover", "close_cover")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_house_door_close_checks_obstruction_again(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, door_open_close_enabled=True, house_door_sensor=DOOR,
    )
    try:
        setup(garage="open", safety="on")
        await run("house_door_opened")
        assert not actions(calls, "cover", "close_cover")
        hass.states.async_set(CLEAR, "off")
        await run("house_door_opened")
        assert actions(calls, "cover", "close_cover")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_unconfigured_deadline_does_not_send_automatic_close(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
        close_deadline_helper="input_datetime.garage_close_deadline_placeholder",
    )
    try:
        setup(garage="open")
        await run("startup")
        assert actions(calls, "persistent_notification", "create")
        await run("garage_opened", from_state=SimpleNamespace(state="opening"))
        assert not actions(calls, "input_datetime", "set_datetime")
        await run("minute_check")
        assert not actions(calls, "cover", "close_cover")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_timer_closes_without_home_assistant_clearance_sensor(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
        safety_clear_sensor="",
    )
    try:
        setup(garage="open", safety="unknown")
        hass.states.async_set(DEADLINE, datetime.fromtimestamp(
            time() - 40, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        await run("minute_check")
        assert len(actions(calls, "cover", "close_cover")) == 1
        assert hass.states.get(GARAGE).state == "closed"
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_house_door_trigger_closes_without_home_assistant_clearance_sensor(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, door_open_close_enabled=True, house_door_sensor=DOOR,
        safety_clear_sensor="",
    )
    try:
        setup(garage="open", safety="unavailable")
        await run("house_door_opened")
        assert len(actions(calls, "cover", "close_cover")) == 1
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_mobile_close_now_without_home_assistant_clearance_sensor(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, safety_clear_sensor="",
    )
    try:
        setup(garage="open", safety="unknown")
        await run("mobile_action", event=SimpleNamespace(
            data={"action": "GARAGE_CLOSE_NOW_automation.garage_manager"}))
        assert len(actions(calls, "cover", "close_cover")) == 1
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_configured_sensor_blocks_closing_even_if_it_fails(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
        safety_clear_sensor=CLEAR,
    )
    try:
        setup(garage="open", safety="off")
        hass.states.async_set(DEADLINE, datetime.fromtimestamp(
            time() - 45, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        for blocked in ("on", "unknown", "unavailable"):
            hass.states.async_set(CLEAR, blocked)
            await run("minute_check")
            assert not actions(calls, "cover", "close_cover"), blocked
        hass.states.async_set(CLEAR, "off")
        await run("minute_check")
        assert len(actions(calls, "cover", "close_cover")) == 1
    finally:
        await hass.async_stop()
