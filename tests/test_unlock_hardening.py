"""Regression tests for the October 2026 Unlock Sequence security review."""
from datetime import datetime, timezone
import unittest

import test_unlock_sequence as base


class HardeningTests(unittest.TestCase):
    setUpClass = classmethod(base.UnlockSequenceTests.setUpClass.__func__)
    config = base.UnlockSequenceTests.config
    def helpers(self, count='0', attrs=None, **overrides):
        values = {'input_number.count': count, 'input_datetime.lock': '2000-01-01 00:00:00',
                  'input_datetime.window': '2000-01-01 00:00:00', 'input_datetime.cooldown': '2000-01-01 00:00:00'}
        properties = {'input_number.count': {'min': 0, 'max': 100, 'step': 1}}
        properties.update({k: {'has_date': True, 'has_time': True} for k in values if k.startswith('input_datetime.')})
        properties['input_number.count'].update(attrs or {})
        def stamp(v, default=None):
            try:
                return datetime.fromisoformat(v).replace(tzinfo=timezone.utc).timestamp()
            except (TypeError, ValueError):
                return default
        context = dict(_protect=True, _count_helper='input_number.count', _lock_helper='input_datetime.lock',
                       _window_mode='cumulative', _window_helper='input_datetime.window', _maximum_failures=3,
                       _cooldown_seconds=0, _cooldown_helper='input_datetime.cooldown', _verify=False,
                       states=lambda e: values.get(e, 'unknown'), state_attr=lambda e, a: properties.get(e, {}).get(a),
                       as_timestamp=stamp)
        context.update(overrides)
        return self.env.from_string(self.data['variables']['_helpers_valid']).render(**context).strip() == 'True'

    def test_counter_bounds_and_integrality(self):
        self.assertTrue(self.helpers())
        for attrs in ({'max': 1}, {'min': 1}, {'step': 0.5}, {'max': None}):
            with self.subTest(attrs=attrs):
                self.assertFalse(self.helpers(attrs=attrs))
        for value in ('0.5', '-1', 'unavailable', 'unknown', 'bad', 'nan', 'inf', '101'):
            with self.subTest(value=value):
                self.assertFalse(self.helpers(count=value))

    def test_unused_optional_helpers_can_be_missing(self):
        self.assertTrue(self.helpers(_protect=False, _count_helper='', _lock_helper='', _window_helper=''))

    def test_active_helpers_must_be_distinct(self):
        self.assertFalse(self.helpers(_window_mode='fixed', _window_helper='input_datetime.lock'))
        self.assertFalse(self.helpers(_cooldown_seconds=30, _cooldown_helper='input_datetime.lock'))

    def test_overlaps_and_unknown_combinations_fail_closed(self):
        banks = [
            [{'trigger': 'event', 'event_type': 'button', 'id': 'A'},
             {'trigger': 'event', 'event_type': 'button', 'event_data': {'key': 'one'}, 'id': 'B'}],
            [{'trigger': 'mqtt', 'topic': 'buttons/#', 'id': 'A'},
             {'trigger': 'mqtt', 'topic': 'buttons/a', 'payload': 'press', 'id': 'B'}],
            [{'trigger': 'template', 'value_template': '{{ true }}', 'id': 'A'},
             {'trigger': 'state', 'entity_id': 'sensor.x', 'to': 'on', 'id': 'B'}],
            [{'trigger': 'event', 'event_type': 'a', 'variables': {'_protect': False}, 'id': 'A'}],
        ]
        for bank in banks:
            with self.subTest(bank=bank):
                self.assertFalse(self.config(_code='A', _advanced_triggers=bank))

    def test_disjoint_events_mqtt_and_states_work(self):
        for platform, first, second in [
            ('event', {'event_type': 'button', 'event_data': {'key': 'one'}}, {'event_type': 'button', 'event_data': {'key': 'two'}}),
            ('mqtt', {'topic': 'buttons', 'payload': 'a'}, {'topic': 'buttons', 'payload': 'b'}),
            ('state', {'entity_id': 'sensor.x', 'to': 'on'}, {'entity_id': 'sensor.x', 'to': 'off'}),
        ]:
            bank = [dict(trigger=platform, id='A', **first), dict(trigger=platform, id='B', **second)]
            with self.subTest(platform=platform):
                self.assertTrue(self.config(_code='AB', _advanced_triggers=bank))
        self.assertTrue(self.config(_code='AAAA', _advanced_triggers=[
            {'trigger': 'template', 'value_template': '{{ true }}', 'id': 'A'}]))

    def test_live_guards_use_template_and_abort_entire_run(self):
        template = self.data['variables']['_helpers_valid']
        aliases = ['Validate live storage before waiting',
                   'Fail closed if storage became invalid during the wait',
                   'Validate live storage after collection',
                   'Validate live protection state before final authorization',
                   'Validate live storage immediately before success actions']
        for alias in aliases:
            node = next(n for n in base.walk(self.data) if n.get('alias') == alias)
            self.assertEqual(node['if'][0]['value_template'], template)
            self.assertIn('stop', node['else'][0])


if __name__ == '__main__':
    unittest.main()
