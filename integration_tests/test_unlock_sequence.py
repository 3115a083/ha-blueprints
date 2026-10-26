"""Live Home Assistant action-schema and safe one-step execution checks.

No physical devices are controlled; all service effects are mocked.
"""
from pathlib import Path
import asyncio

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, HomeAssistant
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.helpers import config_validation as cv, trigger as trigger_helper
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.util.yaml import load_yaml

PATH = Path(__file__).resolve().parents[1] / (
    "blueprints/automation/unlock_sequence/unlock_sequence.yaml"
)


def substitute(**inputs):
    blueprint = Blueprint(
        load_yaml(str(PATH)), expected_domain="automation",
        schema=BLUEPRINT_SCHEMA
    )
    assert blueprint.validate() is None
    obj = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "unlock_sequence.yaml",
                "input": {
                    "configuration_mode": "simple",
                    "simple_triggers": [
                        {"trigger": "event", "event_type": "unlock_test_press"}
                    ],
                    "simple_repeats": 1,
                    "success_cooldown_seconds": 0,
                    "success_actions": [
                        {"action": "persistent_notification.create",
                         "data": {"title": "Test", "message": "Validated"}}
                    ],
                    **inputs,
                }
            }
        },
    )
    obj.validate()
    return obj.async_substitute()


@pytest.mark.asyncio
async def test_expanded_unlock_actions_validate_with_real_ha(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    try:
        config = substitute()
        actions = await async_validate_actions_config(
            hass,
            cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]]),
        )
        assert actions
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_one_event_can_execute_safe_action_once(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    seen = []

    async def record(call):
        seen.append(dict(call.data))

    hass.services.async_register("persistent_notification", "create", record)
    try:
        config = substitute()
        actions = await async_validate_actions_config(
            hass,
            cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]]),
        )
        script = Script(
            hass, actions, "Unlock sequence test", "automation",
            script_mode="single",
        )
        await script.async_run(
            {"this": {"entity_id": "automation.test_unlock"},
             "trigger": {"id": "0"}},
            Context(),
        )
        await hass.async_block_till_done()
        assert seen == [{"title": "Test", "message": "Validated"}]
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_second_input_advances_only_once(tmp_path):
    """A real event must advance the active wait and execute one safe action."""
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    seen = []

    async def record(call):
        seen.append(dict(call.data))

    hass.services.async_register("persistent_notification", "create", record)
    try:
        config = substitute(simple_repeats=2, debounce_ms=0)
        actions = await async_validate_actions_config(
            hass,
            cv.SCRIPT_SCHEMA([{"variables": config["variables"]}, *config["actions"]]),
        )
        script = Script(
            hass, actions, "Unlock two-press sequence", "automation",
            script_mode="single",
        )
        task = asyncio.create_task(
            script.async_run(
                {"this": {"entity_id": "automation.test_unlock"},
                 "trigger": {"id": "0"}},
                Context(),
            )
        )
        await asyncio.sleep(0.05)
        assert seen == [], "A single input must not unlock a two-input code"
        hass.bus.async_fire("unlock_test_press")
        await asyncio.wait_for(task, timeout=3)
        await hass.async_block_till_done()
        assert seen == [{"title": "Test", "message": "Validated"}]
    finally:
        await hass.async_stop()


async def hardened_environment(tmp_path, **inputs):
    """Real HA scripts; only helper/notification services are simulated."""
    from datetime import datetime, timezone
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    loader.async_setup(hass)
    await trigger_helper.async_setup(hass)
    calls = []
    hass.states.async_set('input_number.failures', '0', {'min': 0, 'max': 100, 'step': 1})
    for name in ('lock', 'window', 'cooldown'):
        hass.states.async_set('input_datetime.' + name, '2000-01-01 00:00:00',
                              {'has_date': True, 'has_time': True})
    async def record(call):
        calls.append((call.domain + '.' + call.service, dict(call.data)))
        entity = call.data.get('entity_id')
        if isinstance(entity, list):
            entity = entity[0]
        if entity and hass.states.get(entity) and hass.states.get(entity).state != 'unavailable':
            attrs = dict(hass.states.get(entity).attributes)
            if call.domain == 'input_number':
                hass.states.async_set(entity, str(call.data['value']), attrs)
            elif call.domain == 'input_datetime':
                value = call.data.get('datetime')
                if 'timestamp' in call.data:
                    value = datetime.fromtimestamp(float(call.data['timestamp']), timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                hass.states.async_set(entity, value, attrs)
    for domain, service in [('persistent_notification', 'create'), ('input_number', 'set_value'), ('input_datetime', 'set_datetime')]:
        hass.services.async_register(domain, service, record)
    config = substitute(**inputs)
    actions = await async_validate_actions_config(hass, cv.SCRIPT_SCHEMA([
        {'variables': config['variables']}, *config['actions']]))
    script = Script(hass, actions, 'Unlock hardening regression', 'automation', script_mode='single',
                    logger=__import__('logging').getLogger(__name__))
    async def run(identifier='0'):
        await script.async_run({'this': {'entity_id': 'automation.test_unlock'},
                                'trigger': {'id': identifier}}, Context())
    return hass, calls, script, run


def protected_inputs(**extra):
    return dict(protection_enabled=True, failure_count='input_number.failures',
                failure_lock_until='input_datetime.lock', **extra)


@pytest.mark.asyncio
@pytest.mark.parametrize('helper', ['input_number.failures', 'input_datetime.lock', 'input_datetime.cooldown'])
async def test_storage_disappearing_during_wait_aborts_without_success(tmp_path, helper):
    hass, calls, script, run = await hardened_environment(tmp_path, **protected_inputs(
        simple_repeats=2, debounce_ms=0, success_cooldown_seconds=30,
        success_cooldown_until='input_datetime.cooldown', reset_failures_on='confirmed'))
    try:
        task = asyncio.create_task(run())
        await asyncio.sleep(0.05)
        hass.states.async_set(helper, 'unavailable')
        hass.bus.async_fire('unlock_test_press')
        await asyncio.wait_for(task, 2)
        assert not any(c[0] == 'persistent_notification.create' for c in calls)
    finally:
        await script.async_stop()
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('count,maximum,step', [('0', 1, 1), ('0.5', 100, 1), ('nan', 100, 1), ('0', 100, .5)])
async def test_invalid_counter_configuration_fails_closed(tmp_path, count, maximum, step):
    hass, calls, script, run = await hardened_environment(tmp_path, **protected_inputs())
    try:
        hass.states.async_set('input_number.failures', count, {'min': 0, 'max': maximum, 'step': step})
        await run()
        assert calls == []
    finally:
        await script.async_stop()
        await hass.async_stop()


@pytest.mark.asyncio
async def test_ambiguous_event_bank_cannot_run_success(tmp_path):
    hass, calls, script, run = await hardened_environment(tmp_path,
        configuration_mode='advanced', simple_triggers=[], advanced_code='A', advanced_triggers=[
            {'trigger': 'event', 'event_type': 'press', 'id': 'A'},
            {'trigger': 'event', 'event_type': 'press', 'event_data': {'button': 'one'}, 'id': 'B'}])
    try:
        await run('A')
        assert calls == []
    finally:
        await script.async_stop()
        await hass.async_stop()


@pytest.mark.asyncio
async def test_ignored_wrong_input_does_not_extend_gap(tmp_path):
    hass, calls, script, run = await hardened_environment(tmp_path,
        configuration_mode='advanced', simple_triggers=[], advanced_code='AB',
        advanced_triggers=[{'trigger': 'event', 'event_type': 'press_a', 'id': 'A'},
                           {'trigger': 'event', 'event_type': 'press_b', 'id': 'B'}],
        total_timeout=0, step_timeout=1, debounce_ms=0, wrong_input_policy='ignore',
        failure_actions=[{'action': 'persistent_notification.create', 'data': {'message': 'failed'}}])
    try:
        task = asyncio.create_task(run('A'))
        await asyncio.sleep(.65)
        hass.bus.async_fire('press_a')
        await asyncio.wait_for(task, .65)
        assert [c[1].get('message') for c in calls] == ['failed']
    finally:
        await script.async_stop()
        await hass.async_stop()


@pytest.mark.asyncio
async def test_lock_threshold_persists_before_failing_notification(tmp_path):
    from homeassistant.exceptions import HomeAssistantError
    hass, calls, script, run = await hardened_environment(tmp_path, **protected_inputs(
        simple_repeats=2, step_timeout=1, max_failures=1,
        lock_started_actions=[{'action': 'persistent_notification.create', 'data': {'message': 'lock'}}]))
    async def fail(call):
        raise HomeAssistantError('Notification failed')
    hass.services.async_register('persistent_notification', 'create', fail)
    try:
        try:
            await run()
        except HomeAssistantError:
            pass  # Some HA callers propagate service errors; persistence is required either way.
        assert float(hass.states.get('input_number.failures').state) == 1
        assert hass.states.get('input_datetime.lock').state > '2000-01-01 00:00:00'
        # A fresh valid one-step invocation is still blocked by the deadline.
        await run()
        assert len([c for c in calls if c[0] == 'input_number.set_value']) == 1
    finally:
        await script.async_stop()
        await hass.async_stop()


@pytest.mark.asyncio
async def test_confirmation_ignores_extra_sequence_inputs(tmp_path):
    hass, calls, script, run = await hardened_environment(tmp_path,
        verify_enabled=True, verify_timeout=1,
        verify_conditions=[{'condition': 'state', 'entity_id': 'binary_sensor.result', 'state': 'on'}],
        verify_triggers=[{'trigger': 'state', 'entity_id': 'binary_sensor.result', 'to': 'on'}],
        error_actions=[{'action': 'persistent_notification.create', 'data': {'message': 'unconfirmed'}}])
    try:
        hass.states.async_set('binary_sensor.result', 'off')
        task = asyncio.create_task(run())
        await asyncio.sleep(.05)
        await run()  # mode: single drops this invocation while confirming.
        hass.bus.async_fire('unlock_test_press')
        await asyncio.wait_for(task, 2)
        assert [c[1].get('message') for c in calls] == ['Validated', 'unconfirmed']
    finally:
        await script.async_stop()
        await hass.async_stop()
