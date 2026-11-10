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
    hass.services.async_register("notify","send_message",receive)
    hass.services.async_register("system_log","write",receive)
    hass.services.async_register("test","record",receive)
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
        # A previously silent device is surfaced on restart/reload even if
        # its exact first one-minute alert window was missed during downtime.
        stamp=(datetime.now(timezone.utc)-timedelta(hours=26)).isoformat()
        hass.states.async_set(sensor,"off",{"last_seen":stamp},timestamp=time()-120)
        await run("startup")
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


@pytest.mark.asyncio
async def test_notify_entity_picker_sends_without_legacy_mobile_action(tmp_path):
    sensor="binary_sensor.kitchen_window"
    hass,calls,run=await build(
        tmp_path,[room("Kitchen",[sensor])],[sensor],
        notify_entities=["notify.kitchen_phone"],notify_services="",
        persistent_enabled=False
    )
    try:
        hass.states.async_set(sensor,"on",timestamp=time()-630)
        await run()
        selected=[x for x in calls if x[:2]==("notify","send_message")]
        assert len(selected)==1
        assert "Kitchen" in selected[0][2]["title"]
        assert not any(x[:2]==("notify","mobile_app_phone") for x in calls)
        assert not any(x[0]=="persistent_notification" for x in calls)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_open_and_health_conditions_are_independent(tmp_path):
    window="binary_sensor.kitchen_window"
    door="binary_sensor.hall_door"
    hass,calls,run=await build(
        tmp_path,[
            room("Kitchen",[window]),
            room("Hall",[door]),
        ],
        [window,door],
        notify_entities=["notify.kitchen_phone"],persistent_enabled=False,
        open_alert_conditions=[{
            "condition":"numeric_state",
            "entity_id":"sensor.outdoor_temperature",
            "below":17,
        }],
        health_alert_conditions=[{
            "condition":"state",
            "entity_id":"person.someone",
            "state":"not_home",
        }],
    )
    try:
        hass.states.async_set(window,"on",timestamp=time()-630)
        hass.states.async_set(door,"unavailable",timestamp=time()-1230)

        # Outside too warm for the open-contact warning; person away
        # is enough to allow the independent offline warning.
        hass.states.async_set("sensor.outdoor_temperature","19")
        hass.states.async_set("person.someone","not_home")
        await run()
        warnings=[x for x in calls if x[:2]==("notify","send_message")]
        assert len(warnings)==1
        assert "Hall" in warnings[0][2]["title"]
        calls.clear()

        # Reverse which condition passes, keeping both contact issues due.
        hass.states.async_set("sensor.outdoor_temperature","16.5")
        hass.states.async_set("person.someone","home")
        await run()
        warnings=[x for x in calls if x[:2]==("notify","send_message")]
        assert len(warnings)==1
        assert "Kitchen" in warnings[0][2]["title"]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_legacy_shared_conditions_still_gate_both_alert_types(tmp_path):
    window="binary_sensor.kitchen_window"
    door="binary_sensor.hall_door"
    hass,calls,run=await build(
        tmp_path,[room("Kitchen",[window]),room("Hall",[door])],[window,door],
        notify_entities=["notify.kitchen_phone"],persistent_enabled=False,
        notify_conditions=[{
            "condition":"state",
            "entity_id":"input_boolean.alerts_enabled",
            "state":"on",
        }],
    )
    try:
        hass.states.async_set(window,"on",timestamp=time()-630)
        hass.states.async_set(door,"unavailable",timestamp=time()-1230)
        hass.states.async_set("input_boolean.alerts_enabled","off")
        await run()
        assert not calls
        hass.states.async_set("input_boolean.alerts_enabled","on")
        await run()
        assert len([x for x in calls if x[:2]==("notify","send_message")])==2
    finally:
        await hass.async_stop()



@pytest.mark.asyncio
async def test_custom_message_and_actions_run_after_notifications(tmp_path):
    sensor="binary_sensor.study_window"
    hass,calls,run=await build(
        tmp_path,[room("Study",[sensor])],[sensor],
        notify_entities=["notify.study_phone"],
        alert_title_template="{{ room_name }}: {{ alert_type }} warning",
        alert_message_template=(
            "{{ contact_label }} ({{ contact_id }}) in {{ room_name }} "
            "has been {{ alert_type }} for {{ elapsed_minutes }} minutes."
        ),
        on_alert_actions=[{
            "action":"test.record",
            "data":{
                "message":"{{ alert_message }}",
                "contact":"{{ contact_id }}",
            },
        }],
    )
    try:
        hass.states.async_set(sensor,"on",{"friendly_name":"Study window"},timestamp=time()-630)
        await run()
        assert [(domain,service) for domain,service,_ in calls]==[
            ("persistent_notification","create"),
            ("notify","send_message"),
            ("test","record"),
        ]
        title=calls[0][2]["title"]
        message=calls[0][2]["message"]
        assert title=="Study: open warning"
        assert "Study window (binary_sensor.study_window) in Study" in message
        assert calls[1][2]["message"]==message
        assert calls[2][2]["message"]==message
        assert calls[2][2]["contact"]==sensor
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_specific_reminders_at_five_and_fifteen_minutes(tmp_path):
    sensor="binary_sensor.hall_window"
    hass,calls,run=await build(
        tmp_path,[room("Hall",[sensor])],[sensor],
        reminder_offsets_minutes="5,15",reminder_minutes=2,
        on_alert_actions=[{"action":"test.record","data":{"alert":"{{ alert_type }}"}}],
    )
    try:
        for elapsed,expected in (
            (630,True),      # first warning at 10 min
            (735,False),     # legacy 2-minute period suppressed
            (930,True),      # first reminder at 15 min of open state
            (990,False),     # no second minute of the same reminder
            (1230,False),
            (1530,True),     # second reminder at 25 min of open state
            (1590,False),
            (1830,False),    # no unrequested repeat
        ):
            hass.states.async_set(sensor,"off")
            hass.states.async_set(sensor,"on",timestamp=time()-elapsed)
            calls.clear()
            await run()
            creates=[x for x in calls if x[:2]==("persistent_notification","create")]
            actions=[x for x in calls if x[:2]==("test","record")]
            assert bool(creates)==expected,(elapsed,calls)
            assert len(actions)==len(creates),(elapsed,calls)
            if creates:
                assert creates[0][2]["notification_id"]=="contact_guard_binary_sensor_hall_window_open"
    finally:
        await hass.async_stop()



@pytest.mark.asyncio
async def test_warning_and_reminder_actions_are_separate(tmp_path):
    sensor="binary_sensor.study_window"
    hass,calls,run=await build(
        tmp_path,[room("Study",[sensor])],[sensor],
        reminder_offsets_minutes="5,15",
        on_alert_actions=[{"action":"test.record","data":{"phase":"initial"}}],
        on_reminder_actions=[{"action":"test.record","data":{"phase":"reminder"}}],
    )
    try:
        for age,phase in ((630,"initial"),(930,"reminder"),(1530,"reminder")):
            hass.states.async_set(sensor,"off")
            hass.states.async_set(sensor,"on",timestamp=time()-age)
            calls.clear()
            await run()
            assert calls[-1][:2]==("test","record"),calls
            phases=[x[2]["phase"] for x in calls if x[:2]==("test","record")]
            assert phases==[phase],calls
        calls.clear()
        hass.states.async_set(sensor,"off")
        hass.states.async_set(sensor,"on",timestamp=time()-870)
        await run()
        assert not [x for x in calls if x[:2]==("test","record")]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_two_contacts_share_one_persistent_and_mobile_tag(tmp_path):
    first="binary_sensor.kitchen_window"
    second="binary_sensor.bath_window"
    hass,calls,run=await build(
        tmp_path,[room("Kitchen",[first]),room("Bathroom",[second])],
        [first,second],notify_services="notify.mobile_app_phone",
    )
    try:
        hass.states.async_set(first,"on",{"friendly_name":"Kitchen window"},timestamp=time()-630)
        hass.states.async_set(second,"off",{"friendly_name":"Bathroom window"})
        await run()
        first_persistent=[x for x in calls if x[:2]==("persistent_notification","create")]
        first_mobile=[x for x in calls if x[:2]==("notify","mobile_app_phone")
                      and x[2].get("message")!="clear_notification"]
        assert len(first_persistent)==len(first_mobile)==1
        tag=first_persistent[0][2]["notification_id"]
        assert tag.endswith("_open")
        assert first_mobile[0][2]["data"]["tag"]==tag
        calls.clear()

        # A second sensor opens later and reaches its own initial deadline.
        hass.states.async_set(first,"on",{"friendly_name":"Kitchen window"},timestamp=time()-900)
        hass.states.async_set(second,"on",{"friendly_name":"Bathroom window"},timestamp=time()-630)
        await run()
        updated=[x for x in calls if x[:2]==("persistent_notification","create")]
        updated_mobile=[x for x in calls if x[:2]==("notify","mobile_app_phone")
                        and x[2].get("message")!="clear_notification"]
        assert len(updated)==len(updated_mobile)==1,calls
        assert updated[0][2]["notification_id"]==tag
        assert updated_mobile[0][2]["data"]["tag"]==tag
        assert "Kitchen window" in updated[0][2]["message"]
        assert "Bathroom window" in updated[0][2]["message"]
        assert "Kitchen window" in updated_mobile[0][2]["message"]

        # Closing the first window retains the bundled tag with the second.
        old=hass.states.get(first)
        hass.states.async_set(first,"off")
        new=hass.states.get(first)
        calls.clear()
        await run("contact_changed",entity_id=first,from_state=old,to_state=new)
        revisions=[x for x in calls if x[:2]==("persistent_notification","create")]
        assert len(revisions)==1,calls
        assert revisions[0][2]["notification_id"]==tag
        assert "Bathroom window" in revisions[0][2]["message"]
        assert "Kitchen window" not in revisions[0][2]["message"]
        assert not [x for x in calls if x[:2]==("persistent_notification","dismiss") and
                    x[2]["notification_id"]==tag]
        calls.clear()

        # Last recovery dismisses exactly the shared bundle.
        old=hass.states.get(second)
        hass.states.async_set(second,"off")
        new=hass.states.get(second)
        await run("contact_changed",entity_id=second,from_state=old,to_state=new)
        assert len([x for x in calls if x[:2]==("persistent_notification","dismiss")
                    and x[2]["notification_id"]==tag])==1,calls
        assert any(x[:2]==("notify","mobile_app_phone") and
                   x[2].get("message")=="clear_notification" and
                   x[2].get("data",{}).get("tag")==tag for x in calls)
    finally:
        await hass.async_stop()
