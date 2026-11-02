"""Real Home Assistant action validation and guarded media service behavior.

No physical speakers or Music Assistant instance are accessed. Services are mocked.
"""
from pathlib import Path

import pytest

from homeassistant import loader
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, Event, HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.util.yaml import load_yaml

PATH = Path(__file__).resolve().parents[1] / (
    "blueprints/automation/play_when_idle/play_when_idle.yaml"
)
LIVING = "media_player.ma_living"
KITCHEN = "media_player.ma_kitchen"


def expanded(**overrides):
    source = Blueprint(load_yaml(str(PATH)), expected_domain="automation",
                       schema=BLUEPRINT_SCHEMA)
    assert source.validate() is None
    config = BlueprintInputs(source, {"use_blueprint": {
        "path": "play_when_idle.yaml",
        "input": {"monitored_players": [LIVING, KITCHEN],
                  "ma_radio_id": "Test Radio", "cooldown_seconds": 0, **overrides}
    }})
    config.validate()
    return config.async_substitute()


async def env(tmp_path, *, living_state="idle", kitchen_state="idle",
              ma_items=0, **inputs):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    calls = []
    for entity, state in ((LIVING, living_state), (KITCHEN, kitchen_state)):
        hass.states.async_set(entity, state, {"mass_player_type": "player"})

    async def record(call):
        calls.append((f"{call.domain}.{call.service}", dict(call.data)))

    async def get_queue(call):
        return {call.data.get("entity_id", LIVING): {"items": ma_items}}

    hass.services.async_register("music_assistant", "play_media", record)
    hass.services.async_register("music_assistant", "get_queue", get_queue,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register("media_player", "play_media", record)
    hass.services.async_register("persistent_notification", "create", record)

    config = expanded(**inputs)
    actions = await async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]])
    )
    script = Script(hass, actions, "Play when idle real HA test", "automation",
                    script_mode="single")

    async def run(entity_id=LIVING, *, service_id="ha_media_play"):
        event = Event("call_service", {"service_data": {"entity_id": entity_id}})
        await script.async_run({"trigger": {"id": service_id, "event": event},
                                "this": {"entity_id": "automation.play_when_idle"}},
                               Context())
        await hass.async_block_till_done()

    return hass, calls, run


@pytest.mark.asyncio
async def test_ha_radio_play_on_idle_and_only_requested_speaker(tmp_path):
    hass, calls, run = await env(tmp_path)
    try:
        await run(KITCHEN)
        assert calls == [("music_assistant.play_media", {
            "entity_id": KITCHEN, "media_id": "Test Radio",
            "media_type": "radio", "enqueue": "replace"
        })]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["playing", "paused", "buffering", "off", "unavailable"])
async def test_real_ha_guard_does_not_interrupt_other_states(tmp_path, state):
    hass, calls, run = await env(tmp_path, living_state=state)
    try:
        await run()
        assert calls == []
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_strict_ma_queue_requires_zero_items(tmp_path):
    hass, calls, run = await env(tmp_path, ma_items=2, idle_check="ma_empty")
    try:
        await run()
        assert [call for call in calls if call[0] == "music_assistant.play_media"] == []
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_standard_media_and_custom_action(tmp_path):
    hass, calls, run = await env(tmp_path, fallback_mode="standard_media",
                                 media_content_id="https://example.org/radio.mp3")
    try:
        await run()
        assert calls == [("media_player.play_media", {
            "entity_id": LIVING,
            "media_content_id": "https://example.org/radio.mp3",
            "media_content_type": "music"
        })]
    finally:
        await hass.async_stop()

    hass, calls, run = await env(tmp_path, fallback_mode="custom",
        custom_actions=[{"action": "persistent_notification.create", "data": {
            "title": "Pressed", "message": "{{ play_target_player }}"}}])
    try:
        await run()
        assert calls == [("persistent_notification.create", {
            "title": "Pressed", "message": LIVING
        })]
    finally:
        await hass.async_stop()
