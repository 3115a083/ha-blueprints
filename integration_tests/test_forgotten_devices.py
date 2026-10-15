"""Real HA schema, template and action tests. No physical device calls."""
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant import loader
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.config_entries import ConfigEntries
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.helpers import config_validation as cv, template, device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util, yaml as yaml_util

PATH=Path(__file__).resolve().parents[1]/'blueprints/automation/forgotten_devices/forgotten_devices.yaml'


def configuration(inputs):
    blueprint=Blueprint(yaml_util.load_yaml(str(PATH)),expected_domain='automation',schema=BLUEPRINT_SCHEMA)
    assert blueprint.validate() is None
    instance=BlueprintInputs(blueprint,{'use_blueprint':{'path':'forgotten_devices.yaml','input':inputs}})
    instance.validate()
    return instance.async_substitute()


async def environment(tmp_path, entries=None, **inputs):
    hass=HomeAssistant(str(tmp_path))
    hass.config_entries=ConfigEntries(hass,{})
    loader.async_setup(hass)
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    now=dt_util.utcnow()
    calls=[]
    entries=entries if entries is not None else [{'entity':'light.test','last_attempt':'input_datetime.test','rules':[{'entity':'binary_sensor.room','state':'off'}]}]
    hass.states.async_set('binary_sensor.room','off')
    for item in entries:
        target=item['entity']
        domain=target.split('.')[0]
        status={'climate':'heat','media_player':'playing'}.get(domain,'on')
        attrs={'hvac_modes':['off','heat']} if domain=='climate' else {}
        # Explicit past state time allows fast real-template tests without clock sleeps.
        hass.states._states[target]=State(target,status,attrs,last_changed=now-timedelta(hours=1))
        helper=item.get('last_attempt','input_datetime.test')
        hass.states.async_set(helper,'2020-01-01 00:00:00',{'has_date':True,'has_time':True,'timestamp':1577836800})
    async def record(call):
        data=dict(call.data)
        if isinstance(data.get('entity_id'),list):
            assert len(data['entity_id'])==1
            data['entity_id']=data['entity_id'][0]
        calls.append((call.domain+'.'+call.service,data))
        if call.domain=='input_datetime':
            helper=data['entity_id']
            hass.states.async_set(helper,'2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
    for domain,services in {'input_datetime':['set_datetime'],'light':['turn_off'],'switch':['turn_off'], 'fan':['turn_off'],'humidifier':['turn_off'],'input_boolean':['turn_off'],'climate':['set_hvac_mode'],'media_player':['media_stop','media_pause','turn_off'],'persistent_notification':['create']}.items():
        for service in services:
            hass.services.async_register(domain,service,record)
    config=configuration({'device_entries':entries,'preview_only':False,**inputs})
    variables=config['variables']
    actions=await async_validate_actions_config(hass,cv.SCRIPT_SCHEMA([{'variables':variables},*config['actions']]))
    script=Script(hass,actions,'Forgotten devices test','automation',script_mode='single')
    async def run():
        await script.async_run({'this':{'entity_id':'automation.energy'}},Context())
        await hass.async_block_till_done()
    return hass,calls,run,entries,now


@pytest.mark.asyncio
async def test_real_schema_and_selectors(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        await run()
        assert [x[0] for x in calls]==['input_datetime.set_datetime','light.turn_off']
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('domain,expected',[('light','light.turn_off'),('switch','switch.turn_off'),('climate','climate.set_hvac_mode'),('media_player','media_player.media_stop'),('fan','fan.turn_off'),('humidifier','humidifier.turn_off'),('input_boolean','input_boolean.turn_off')])
async def test_domain_dispatch(tmp_path,domain,expected):
    hass,calls,run,_,_=await environment(tmp_path,[{'entity':domain+'.test','last_attempt':'input_datetime.test','allow_time_only':True}])
    try:
        await run()
        assert calls[-1][0]==expected
        assert calls[-1][1]['entity_id']==domain+'.test'
        if domain=='climate': assert calls[-1][1]['hvac_mode']=='off'
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,global_ok,local_ok,expected',[
    ('require',True,True,True),('require',True,False,False),('require',False,True,False),
    ('alternative',True,False,True),('alternative',False,True,True),('alternative',False,False,False),
    ('ignore',False,True,True),('ignore',True,False,False)])
async def test_global_modes(tmp_path,mode,global_ok,local_ok,expected):
    conditions=[{'condition':'template','value_template':'{{ '+str(global_ok).lower()+' }}'}]
    entries=[{'entity':'light.test','last_attempt':'input_datetime.test','global_mode':mode,'rules':[{'entity':'binary_sensor.room','state':'off'}]}]
    hass,calls,run,_,_=await environment(tmp_path,entries,global_conditions=conditions)
    try:
        hass.states.async_set('binary_sensor.room','off' if local_ok else 'on')
        await run()
        assert any(c[0]=='light.turn_off' for c in calls)==expected
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('override,global_minutes,expected',[(15,120,True),(120,15,False),(None,120,False),(None,15,True)])
async def test_individual_runtime_wins(tmp_path,override,global_minutes,expected):
    entry={'entity':'light.test','last_attempt':'input_datetime.test','allow_time_only':True}
    if override is not None: entry['max_minutes']=override
    hass,calls,run,_,_=await environment(tmp_path,[entry],global_minutes=global_minutes)
    try:
        await run()
        assert any(c[0]=='light.turn_off' for c in calls)==expected
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_once_per_state_period_even_failed_service(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    from homeassistant.exceptions import HomeAssistantError
    async def fail(call):
        calls.append(('light.turn_off',{}))
        raise HomeAssistantError('Simulated offline device')
    hass.services.async_register('light','turn_off',fail)
    try:
        await run()
        await run()
        assert len([c for c in calls if c[0]=='light.turn_off'])==1
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('condition_state',['on','unknown','unavailable'])
async def test_local_condition_failure_blocks(tmp_path,condition_state):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        hass.states.async_set('binary_sensor.room',condition_state)
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_preview_does_not_send_or_consume_attempt(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path,preview_only=True)
    try:
        await run()
        assert [c[0] for c in calls]==['persistent_notification.create']
        assert hass.states.get('input_datetime.test').attributes['timestamp']==1577836800
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_empty_conditions_are_not_an_or_bypass(tmp_path):
    entry={'entity':'light.test','last_attempt':'input_datetime.test','global_mode':'alternative','rules':[{'entity':'binary_sensor.room','state':'on'}]}
    hass,calls,run,_,_=await environment(tmp_path,[entry])
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_empty_entries_no_commands(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path,[])
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_duplicates_skipped_without_affecting_other_entries(tmp_path):
    entries=[{'entity':'light.test','last_attempt':'input_datetime.a','allow_time_only':True},
             {'entity':'light.test','last_attempt':'input_datetime.b','allow_time_only':True},
             {'entity':'switch.other','last_attempt':'input_datetime.c','allow_time_only':True}]
    hass,calls,run,_,_=await environment(tmp_path,entries)
    try:
        await run()
        assert [c[0] for c in calls]==['input_datetime.set_datetime','switch.turn_off']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_helper_write_failure_skips_only_affected_target(tmp_path):
    entries=[{'entity':'light.test','last_attempt':'input_datetime.a','allow_time_only':True},
             {'entity':'switch.other','last_attempt':'input_datetime.b','allow_time_only':True}]
    hass,calls,run,_,_=await environment(tmp_path,entries)
    from homeassistant.exceptions import HomeAssistantError
    async def update(call):
        entity_id=call.data['entity_id']
        if isinstance(entity_id,list): entity_id=entity_id[0]
        if entity_id=='input_datetime.a': raise HomeAssistantError('Simulated write failure')
        hass.states.async_set('input_datetime.b','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
    hass.services.async_register('input_datetime','set_datetime',update)
    try:
        await run()
        assert [c[0] for c in calls]==['switch.turn_off']
    finally: await hass.async_stop()

@pytest.mark.asyncio
@pytest.mark.parametrize('bad_state',['off','unknown','unavailable'])
async def test_inactive_or_unavailable_target_never_touched(tmp_path,bad_state):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        hass.states.async_set('light.test',bad_state)
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_unavailable_helper_blocks(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        hass.states.async_set('input_datetime.test','unavailable')
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('match,source_state,source_age,expected',[
    ('state','off',5,False),('state','off',20,True),('away','work',20,True),
    ('away','home',20,False),('away','unknown',20,False),('away','unavailable',20,False)])
async def test_stable_state_and_away_rules(tmp_path,match,source_state,source_age,expected):
    source='person.test' if match=='away' else 'binary_sensor.room'
    entries=[{'entity':'light.test','last_attempt':'input_datetime.test','rules':[{'entity':source,'match':match,'state':'off','for_minutes':10}]}]
    hass,calls,run,_,now=await environment(tmp_path,entries)
    try:
        hass.states._states[source]=State(source,source_state,last_changed=now-timedelta(minutes=source_age))
        await run()
        assert any(c[0]=='light.turn_off' for c in calls)==expected
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,expected',[('all',False),('any',True)])
async def test_local_all_any(tmp_path,mode,expected):
    entries=[{'entity':'light.test','last_attempt':'input_datetime.test','local_match':mode,'rules':[{'entity':'binary_sensor.room','state':'off'},{'entity':'binary_sensor.other','state':'off'}]}]
    hass,calls,run,_,_=await environment(tmp_path,entries)
    try:
        hass.states.async_set('binary_sensor.other','on')
        await run()
        assert any(c[0]=='light.turn_off' for c in calls)==expected
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_conditions_can_become_true_after_runtime_without_consuming_attempt(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        hass.states.async_set('binary_sensor.room','on')
        await run()
        assert calls==[]
        hass.states.async_set('binary_sensor.room','off')
        await run()
        assert calls[-1][0]=='light.turn_off'
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_always_required_safety_blocks_or_and_ignore(tmp_path):
    for mode in ('alternative','ignore'):
        entries=[{'entity':'light.test','last_attempt':'input_datetime.test','global_mode':mode,'allow_time_only':True}]
        child=tmp_path/mode
        child.mkdir()
        hass,calls,run,_,_=await environment(child,entries,global_conditions=[{'condition':'template','value_template':'{{ true }}'}],safety_conditions=[{'condition':'template','value_template':'{{ false }}'}])
        try:
            await run()
            assert calls==[]
        finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_no_conditions_requires_explicit_time_only(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path,[{'entity':'light.test','last_attempt':'input_datetime.test'}])
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_attribute_update_does_not_reset_runtime(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        hass.states.async_set('light.test','on',{'brightness':20})
        await run()
        assert calls[-1][0]=='light.turn_off'
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_restart_or_new_activation_gets_full_runtime(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        hass.states.async_set('light.test','off')
        hass.states.async_set('light.test','on')
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_target_reactivated_during_helper_write_not_switched_off(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        hass.states.async_set('light.test','off')
        hass.states.async_set('light.test','on')
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('action',['media_pause','turn_off'])
async def test_media_action_choice(tmp_path,action):
    hass,calls,run,_,_=await environment(tmp_path,[{'entity':'media_player.test','last_attempt':'input_datetime.test','allow_time_only':True,'media_action':action}])
    try:
        await run()
        assert calls[-1][0]=='media_player.'+action
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_duplicate_helpers_block_both_devices(tmp_path):
    entries=[{'entity':'light.test','last_attempt':'input_datetime.shared','allow_time_only':True},
             {'entity':'switch.other','last_attempt':'input_datetime.shared','allow_time_only':True}]
    hass,calls,run,_,_=await environment(tmp_path,entries)
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_nested_selector_input_validation(tmp_path):
    from homeassistant.helpers.selector import selector
    blueprint=Blueprint(yaml_util.load_yaml(str(PATH)),expected_domain='automation',schema=BLUEPRINT_SCHEMA)
    select=selector(blueprint.inputs['device_entries']['selector'])
    # Blueprint schema has instantiated real Selector objects, including nested fields.
    entries=[{'entity':'light.test','last_attempt':'input_datetime.test','rules':[{'entity':'binary_sensor.room','state':'off','for_minutes':10}]}]
    assert select(entries)==entries
    import probatio
    with pytest.raises(probatio.Invalid):
        select([{'entity':'light.test'}])

@pytest.mark.asyncio
async def test_unsupported_domain_rejected_at_execution(tmp_path):
    # Entity selector domain filters constrain the picker, not backend input data.
    hass,calls,run,_,_=await environment(tmp_path,[{'entity':'lock.test','last_attempt':'input_datetime.test','allow_time_only':True}])
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_one_failed_target_does_not_block_next(tmp_path):
    entries=[{'entity':'light.test','last_attempt':'input_datetime.a','allow_time_only':True},
             {'entity':'switch.other','last_attempt':'input_datetime.b','allow_time_only':True}]
    hass,calls,run,_,_=await environment(tmp_path,entries)
    from homeassistant.exceptions import HomeAssistantError
    async def fail(call): raise HomeAssistantError('Simulated device failure')
    hass.services.async_register('light','turn_off',fail)
    try:
        await run()
        assert calls[-1][0]=='switch.turn_off'
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_rules_rechecked_after_marker_write(tmp_path):
    hass,calls,run,_,_=await environment(tmp_path)
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        hass.states.async_set('binary_sensor.room','on')
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_many_targets_independent(tmp_path):
    entries=[{'entity':f'light.test_{i}','last_attempt':f'input_datetime.test_{i}','allow_time_only':True,'max_minutes':15 if i%2==0 else 120} for i in range(30)]
    hass,calls,run,_,_=await environment(tmp_path,entries)
    try:
        await run()
        targets=[c[1]['entity_id'] for c in calls if c[0]=='light.turn_off']
        assert targets==[f'light.test_{i}' for i in range(0,30,2)]
    finally: await hass.async_stop()

@pytest.mark.asyncio
async def test_complete_automation_configuration(tmp_path):
    from homeassistant.components.automation.config import async_validate_config_item
    from homeassistant.helpers import trigger
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        await trigger.async_setup(hass)
        validated=await async_validate_config_item(hass,'automation',configuration({}))
        assert validated['triggers'][0]['platform']=='time_pattern'
        assert validated['mode']=='single'
    finally: await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('elapsed,limit,expected',[(60,60,True),(60,120,False),(10,10,True)])
async def test_runtime_across_dst_and_midnight(tmp_path,elapsed,limit,expected):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    hass,calls,run,_,_=await environment(tmp_path)
    try:
        if elapsed==60:
            zone=ZoneInfo('Europe/Berlin')
            start=datetime(2026,10,25,2,30,tzinfo=zone,fold=0)
            finish=datetime(2026,10,25,2,30,tzinfo=zone,fold=1)
        else:
            start=datetime(2026,10,14,23,55,tzinfo=timezone.utc)
            finish=datetime(2026,10,15,0,5,tzinfo=timezone.utc)
        hass.states._states['light.test']=State('light.test','on',last_changed=start.astimezone(timezone.utc))
        raw=yaml_util.load_yaml(str(PATH))
        sequence=next(a['repeat']['sequence'] for a in raw['actions'] if 'repeat' in a)
        block=next(a['variables']['runtime_due'] for a in sequence if 'runtime_due' in a.get('variables',{}))
        result=template.Template(block,hass).async_render({'target_entity':'light.test','attempt_helper':'input_datetime.test','runtime_minutes':limit,'now':lambda:finish})
        assert result is expected
    finally: await hass.async_stop()
