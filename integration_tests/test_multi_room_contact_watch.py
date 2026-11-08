"""Validate the new room form and action tree with real Home Assistant 2026.11.0."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
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
FILE = ROOT / "blueprints/automation/multi_room_contact_watch/multi_room_contact_watch.yaml"


def room(name, contact, **additional):
    return {
        "name": name,
        "contacts": [contact],
        "issue_state": "on",
        "open_minutes": 10,
        "enabled": True,
        **additional,
    }


def expanded(rooms, **options):
    blueprint = Blueprint(load_yaml(str(FILE)), expected_domain="automation",
                          schema=BLUEPRINT_SCHEMA)
    assert blueprint.validate() is None
    inputs = BlueprintInputs(blueprint, {"use_blueprint": {
        "path": "multi_room_contact_watch.yaml",
        "input": {
            "rooms": rooms,
            **options,
        },
    }})
    inputs.validate()
    return inputs.async_substitute()


@pytest.mark.asyncio
async def test_room_actions_validate_using_real_ha_2026_11(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)

    hass.states.async_set("binary_sensor.kitchen_window", "off")
    hass.states.async_set("binary_sensor.hall_door", "off")
    calls = []

    async def record(call):
        calls.append((call.domain, call.service, dict(call.data)))

    for domain, service in (
        ("notify", "send_message"),
        ("persistent_notification", "create"),
        ("persistent_notification", "dismiss"),
        ("system_log", "write"),
    ):
        hass.services.async_register(domain, service, record)

    settings = expanded(
        [room("Kitchen", "binary_sensor.kitchen_window"),
         room("Hall", "binary_sensor.hall_door")],
        notify_entities=["notify.phone"],
        persistent_notifications=False,
    )
    script_actions = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA(
            [{"variables": settings["variables"]}, *settings["actions"]]
        ),
    )
    script = Script(hass, script_actions, "Contact Watch HA 2026.11",
                    "automation", script_mode="queued")
    try:
        await script.async_run(
            {
                "trigger": {"id": "minute"},
                "this": SimpleNamespace(entity_id="automation.contact_watch_test"),
            },
            Context(),
        )
        await hass.async_block_till_done()
        assert calls == []  # Closed contacts without prior warnings send no alerts.

        # Simulate a physical contact whose ON state began ten minutes ago.
        hass.states.async_set("binary_sensor.kitchen_window", "on")
        hass.states.get("binary_sensor.kitchen_window").last_changed = (
            datetime.now(timezone.utc) - timedelta(minutes=10, seconds=10)
        )
        await script.async_run(
            {"trigger": {"id": "minute"},
             "this": SimpleNamespace(entity_id="automation.contact_watch_test")},
            Context(),
        )
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0][0:2] == ("notify", "send_message")
        assert "Kitchen" in calls[0][2]["message"]
        assert "Hall" not in calls[0][2]["message"]

        # A vanished Zigbee contact must produce an independent health warning.
        hass.states.async_set("binary_sensor.kitchen_window", "unavailable")
        hass.states.get("binary_sensor.kitchen_window").last_changed = (
            datetime.now(timezone.utc) - timedelta(minutes=15, seconds=10)
        )
        await script.async_run(
            {"trigger": {"id": "minute"},
             "this": SimpleNamespace(entity_id="automation.contact_watch_test")},
            Context(),
        )
        await hass.async_block_till_done()
        assert len(calls) == 2
        assert calls[1][0:2] == ("notify", "send_message")
        assert "sensor health warning" in calls[1][2]["title"]

        # A recovered closed sensor must not generate another warning.
        hass.states.async_set("binary_sensor.kitchen_window", "off")
        await script.async_run(
            {"trigger": {"id": "minute"},
             "this": SimpleNamespace(entity_id="automation.contact_watch_test")},
            Context(),
        )
        await hass.async_block_till_done()
        assert len(calls) == 2
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_zero_rooms_inert_and_script_valid(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    settings = expanded([])
    script_actions = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA(
            [{"variables": settings["variables"]}, *settings["actions"]]
        ),
    )
    script = Script(hass, script_actions, "Empty Contact Watch",
                    "automation", script_mode="queued")
    try:
        await script.async_run(
            {"trigger": {"id": "minute"},
             "this": SimpleNamespace(entity_id="automation.empty_contact_watch")},
            Context(),
        )
        await hass.async_block_till_done()
    finally:
        await hass.async_stop()
