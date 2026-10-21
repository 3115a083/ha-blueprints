"""Static and behavioral regression tests for multi-zone heating."""
from pathlib import Path
import re
import unittest

import jinja2
import yaml


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/automation/advanced_heating_multi_zone/advanced_heating_multi_zone.yaml"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


def find_variable(node, name):
    if isinstance(node, dict):
        if "variables" in node and isinstance(node["variables"], dict) and name in node["variables"]:
            return node["variables"][name]
        for value in node.values():
            match = find_variable(value, name)
            if match is not None:
                return match
    elif isinstance(node, list):
        for value in node:
            match = find_variable(value, name)
            if match is not None:
                return match
    return None


def templates(node):
    if isinstance(node, dict):
        for item in node.values():
            yield from templates(item)
    elif isinstance(node, list):
        for item in node:
            yield from templates(item)
    elif isinstance(node, str) and ("{{" in node or "{%" in node):
        yield node


def check_action_guards(actions, inside_repeat=False):
    """A condition *action* inside a repeat aborts the entire automation."""
    for step in actions:
        if inside_repeat:
            assert "condition" not in step, "An invalid room must not cancel later rooms"
        if "repeat" in step:
            check_action_guards(step["repeat"]["sequence"], True)
        if "then" in step:
            check_action_guards(step["then"], inside_repeat)
        if "else" in step:
            check_action_guards(step["else"], inside_repeat)
        if "choose" in step:
            for choice in step["choose"]:
                check_action_guards(choice["sequence"], inside_repeat)
        if "default" in step and isinstance(step["default"], list):
            check_action_guards(step["default"], inside_repeat)


class HeatingMultiZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PATH.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.text, Loader=Loader)
        cls.sections = cls.data["blueprint"]["input"]
        cls.inputs = {key: entry for section in cls.sections.values()
                      for key, entry in section["input"].items()}
        cls.env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)

    def test_blueprint_structure(self):
        metadata = self.data["blueprint"]
        self.assertEqual(metadata["domain"], "automation")
        self.assertEqual(metadata["homeassistant"]["min_version"], "2026.10.1")
        self.assertEqual(list(self.sections), ["rooms_section", "general_section",
                                              "vacation_section", "diagnostics_section"])
        self.assertIn("Räume", self.sections["rooms_section"]["name"])
        room_selector = self.inputs["room_entries"]["selector"]["object"]
        self.assertTrue(room_selector["multiple"])
        self.assertEqual(room_selector["label_field"], "name")
        self.assertEqual(self.inputs["room_entries"]["default"], [])
        self.assertTrue(self.inputs["preview_only"]["default"])
        self.assertEqual(self.inputs["vacation_strategy"]["default"], "setback")
        self.assertIn("panhans", metadata["description"])
        self.assertIn("https://community.home-assistant.io/t/advanced-heating-control/469873",
                      metadata["description"])

    def test_room_controls_in_one_section_and_globals_separate(self):
        fields = self.inputs["room_entries"]["selector"]["object"]["fields"]
        required = {"name", "thermostats", "temperature_sensor", "windows", "window_delay",
                    "window_strategy", "schedule", "motion", "comfort_temperature",
                    "eco_temperature", "vacation_temperature", "frost_temperature",
                    "hvac_mode", "pause_entity", "calibrate_generic"}
        self.assertTrue(required.issubset(fields))
        self.assertTrue({"people", "guest_entity", "party_entity", "after_change_actions",
                         "safety_conditions"}.issubset(self.sections["general_section"]["input"]))
        self.assertEqual(set(self.sections["vacation_section"]["input"]),
                         {"vacation_switch", "vacation_strategy"})
        self.assertNotIn("thermostat_section", self.sections)

    def test_inputs_resolve_and_jinja_parses(self):
        refs = re.findall(r"!input\s+([a-zA-Z0-9_]+)", self.text)
        self.assertTrue(refs)
        self.assertEqual(set(refs) - set(self.inputs), set())
        for tmpl in templates(self.data):
            with self.subTest(template=tmpl[:75]):
                self.env.parse(tmpl)

    def test_room_or_thermostat_failure_cannot_abort_next_room(self):
        check_action_guards(self.data["actions"])
        self.assertEqual(self.data["mode"], "single")
        triggers = self.data["triggers"]
        self.assertEqual({item["trigger"] for item in triggers},
                         {"time_pattern", "homeassistant", "state"})
        self.assertEqual(triggers[0]["minutes"], "/1")

    def test_priority_table(self):
        tmpl = self.env.from_string(find_variable(self.data["actions"], "desired_profile"))
        states = {}
        def is_state(key, value):
            return states.get(key) == value
        base = dict(is_state=is_state, windows_open_long=False, vacation_active=False,
                    party_active=False, anybody_home=True, guest_active=False,
                    room_schedule="", room_motion="", unscheduled_value="comfort")
        def result(**kwargs):
            return tmpl.render(**(base | kwargs)).strip()
        self.assertEqual(result(), "comfort")
        self.assertEqual(result(vacation_active=True, party_active=True), "vacation")
        self.assertEqual(result(windows_open_long=True, vacation_active=True), "window")
        self.assertEqual(result(anybody_home=False), "eco")
        self.assertEqual(result(anybody_home=False, guest_active=True), "comfort")
        self.assertEqual(result(room_schedule="schedule.test"), "eco")
        self.assertEqual(result(room_motion="binary_sensor.test"), "eco")
        states["schedule.test"] = "on"
        states["binary_sensor.test"] = "on"
        self.assertEqual(result(room_schedule="schedule.test",
                                room_motion="binary_sensor.test"), "comfort")
        self.assertEqual(result(unscheduled_value="eco"), "eco")

    def test_frost_protection_when_off_is_requested(self):
        tmpl = self.env.from_string(find_variable(self.data["actions"], "frost_needed"))
        def result(temp):
            return tmpl.render(desired_off=True, current_room_temp=temp,
                               room_frost=7).strip()
        self.assertEqual(result(999), "True")
        self.assertEqual(result(7.4), "True")
        self.assertEqual(result(8.1), "False")

    def test_documentation_and_source_url(self):
        source = ("https://github.com/3115a083/ha-blueprints/blob/main/"
                  + PATH.relative_to(ROOT).as_posix())
        self.assertEqual(self.data["blueprint"]["source_url"], source)
        doc = (PATH.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn(chr(96) * 3 + "text\n" + source + "\n" + chr(96) * 3, doc)
        self.assertIn("blueprints_updater.reload", doc)
        self.assertIn("panhans", doc)


if __name__ == "__main__":
    unittest.main()
