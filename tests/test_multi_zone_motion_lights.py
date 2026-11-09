"""Static and Jinja regressions for multi-zone motion lighting."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import re
import unittest

import jinja2
import yaml


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "blueprints/automation/multi_zone_motion_lights/multi_zone_motion_lights.yaml"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for item in obj.values():
            yield from walk(item)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def find_variable(node, name):
    for obj in walk(node):
        if isinstance(obj, dict) and isinstance(obj.get("variables"), dict):
            if name in obj["variables"]:
                return obj["variables"][name]
    raise KeyError(name)


def templates(obj):
    for node in walk(obj):
        if isinstance(node, str) and ("{{" in node or "{%" in node):
            yield node
        if isinstance(node, dict):
            for value in node.values():
                if isinstance(value, str) and ("{{" in value or "{%" in value):
                    yield value


class MultiZoneMotionLightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = FILE.read_text(encoding="utf-8")
        cls.config = yaml.load(cls.text, Loader=Loader)
        cls.inputs = {key: entry for section in cls.config["blueprint"]["input"].values()
                      for key, entry in section["input"].items()}
        cls.env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)

    def rendered(self, key, **kwargs):
        return self.env.from_string(find_variable(self.config["actions"], key)).render(
            **kwargs
        ).strip()

    def test_blueprint_structure_and_multi_zone_form(self):
        metadata = self.config["blueprint"]
        self.assertEqual(metadata["domain"], "automation")
        self.assertEqual(metadata["homeassistant"]["min_version"], "2026.10.1")
        self.assertEqual(self.config["mode"], "queued")
        self.assertEqual(self.config["max"], 50)
        self.assertEqual(self.config["triggers"][0]["entity_id"],
                         "!input monitored_motion_sensors")
        selector = self.inputs["lighting_zones"]["selector"]["object"]
        self.assertTrue(selector["multiple"])
        self.assertEqual(selector["label_field"], "name")
        fields = selector["fields"]
        self.assertTrue({
            "name", "motion_sensors", "on_entities", "off_entities", "off_delay_seconds",
            "linked_presence", "cross_room_grace_seconds", "ownership_helper",
            "lux_sensor", "lux_threshold", "sun_mode", "start_time", "end_time",
            "blocking_entity", "enabled", "darkness_activation", "occupancy_sensors",
        }.issubset(fields))
        self.assertEqual(fields["darkness_activation"]["default"], "off")
        self.assertEqual(self.inputs["monitored_illuminance_sensors"]["default"], [])
        self.assertEqual(fields["cross_room_grace_seconds"]["default"], 180)
        self.assertEqual(fields["off_delay_seconds"]["default"], 120)
        self.assertEqual(self.inputs["lighting_zones"]["default"], [])
        self.assertEqual(set(self.config["blueprint"]["input"]),
                         {"sensors_section", "zones_section", "diagnostics_section"})

    def test_turn_on_blocker_accepts_light_entity_and_fails_closed(self):
        fields = self.inputs["lighting_zones"]["selector"]["object"]["fields"]
        domains = {entry["domain"] for entry in
                   fields["blocking_entity"]["selector"]["entity"]["filter"]}
        self.assertIn("light", domains)
        self.assertIn("binary_sensor", domains)
        activation = str(self.config["actions"])
        self.assertIn("is_state(zone_blocker, 'off')", activation)

    def test_inputs_exist_and_templates_compile(self):
        found = set(re.findall(r"!input\s+([a-zA-Z0-9_]+)", self.text))
        self.assertFalse(found - set(self.inputs))
        compiled = 0
        for obj in walk(self.config):
            if isinstance(obj, str) and ("{{" in obj or "{%" in obj):
                with self.subTest(template=obj[:80]):
                    self.env.parse(obj)
                    compiled += 1
            elif isinstance(obj, dict):
                for value in obj.values():
                    if isinstance(value, str) and ("{{" in value or "{%" in value):
                        with self.subTest(template=value[:80]):
                            self.env.parse(value)
                            compiled += 1
        self.assertGreater(compiled, 20)

    def test_cross_room_form_explains_direction_and_multiple_linked_rooms(self):
        blueprint = self.config["blueprint"]
        fields = self.inputs["lighting_zones"]["selector"]["object"]["fields"]
        linked_label = fields["linked_presence"]["label"]
        grace_label = fields["cross_room_grace_seconds"]["label"]
        self.assertIn("THIS zone", linked_label)
        self.assertIn("OTHER rooms", linked_label)
        self.assertIn("ALL linked rooms", grace_label)
        self.assertIn("HALLWAY", blueprint["input"]["zones_section"]["description"])
        self.assertIn("BATHROOM", blueprint["input"]["zones_section"]["description"])
        self.assertIn("KITCHEN", blueprint["input"]["zones_section"]["description"])
        self.assertIn("BATHROOM", self.inputs["lighting_zones"]["description"])
        self.assertIn("KITCHEN", self.inputs["lighting_zones"]["description"])
        # Nested object selector fields cannot contain descriptions in HA 2026.10.1.
        self.assertNotIn("description", fields["linked_presence"])
        self.assertNotIn("description", fields["cross_room_grace_seconds"])

    def test_motion_is_immediate_without_global_state_listener(self):
        triggers = self.config["triggers"]
        self.assertEqual([x["id"] for x in triggers],
                         ["motion_on", "sunset", "lux_changed",
                          "off_reconcile", "startup", "startup"])
        self.assertEqual(triggers[0]["trigger"], "state")
        self.assertEqual(triggers[0]["to"], "on")
        self.assertEqual(triggers[1]["entity_id"], "sun.sun")
        self.assertEqual(triggers[1]["from"], "above_horizon")
        self.assertEqual(triggers[1]["to"], "below_horizon")
        self.assertEqual(triggers[2]["entity_id"],
                         "!input monitored_illuminance_sensors")
        self.assertIn("_monitored_lux", triggers[2]["enabled"])
        self.assertEqual(triggers[3]["seconds"], "/15")
        self.assertEqual(triggers[4]["trigger"], "homeassistant")
        self.assertFalse(any(x.get("event_type") == "state_changed" for x in triggers))
        self.assertFalse(any(x.get("trigger") == "time_pattern" and
                             x.get("seconds") in ("/1", 1) for x in triggers))

    def test_each_area_independent_and_actions_limited(self):
        all_steps = list(walk(self.config["actions"]))
        command_names = [x["action"] for x in all_steps if isinstance(x, dict)
                         and "action" in x]
        self.assertEqual(command_names.count("homeassistant.turn_on"), 1)
        self.assertEqual(command_names.count("homeassistant.turn_off"), 1)
        self.assertEqual(set(command_names) - {
            "homeassistant.turn_on", "homeassistant.turn_off",
            "input_boolean.turn_on", "input_boolean.turn_off", "system_log.write"
        }, set())
        self.assertNotIn("shell_command", self.text)
        self.assertFalse(any("delay" in x for x in command_names))
        self.assertNotIn("wait_for_trigger", self.text)
        # Condition actions inside repeat would accidentally abort every later zone.
        for item in all_steps:
            if isinstance(item, dict) and "repeat" in item:
                for step in item["repeat"]["sequence"]:
                    self.assertNotIn("condition", step)

    def test_zone_targets_derive_only_for_light_switch_or_group(self):
        self.assertEqual(self.rendered(
            "zone_off", zone_off_explicit=[],
            zone_on=["light.hall", "switch.desk"]
        ), "['light.hall', 'switch.desk']")
        self.assertEqual(self.rendered(
            "zone_off", zone_off_explicit=[],
            zone_on=["scene.night", "light.hall"]
        ), "[]")
        self.assertEqual(self.rendered(
            "zone_off", zone_off_explicit=["light.hall"],
            zone_on=["scene.night"]
        ), "['light.hall']")

    def test_time_window_normal_and_overnight(self):
        s = find_variable(self.config["actions"], "in_time_window")
        t = self.env.from_string(s)
        def ok(start, end, current):
            return t.render(zone_start=start, zone_end=end,
                            now_local=current).strip() == "True"
        self.assertTrue(ok("08:00:00", "22:00:00", "19:00:00"))
        self.assertFalse(ok("08:00:00", "22:00:00", "23:00:00"))
        self.assertTrue(ok("22:00:00", "06:00:00", "23:00:00"))
        self.assertTrue(ok("22:00:00", "06:00:00", "02:00:00"))
        self.assertFalse(ok("22:00:00", "06:00:00", "12:00:00"))

    def test_cross_room_presence_holds_off_until_clear_plus_grace(self):
        expression = self.env.from_string(next(
            x["value_template"] for x in walk(self.config["actions"])
            if isinstance(x, dict) and "value_template" in x
            and "last_linked_clear" in x["value_template"]
            and "last_motion_clear" in x["value_template"]
        ))
        base = dict(
            zone={"enabled": True},
            zone_delay=120, zone_off=["light.hall"], zone_motion=["binary_sensor.hall"],
            motion_valid=True, linked_clear=True, off_targets_known=True,
            off_targets_on=True, new_manual_on=False, zone_owner="",
            last_motion_clear=1000, last_linked_clear=1200,
            zone_grace=180, zone_linked=["binary_sensor.bath"],
            now=lambda: 1400, as_timestamp=lambda x: x,
            is_state=lambda ent, value: False
        )
        def eligible(**updates):
            args = base | updates
            return expression.render(**args).strip() == "True"
        self.assertTrue(eligible())  # 1400 >= max(1120, 1380)
        self.assertFalse(eligible(now=lambda: 1379))
        self.assertFalse(eligible(linked_clear=False))  # bath is occupied
        self.assertFalse(eligible(motion_valid=False))  # hall is occupied
        self.assertFalse(eligible(new_manual_on=True))
        self.assertFalse(eligible(off_targets_on=False))
        self.assertFalse(eligible(zone_owner="input_boolean.hall",
                                  is_state=lambda ent, value: False))
        self.assertTrue(eligible(zone_owner="input_boolean.hall",
                                 is_state=lambda ent, value: True))
        self.assertTrue(eligible(zone_linked=[], last_linked_clear=0,
                                 now=lambda: 1120))
        self.assertFalse(eligible(zone_delay=0))
        self.assertFalse(eligible(zone={"enabled": False}))
        self.assertFalse(eligible(off_targets_known=False))

    def test_missing_and_unavailable_motion_fails_closed(self):
        template = self.env.from_string(find_variable(self.config["actions"], "motion_valid"))
        states = {}
        base = ["binary_sensor.motion_a", "binary_sensor.motion_b"]
        def is_state(entity_id, expected):
            return entity_id in states and states[entity_id].state == expected
        def ok():
            return template.render(zone_motion=base, zone_activity=base,
                                   is_state=is_state).strip() == "True"
        self.assertFalse(ok())
        states[base[0]] = SimpleNamespace(state="off")
        self.assertFalse(ok())
        states[base[1]] = SimpleNamespace(state="off")
        self.assertTrue(ok())
        states[base[1]].state = "on"
        self.assertFalse(ok())
        states[base[1]].state = "unavailable"
        self.assertFalse(ok())

    def test_presence_unavailable_never_turns_lights_off(self):
        template = self.env.from_string(find_variable(self.config["actions"], "linked_clear"))
        states = {"binary_sensor.bath": SimpleNamespace(state="unknown")}
        result = template.render(zone_linked=["binary_sensor.bath"],
                                 is_state=lambda entity, expected:
                                     entity in states and states[entity].state == expected)
        self.assertEqual(result.strip(), "False")

    def test_unregistered_warning_is_diagnostic_only(self):
        template = self.env.from_string(find_variable(self.config["actions"], "unregistered"))
        zones = [
            {"name": "Hall", "motion_sensors": ["binary_sensor.hall"]},
            {"name": "Bath", "motion_sensors": ["binary_sensor.bath"]},
        ]
        self.assertEqual(template.render(configured_zones=zones,
                                         monitored_entities=["binary_sensor.hall"]).strip(),
                         "['binary_sensor.bath']")
        self.assertEqual(template.render(configured_zones=zones,
                                         monitored_entities=["binary_sensor.hall",
                                                             "binary_sensor.bath"]).strip(),
                         "[]")

    def test_group_entities_use_their_own_state_not_expanded_members(self):
        target = self.env.from_string(find_variable(self.config["actions"], "target_available"))
        available = target.render(
            zone_off=["group.hall_lights"],
            has_value=lambda eid: eid == "group.hall_lights",
        ).strip()
        self.assertEqual(available, "True")
        motion = self.env.from_string(find_variable(self.config["actions"], "motion_valid"))
        self.assertEqual(motion.render(
            zone_motion=["group.hall_motion"], zone_activity=["group.hall_motion"],
            is_state=lambda eid, expected: eid == "group.hall_motion" and expected == "off",
        ).strip(), "True")
        self.assertEqual(motion.render(
            zone_motion=["group.hall_motion"], zone_activity=["group.hall_motion"],
            is_state=lambda eid, expected: False,
        ).strip(), "False")

    def test_late_auto_on_is_not_misclassified_as_manual_override(self):
        template = self.env.from_string(find_variable(self.config["actions"], "new_manual_on"))
        lights = {"light.hall": SimpleNamespace(last_changed=1100)}
        def render(light_ts, motion_end=1000, extra_end=0, hold=None):
            lights["light.hall"].last_changed = light_ts
            return template.render(
                zone_off=["light.hall"], zone_delay=120,
                last_motion_clear=motion_end, last_linked_clear=extra_end,
                zone_grace=180, zone_linked=hold or [],
                states=lights, is_state=lambda eid, state: state == "on",
                as_timestamp=lambda value, default=0: value,
            ).strip() == "True"
        self.assertFalse(render(1100))  # delayed light acknowledgement inside off delay
        self.assertFalse(render(1120))
        self.assertTrue(render(1124))  # manual activation after the due deadline
        self.assertFalse(render(1300, extra_end=1200, hold=["binary_sensor.bath"]))
        self.assertTrue(render(1383, extra_end=1200, hold=["binary_sensor.bath"]))

    def test_own_zone_presence_required_for_darkness_and_blocks_early_off(self):
        occupied = self.env.from_string(find_variable(self.config["actions"], "zone_occupied"))
        values = {
            "binary_sensor.hall_motion": "off",
            "input_boolean.hall_occupied": "on",
            "binary_sensor.bath_occupied": "on",
        }
        def own_occupied():
            return occupied.render(
                zone_motion=["binary_sensor.hall_motion"],
                zone_local_presence=["input_boolean.hall_occupied"],
                is_state=lambda eid, state: values.get(eid) == state
            ).strip() == "True"
        self.assertTrue(own_occupied())
        values["input_boolean.hall_occupied"] = "off"
        self.assertFalse(own_occupied())  # bath is cross-room hold, not own presence
        motion_valid = self.env.from_string(find_variable(self.config["actions"], "motion_valid"))
        values["input_boolean.hall_occupied"] = "on"
        self.assertEqual(motion_valid.render(
            zone_motion=["binary_sensor.hall_motion"],
            zone_activity=["binary_sensor.hall_motion", "input_boolean.hall_occupied"],
            is_state=lambda eid, state: values.get(eid) == state
        ).strip(), "False")

    def test_sunset_and_lux_crossing_match_only_occupied_zone(self):
        template = self.env.from_string(find_variable(self.config["actions"], "activation_event_matches"))
        def matches(event_id, mode="both", occupied=True, entity="sun.sun",
                    lux_id="sensor.hall_lux", old="100", new="79", threshold=80):
            trigger = SimpleNamespace(
                id=event_id, entity_id=entity,
                from_state=SimpleNamespace(state=old),
                to_state=SimpleNamespace(state=new),
            )
            return template.render(
                trigger=trigger, zone_motion=["binary_sensor.hall_motion"],
                zone_darkness_mode=mode, zone_occupied=occupied,
                zone_lux=lux_id, zone_lux_threshold=threshold,
                is_number=lambda val: (
                    isinstance(val, (str, int, float))
                    and str(val).replace(".", "", 1).isdigit()
                ),
            ).strip() == "True"
        self.assertTrue(matches("sunset"))
        self.assertFalse(matches("sunset", occupied=False))
        self.assertFalse(matches("sunset", mode="lux"))
        self.assertFalse(matches("sunset", mode="off"))
        self.assertTrue(matches("lux_changed", entity="sensor.hall_lux"))
        self.assertTrue(matches("lux_changed", entity="sensor.hall_lux", new="80"))
        self.assertFalse(matches("lux_changed", entity="sensor.kitchen_lux"))
        self.assertFalse(matches("lux_changed", entity="sensor.hall_lux", old="70"))
        self.assertFalse(matches("lux_changed", entity="sensor.hall_lux", new="90"))
        self.assertFalse(matches("lux_changed", entity="sensor.hall_lux", old="unavailable"))
        self.assertFalse(matches("lux_changed", entity="sensor.hall_lux", occupied=False))
        self.assertFalse(matches("lux_changed", entity="sensor.hall_lux", mode="sunset"))
        self.assertFalse(matches("lux_changed", entity="sensor.hall_lux", mode="off"))
        self.assertTrue(matches("motion_on", entity="binary_sensor.hall_motion", mode="off",
                                occupied=False))
        self.assertFalse(matches("motion_on", entity="binary_sensor.other_motion"))

    def test_unregistered_lux_is_detected_only_for_lux_trigger_zones(self):
        tmpl = self.env.from_string(find_variable(self.config["actions"], "unregistered_lux"))
        zones = [
            {"name": "Hall", "lux_sensor": "sensor.hall_lux",
             "darkness_activation": "lux"},
            {"name": "Bath", "lux_sensor": "sensor.bath_lux",
             "darkness_activation": "sunset"},
            {"name": "Kitchen", "lux_sensor": "sensor.hall_lux",
             "darkness_activation": "both"}
        ]
        self.assertEqual(
            tmpl.render(configured_zones=zones, monitored_lux_entities=[]).strip(),
            "['sensor.hall_lux']",
        )
        self.assertEqual(
            tmpl.render(configured_zones=zones,
                        monitored_lux_entities=["sensor.hall_lux"]).strip(), "[]",
        )

    def test_diagnostics_and_docs(self):
        readme = (FILE.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("Cross-room presence", readme)
        self.assertIn("Already occupied at sunset", readme)
        self.assertIn("illumination", readme.lower())
        self.assertIn("Which zone gets the other room's presence sensor?", readme)
        self.assertIn("only the first row applies", readme)
        self.assertIn("Bathroom", readme)
        self.assertIn("Kitchen", readme)
        self.assertIn("ownership helper", readme.lower())
        self.assertIn("15 seconds", readme)
        self.assertIn("freakshock88", readme)
        root = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("multi_zone_motion_lights.yaml", root)


if __name__ == "__main__":
    unittest.main()
