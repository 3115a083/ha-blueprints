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
            "blocking_entity", "enabled",
        }.issubset(fields))
        self.assertEqual(fields["cross_room_grace_seconds"]["default"], 180)
        self.assertEqual(fields["off_delay_seconds"]["default"], 120)
        self.assertEqual(self.inputs["lighting_zones"]["default"], [])
        self.assertEqual(set(self.config["blueprint"]["input"]),
                         {"sensors_section", "zones_section", "diagnostics_section"})

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

    def test_motion_is_immediate_without_global_state_listener(self):
        triggers = self.config["triggers"]
        self.assertEqual([x["id"] for x in triggers],
                         ["motion_on", "off_reconcile", "startup", "startup"])
        self.assertEqual(triggers[0]["trigger"], "state")
        self.assertEqual(triggers[0]["to"], "on")
        self.assertEqual(triggers[1]["seconds"], "/15")
        self.assertEqual(triggers[2]["trigger"], "homeassistant")
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
        self.assertNotIn("delay:", self.text)
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
        def expand(entities):
            return [states[x] for x in entities if x in states]
        base = ["binary_sensor.motion_a", "binary_sensor.motion_b"]
        def ok():
            return template.render(zone_motion=base, expand=expand).strip() == "True"
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
                                 expand=lambda xs: [states[x] for x in xs if x in states])
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

    def test_diagnostics_and_docs(self):
        readme = (FILE.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("Cross-room presence", readme)
        self.assertIn("ownership helper", readme.lower())
        self.assertIn("15 seconds", readme)
        self.assertIn("freakshock88", readme)
        root = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("multi_zone_motion_lights.yaml", root)


if __name__ == "__main__":
    unittest.main()
