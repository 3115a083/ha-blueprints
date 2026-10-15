"""Real HA expansion, area selection, exclusions and batch safety tests."""
from datetime import timedelta

import pytest
from homeassistant.core import State
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.exceptions import HomeAssistantError

from integration_tests.test_forgotten_devices import environment


def state(hass,now,entity,status='on',age=60,**attrs):
    hass.states._states[entity]=State(entity,status,attrs,last_changed=now-timedelta(minutes=age))


def shutoff_targets(calls):
    return [data['entity_id'] for action,data in calls if action not in ('input_datetime.set_datetime','persistent_notification.create')]


async def group_environment(tmp_path,**extra):
    entry={'entity':'light.room_group','last_attempt':'input_datetime.test','allow_time_only':True,**extra}
    hass,calls,run,_,now=await environment(tmp_path,[entry])
    state(hass,now,'light.room_group',entity_id=['light.a','light.b','light.excluded'])
    for entity in ('light.a','light.b','light.excluded'):
        state(hass,now,entity)
    return hass,calls,run,now


@pytest.mark.asyncio
async def test_light_group_with_exception_never_receives_group_service(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    try:
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
        assert [action for action,_ in calls].count('input_datetime.set_datetime')==1
        assert 'light.room_group' not in shutoff_targets(calls)
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_nested_groups_and_excluded_subgroup(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.exclude_group'])
    try:
        state(hass,now,'light.room_group',entity_id=['group.nested','light.b','light.exclude_group'])
        state(hass,now,'group.nested',entity_id=['light.a','light.b'])
        state(hass,now,'light.exclude_group',entity_id=['light.excluded','light.nightlight'])
        state(hass,now,'light.nightlight')
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_all_members_excluded_does_not_consume_attempt(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.room_group'])
    try:
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_explicit_entities_need_one_entry_and_helper(tmp_path):
    hass,calls,run,_,now=await environment(tmp_path,[{'name':'Living room','entities':['light.a','light.b','light.a'],'exclude_entities':['light.b'],'last_attempt':'input_datetime.test','allow_time_only':True}])
    try:
        state(hass,now,'light.a')
        state(hass,now,'light.b')
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


async def assign_area(hass,entity,area):
    domain,object_id=entity.split('.')
    reg=er.async_get(hass)
    saved=hass.states._states.pop(entity,None)
    try:
        created=reg.async_get_or_create(domain,'test',entity,suggested_object_id=object_id)
    finally:
        if saved is not None: hass.states._states[entity]=saved
    assert created.entity_id==entity
    reg.async_update_entity(entity,area_id=area.id)


@pytest.mark.asyncio
async def test_room_lights_except_one_without_group_helper(tmp_path):
    hass,calls,run,_,now=await environment(tmp_path,[{'name':'Living room','areas':['living_room'],'exclude_entities':['light.excluded'],'last_attempt':'input_datetime.test','allow_time_only':True}])
    try:
        await ar.async_load(hass)
        living=ar.async_get(hass).async_create('Living room')
        assert living.id=='living_room'
        kitchen=ar.async_get(hass).async_create('Kitchen')
        for entity,area in [('light.a',living),('light.b',living),('light.excluded',living),('switch.fridge',living),('light.kitchen',kitchen)]:
            state(hass,now,entity)
            await assign_area(hass,entity,area)
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_room_domain_opt_in_and_cross_room_group_filter(tmp_path):
    hass,calls,run,_,now=await environment(tmp_path,[{'areas':['living_room'],'area_domains':['light','switch'],'last_attempt':'input_datetime.test','allow_time_only':True}])
    try:
        await ar.async_load(hass)
        living=ar.async_get(hass).async_create('Living room')
        kitchen=ar.async_get(hass).async_create('Kitchen')
        for entity,area in [('light.a',living),('switch.plug',living),('light.group',living),('light.kitchen',kitchen)]:
            state(hass,now,entity)
            await assign_area(hass,entity,area)
        state(hass,now,'light.group',entity_id=['light.a','light.kitchen'])
        await run()
        assert shutoff_targets(calls)==['light.a','switch.plug']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_new_member_delays_entire_group(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    try:
        state(hass,now,'light.b',age=5)
        await run()
        assert calls==[]
        state(hass,now,'light.b',age=35)
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_excluded_new_light_does_not_delay_group(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    try:
        state(hass,now,'light.excluded',age=1)
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_overlap_between_entries_is_skipped_on_both_sides(tmp_path):
    entries=[{'entities':['light.a','light.shared'],'last_attempt':'input_datetime.a','allow_time_only':True},
             {'entities':['light.b','light.shared'],'last_attempt':'input_datetime.b','allow_time_only':True}]
    hass,calls,run,_,now=await environment(tmp_path,entries)
    try:
        for entity in ('light.a','light.b','light.shared'): state(hass,now,entity)
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_group_membership_change_during_marker_write_is_respected(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        state(hass,now,'light.room_group',entity_id=['light.a','light.excluded'])
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_excluded_group_changes_before_dispatch_are_respected(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.protected_group'])
    state(hass,now,'light.protected_group',entity_id=['light.excluded'])
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        state(hass,now,'light.protected_group',entity_id=['light.excluded','light.b'])
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_reactivated_member_and_failed_member_do_not_block_other_targets(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    async def fail(call):
        data=dict(call.data)
        entity=data['entity_id'][0] if isinstance(data['entity_id'],list) else data['entity_id']
        calls.append(('light.turn_off',{'entity_id':entity}))
        if entity=='light.a': raise HomeAssistantError('Simulated device failure')
    hass.services.async_register('light','turn_off',fail)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()

@pytest.mark.asyncio
async def test_cycle_is_bounded_and_does_not_hide_other_leaf(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=[])
    try:
        state(hass,now,'light.room_group',entity_id=['group.cycle','light.a'])
        state(hass,now,'group.cycle',entity_id=['light.room_group'])
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_empty_group_and_unknown_members_do_not_receive_commands(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path)
    try:
        state(hass,now,'light.room_group',entity_id=[])
        await run()
        assert calls==[]
        state(hass,now,'light.room_group',entity_id=['light.missing','light.excluded'])
        state(hass,now,'light.excluded',status='unavailable')
        await run()
        assert calls==[]
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_mixed_group_dispatch_and_disallowed_members(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path)
    try:
        state(hass,now,'light.room_group',entity_id=['light.a','switch.plug','climate.heater','media_player.speaker','lock.door'])
        state(hass,now,'switch.plug')
        state(hass,now,'climate.heater',status='heat',hvac_modes=['off','heat'])
        state(hass,now,'media_player.speaker',status='playing')
        state(hass,now,'lock.door',status='unlocked')
        await run()
        assert shutoff_targets(calls)==['climate.heater','light.a','media_player.speaker','switch.plug']
        assert 'lock.door' not in shutoff_targets(calls)
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_reactivated_member_during_marker_write_is_skipped(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        hass.states.async_set('light.b','off')
        hass.states.async_set('light.b','on')
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_exception_group_changed_between_leaf_commands(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.protected_group'])
    state(hass,now,'light.protected_group',entity_id=['light.excluded'])
    async def control(call):
        entity=call.data['entity_id']
        if isinstance(entity,list): entity=entity[0]
        calls.append(('light.turn_off',{'entity_id':entity}))
        if entity=='light.a':
            state(hass,now,'light.protected_group',entity_id=['light.excluded','light.b'])
    hass.services.async_register('light','turn_off',control)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_area_move_during_attempt_is_respected(tmp_path):
    hass,calls,run,_,now=await environment(tmp_path,[{'areas':['living_room'],'last_attempt':'input_datetime.test','allow_time_only':True}])
    await ar.async_load(hass)
    living=ar.async_get(hass).async_create('Living room')
    other=ar.async_get(hass).async_create('Other room')
    for entity in ('light.a','light.b'):
        state(hass,now,entity)
        await assign_area(hass,entity,living)
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        er.async_get(hass).async_update_entity('light.b',area_id=other.id)
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_group_preview_names_only_included_active_leaves(tmp_path):
    hass,calls,run,_,now=await environment(tmp_path,[{'name':'Living room lights','entity':'light.room_group','exclude_entities':['light.excluded'],'last_attempt':'input_datetime.test','allow_time_only':True}],preview_only=True)
    try:
        state(hass,now,'light.room_group',entity_id=['light.a','light.b','light.excluded'])
        for entity in ('light.a','light.excluded'): state(hass,now,entity)
        state(hass,now,'light.b',status='off')
        await run()
        assert len(calls)==1 and calls[0][0]=='persistent_notification.create'
        message=calls[0][1]['message']
        assert 'Living room lights' in message and 'light.a' in message
        assert 'light.excluded' not in message and 'light.b' not in message
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_missing_exception_member_stays_excluded_when_it_appears(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['light.excluded'])
    # Both explicit exclusion and group membership remain literal IDs, even while a state is absent.
    hass.states._states.pop('light.excluded')
    async def changed(call):
        hass.states.async_set('input_datetime.test','2026-10-15 00:00:00',{'has_date':True,'has_time':True,'timestamp':call.data['timestamp']})
        state(hass,now,'light.excluded')
    hass.services.async_register('input_datetime','set_datetime',changed)
    try:
        await run()
        assert shutoff_targets(calls)==['light.a','light.b']
    finally: await hass.async_stop()

@pytest.mark.asyncio
async def test_deep_group_nesting_is_bounded_without_aggregate_fallback(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path)
    try:
        state(hass,now,'light.room_group',entity_id=['light.a','group.level_0'])
        for index in range(40):
            state(hass,now,f'group.level_{index}',entity_id=[f'group.level_{index+1}'] if index<39 else ['light.b'])
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


def test_new_and_legacy_entry_forms_validate_with_real_selectors():
    from homeassistant.helpers.selector import selector
    from homeassistant.util.yaml import load_yaml
    from integration_tests.test_forgotten_devices import PATH
    field=load_yaml(str(PATH))['blueprint']['input']['devices']['input']['device_entries']['selector']
    select=selector(field)
    legacy={'entity':'light.a','last_attempt':'input_datetime.test'}
    room={'name':'Living room','areas':['living_room'],'area_domains':['light'],'exclude_entities':['light.b'],'last_attempt':'input_datetime.room'}
    group={'entity':'group.room','entities':['light.a','light.b'],'exclude_entities':['light.a'],'last_attempt':'input_datetime.group'}
    assert select([legacy,room,group])==[legacy,room,group]

@pytest.mark.asyncio
async def test_unresolved_exception_group_blocks_whole_entry(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['group.missing_protection'])
    try:
        await run()
        assert calls==[]
        state(hass,now,'group.missing_protection',entity_id=['light.b','light.excluded'])
        await run()
        assert shutoff_targets(calls)==['light.a']
    finally: await hass.async_stop()


@pytest.mark.asyncio
async def test_depth_limit_in_exception_group_does_not_leak_members(tmp_path):
    hass,calls,run,now=await group_environment(tmp_path,exclude_entities=['group.level_0'])
    try:
        for index in range(40):
            state(hass,now,f'group.level_{index}',entity_id=[f'group.level_{index+1}'] if index<39 else ['light.b'])
        await run()
        assert calls==[]
    finally: await hass.async_stop()
