"""Proximity direction, sustained Bluetooth, calendar and notify target tests."""
import json
from datetime import datetime, timezone
from time import time

from types import SimpleNamespace
import pytest

from integration_tests.test_garage_automation_manager import (
    BT, GPS, TRIP, GARAGE, DEADLINE, build, actions,
)

DIRECTION = "sensor.driver_proximity_direction"
DISTANCE = "sensor.driver_proximity_distance"


def gps(hass, latitude=52.5201, accuracy=10):
    hass.states.async_set(GPS, "home", {
        "latitude": latitude,
        "longitude": 13.405,
        "gps_accuracy": accuracy,
        "tracking_type": "position",
    })
    return hass.states.get(GPS)


def direction(hass, state):
    hass.states.async_set(DIRECTION, state)
    return hass.states.get(DIRECTION)


def distance(hass, km):
    hass.states.async_set(DISTANCE, str(km))
    return hass.states.get(DISTANCE)


def car(hass, name="My Car"):
    hass.states.async_set(BT, "1", {
        "connected_paired_devices": [f"AA:BB:CC:DD:EE:FF ({name})"],
    })


def trip(hass, start_distance=900, since_seconds=180):
    hass.states.async_set(TRIP, json.dumps({
        "s": int(time()) - since_seconds,
        "d": start_distance,
    }))


def config(**kwargs):
    opts = {
        "vehicle_enabled": True,
        "vehicle_gps_tracker": GPS,
        "vehicle_proximity_direction": DIRECTION,
        "vehicle_proximity_distance": DISTANCE,
        "vehicle_session_helper": TRIP,
        "vehicle_bluetooth_sensor": BT,
        "vehicle_bluetooth_device": "My Car",
        "vehicle_connection_sensors": ["binary_sensor.garage_car_connection_placeholder"],
        "vehicle_min_approach_meters": 300,
        "vehicle_min_connection_minutes": 2,
        "vehicle_max_gps_accuracy_meters": 25,
        "vehicle_nearby_meters": 0,
        **kwargs,
    }
    return opts


@pytest.mark.asyncio
async def test_proximity_towards_starts_trip_arrived_opens_after_approach_and_time(tmp_path):
    hass, calls, setup, run = await build(tmp_path, **config())
    try:
        setup()
        car(hass)
        gps(hass)
        distance(hass, 0.90)
        await run("vehicle_approach", to_state=direction(hass, "towards"))
        assert not actions(calls, "cover", "open_cover")
        writes = actions(calls, "input_text", "set_value")
        assert len(writes) == 1
        saved = json.loads(writes[0]["value"])
        assert 899 <= saved["d"] <= 901
        assert saved["s"] > 0

        # A connection observed only a few seconds ago cannot open the door.
        distance(hass, 0)
        calls.clear()
        await run("vehicle_approach", to_state=direction(hass, "arrived"))
        assert not actions(calls, "cover", "open_cover")
        assert hass.states.get(TRIP).state == ""

        # A new, mature observed trip may open on the next arrived event.
        trip(hass, start_distance=900, since_seconds=180)
        calls.clear()
        await run("vehicle_approach", to_state=direction(hass, "arrived"))
        assert len(actions(calls, "cover", "open_cover")) == 1
        assert hass.states.get(TRIP).state == ""
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_arrival_blocks_wrong_bluetooth_inaccurate_gps_short_trip(tmp_path):
    hass, calls, setup, run = await build(tmp_path, **config())
    try:
        setup()
        gps(hass)
        distance(hass, 0)
        car(hass, "Not My Car")
        trip(hass)
        await run("vehicle_approach", to_state=direction(hass, "arrived"))
        assert not actions(calls, "cover", "open_cover")

        car(hass)
        gps(hass, accuracy=85)
        trip(hass)
        calls.clear()
        await run("vehicle_approach", to_state=direction(hass, "arrived"))
        assert not actions(calls, "cover", "open_cover")

        gps(hass, accuracy=12)
        trip(hass, start_distance=200)
        calls.clear()
        await run("vehicle_approach", to_state=direction(hass, "arrived"))
        assert not actions(calls, "cover", "open_cover")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_optional_extra_home_center_radius_blocks_early_zone_arrival(tmp_path):
    hass, calls, setup, run = await build(tmp_path, **config(
        vehicle_nearby_meters=25,
    ))
    try:
        setup()
        car(hass)
        gps(hass, latitude=52.5206)
        distance(hass, 0)
        trip(hass)
        await run("vehicle_approach", to_state=direction(hass, "arrived"))
        assert not actions(calls, "cover", "open_cover")
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_bluetooth_disconnection_or_direction_away_resets_trip(tmp_path):
    hass, calls, setup, run = await build(tmp_path, **config())
    try:
        setup()
        car(hass)
        trip(hass)
        hass.states.async_set(BT, "0", {"connected_paired_devices": []})
        await run("vehicle_bluetooth_changed", to_state=hass.states.get(BT))
        assert hass.states.get(TRIP).state == ""

        car(hass)
        trip(hass)
        await run("vehicle_approach", to_state=direction(hass, "away_from"))
        assert hass.states.get(TRIP).state == ""

        trip(hass)
        await run("startup")
        assert hass.states.get(TRIP).state == ""
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_calendar_only_home_person_and_custom_conditions(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, calendar_enabled=True, calendar_entity="calendar.test",
        calendar_summary_filter="Garage", calendar_home_person="person.driver",
        calendar_open_conditions=[{
            "condition": "state",
            "entity_id": "input_boolean.calendar_ok",
            "state": "on",
        }],
        schedule_enabled=True, schedule_entity="schedule.garage",
    )
    try:
        setup()
        event = SimpleNamespace(summary="Garage appointment", all_day=False)
        hass.states.async_set("person.driver", "not_home")
        hass.states.async_set("input_boolean.calendar_ok", "on")
        await run("calendar_open", calendar_event=event)
        assert not actions(calls, "cover", "open_cover")

        hass.states.async_set("person.driver", "home")
        hass.states.async_set("input_boolean.calendar_ok", "off")
        await run("calendar_open", calendar_event=event)
        assert not actions(calls, "cover", "open_cover")

        await run("schedule_open")
        assert len(actions(calls, "cover", "open_cover")) == 1
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_selected_notify_entities_receive_warning_without_companion_buttons(tmp_path):
    hass, calls, setup, run = await build(
        tmp_path, automatic_closing_enabled=True,
        mobile_notify_action="",
        notify_entities=["notify.household"],
        notify_before_minutes=5,
    )
    try:
        setup(garage="open")
        hass.states.async_set(DEADLINE, datetime.fromtimestamp(
            time() + 180, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        await run("deadline_changed")
        messages = actions(calls, "notify", "send_message")
        assert len(messages) == 1
        assert messages[0]["entity_id"] == ["notify.household"]
        assert "Garage" in messages[0]["title"]
        assert not actions(calls, "notify", "mobile_app_phone")
    finally:
        await hass.async_stop()
