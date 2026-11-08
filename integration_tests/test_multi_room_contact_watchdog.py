"""Real Home Assistant 2026.11.0 schema and script execution checks.

Test doubles represent notification services; no mobile device or Zigbee network is used.
"""
from datetime import datetime, timedelta, timezone
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

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"blueprints/automation/multi_room_contact_watchdog/multi_room_contact_watchdog.yaml"


def room(name,sensors,**extra):
    return {"name":name,"contacts":sensors,**extra}


def expanded(room_entries,monitored,**extra):
    bp=Blueprint(load_yaml(str(PATH)),expected_domain="automation",schema=BLUEPRINT_SCHEMA)
    assert bp.validate() is None
    options=BlueprintInputs(bp,{"use_blueprint":{
        "path":"multi_room_contact_watchdog.yaml",
        "input":{"monitored_contacts":monitored,"room_entries":room_entries,**extra},
    }})
    options.validate()
    return options.async_substitute()


async def build(tmp_path,rooms,monitored,**extra):
    hass=HomeAssistant(str(tmp_path))
    hass.config_entries=ConfigEntries(hass,{})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    calls=[]
    async def receive(call):
        calls.append((call.domain,call.service,dict(call.data)))
    for service in ("create","dismiss"):
        hass.services.async_register("persistent_notification",service,receive)
    hass.services.async_register("notify","mobile_app_phone",receive)
    hass.services.async_register("system_log","write",receive)
    cfg=expanded(rooms,monitored,**extra)
    steps=await async_validate_actions_config(
        hass,cv.SCRIPT_SCHEMA([{"variables":cfg["variables"]},*cfg["actions"]])
    )
    runner=Script(hass,steps,"Contact Watchdog test","automation",script_mode="queued")

    async def run(trigger_id="deadline_check",**kwargs):
        await runner.async_run(
            {"trigger":{"id":trigger_id,**kwargs}},Context()
        )
        await hass.async_block_till_done()
    return hass,calls,run


@pytest.mark.asyncio
async def test_independent_open_and_offline_notifications(tmp_path):
    monitored=["binary_sensor.bath_window","binary_sensor.kitchen_window","binary_sensor.hall_door"]
    hass,calls,run=await build(tmp_path,[
        room("Bathroom",[monitored[0]],open_after_minutes=10),
        room("Kitchen",[monitored[1]],offline_after_minutes=20),
        room("Hall",[monitored[2]],open_after_minutes=10),
    ],monitored,notify_services="notify.mobile_app_phone")
    try:
        hass.states.async_set(monitored[0],"on",{"friendly_name":"Bathroom window"},timestamp=time()-630)
        hass.states.async_set(monitored[1],"unavailable",timestamp=time()-1230)
        hass.states.async_set(monitored[2],"off",timestamp=time()-120)
        await run()
        created=[x for x in calls if x[:2]==("persistent_notification","create")]
        self_tags={x[2]["notification_id"] for x in created}
        assert self_tags=={
            "contact_guard_binary_sensor_bath_window_open",
            "contact_guard_binary_sensor_kitchen_window_offline",
        }
        assert "Bathroom" in created[0][2]["title"]
        assert "Kitchen" in created[1][2]["title"]
        phone=[x for x in calls if x[:2]==("notify","mobile_app_phone")]
        assert len(phone)==2
        assert all("tag" in x[2]["data"] for x in phone)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_unresolved_incident_does_not_repeat_without_reminders(tmp_path):
    sensor="binary_sensor.window"
    hass,calls,run=await build(tmp_path,[room("Office",[sensor])],[sensor])
    try:
        hass.states.async_set(sensor,"on",timestamp=time()-1080)
        await run()
        assert not calls  # first 10-minute delivery window already passed
        await run()
        assert not calls
        # On startup an overdue contact is surfaced once by the startup pass.
        await run("startup")
        assert any(x[:2]==("persistent_notification","create") for x in calls)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_automatic_clear_and_mobile_push_after_close(tmp_path):
    sensor="binary_sensor.hall_door"
    hass,calls,run=await build(tmp_path,
        [room("Hall",[sensor])],[sensor],
        notify_services="notify.mobile_app_phone")
    try:
        hass.states.async_set(sensor,"on",timestamp=time()-640)
        old=hass.states.get(sensor)
        await run()
        assert any(x[:2]==("persistent_notification","create") for x in calls)
        hass.states.async_set(sensor,"off")
        new=hass.states.get(sensor)
        calls.clear()
        await run("contact_changed",entity_id=sensor,from_state=old,to_state=new)
        assert any(x[:2]==("persistent_notification","dismiss") for x in calls)
        assert any(x[:2]==("notify","mobile_app_phone") and
                   x[2].get("message")=="clear_notification" for x in calls)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_silent_last_seen_is_explicit_opt_in(tmp_path):
    sensor="binary_sensor.patio"
    hass,calls,run=await build(tmp_path,
        [room("Living room",[sensor],last_seen_hours=24)],[sensor])
    try:
        stamp=(datetime.now(timezone.utc)-timedelta(hours=26)).isoformat()
        hass.states.async_set(sensor,"off",{"last_seen":stamp},timestamp=time()-120)
        await run()
        create=[x for x in calls if x[:2]==("persistent_notification","create")]
        assert len(create)==1
        assert create[0][2]["notification_id"].endswith("_silent")
        assert "Living room" in create[0][2]["title"]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_no_last_seen_attribute_never_fabricates_failure(tmp_path):
    sensor="binary_sensor.patio"
    hass,calls,run=await build(tmp_path,
        [room("Living room",[sensor],last_seen_hours=24)],[sensor])
    try:
        hass.states.async_set(sensor,"off",timestamp=time()-99999)
        await run()
        assert not calls
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_offline_can_be_disabled_by_room(tmp_path):
    sensor="binary_sensor.bath"
    hass,calls,run=await build(tmp_path,
        [room("Bathroom",[sensor],monitor_offline=False)],[sensor])
    try:
        hass.states.async_set(sensor,"unavailable",timestamp=time()-2000)
        await run()
        assert not calls
    finally:
        await hass.async_stop()
