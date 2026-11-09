"""Static regression checks for repeatable Motion Lighting multi-zone blueprint."""
from pathlib import Path
import re
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/automation/motion_lighting_multi_zone/motion_lighting_multi_zone.yaml"
README = PATH.parent / "README.md"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


def templates(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from templates(item)
    elif isinstance(value, list):
        for item in value:
            yield from templates(item)
    elif isinstance(value, str) and ("{{" in value or "{%" in value):
        yield value


def locate_variables(value, key):
    if isinstance(value, dict):
        if isinstance(value.get("variables"), dict) and key in value["variables"]:
            return value["variables"][key]
        for item in value.values():
            found = locate_variables(item, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = locate_variables(item, key)
            if found is not None:
                return found
    return None


class MotionLightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PATH.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.text, Loader=Loader)
        cls.inputs = {
            key: value
            for section in cls.data["blueprint"]["input"].values()
            for key, value in section["input"].items()
        }

    def test_structure(self):
        meta = self.data["blueprint"]
        self.assertEqual(meta["domain"], "automation")
        self.assertEqual(meta["homeassistant"]["min_version"], "2026.10.1")
        self.assertTrue(meta["source_url"].endswith(
            "/motion_lighting_multi_zone/motion_lighting_multi_zone.yaml"
        ))
        self.assertEqual(self.data["mode"], "queued")
        self.assertGreaterEqual(self.data["max"], 20)
        self.assertEqual(self.inputs["zone_entries"]["default"], [])
        self.assertEqual(self.inputs["zone_entries"]["selector"]["object"]["multiple"], True)
        self.assertEqual(
            self.inputs["zone_entries"]["selector"]["object"]["label_field"], "name"
        )
        self.assertTrue(
            self.inputs["trigger_sensors"]["selector"]["entity"]["multiple"]
        )

    def test_zone_fields_and_defaults(self):
        fields = self.inputs["zone_entries"]["selector"]["object"]["fields"]
        for key in (
            "name", "motion_sensors", "turn_on_entity", "turn_off_entities",
            "auto_off", "off_delay_seconds", "illuminance_sensor",
            "illuminance_below", "illuminance_cutoff_helper",
            "sun_mode", "restrict_time", "time_from", "time_until",
            "linked_presence", "linked_behavior", "linked_seconds",
            "on_blocker", "off_blocker",
        ):
            self.assertIn(key, fields)
        self.assertEqual(fields["off_delay_seconds"]["default"], 120)
        self.assertEqual(fields["linked_behavior"]["default"], "hold")
        self.assertEqual(fields["linked_seconds"]["default"], 120)
        self.assertTrue(fields["auto_off"]["default"])
        self.assertTrue(fields["enabled"]["default"])
        self.assertEqual(fields["linked_presence"]["default"], [])

    def test_light_allowed_for_per_zone_and_global_blockers(self):
        fields = self.inputs["zone_entries"]["selector"]["object"]["fields"]
        for key in ("on_blocker", "off_blocker"):
            domains = {item["domain"] for item in
                       fields[key]["selector"]["entity"]["filter"]}
            self.assertIn("light", domains, key)
        for key in ("on_blocker_global", "off_blocker_global"):
            domains = {item["domain"] for item in
                       self.inputs[key]["selector"]["entity"]["filter"]}
            self.assertIn("light", domains, key)
        actions = str(self.data["actions"])
        self.assertIn("is_state(zone_on_blocker, 'off')", actions)
        self.assertIn("is_state(global_on_blocker_id, 'off')", actions)

    def test_all_input_references_valid_and_templates_compile(self):
        unknown = set(re.findall(r"!input\s+([a-zA-Z0-9_]+)", self.text)) - set(self.inputs)
        self.assertEqual(unknown, set())
        env = jinja2.Environment()
        for index, template in enumerate(templates(self.data)):
            with self.subTest(template=index):
                env.parse(template)

    def test_triggers_are_fast_and_have_no_event_bus_wildcard(self):
        triggers = self.data["triggers"]
        self.assertEqual(triggers[0]["trigger"], "state")
        self.assertEqual(triggers[0]["entity_id"], "!input trigger_sensors")
        self.assertEqual(triggers[0]["to"], "on")
        self.assertEqual(triggers[0]["id"], "motion_on")
        self.assertEqual(triggers[1]["trigger"], "time_pattern")
        self.assertEqual(triggers[1]["seconds"], "/15")
        self.assertEqual(triggers[2]["trigger"], "homeassistant")
        self.assertNotIn("state_changed", str(triggers))
        self.assertNotIn("wait_for_trigger", self.text)
        self.assertNotIn("delay", [key for action in self.data["actions"] for key in action])
        self.assertNotIn("input_datetime.set_datetime", self.text)

    def test_zone_on_and_off_are_guarded(self):
        actions = str(self.data["actions"])
        self.assertIn("trigger.entity_id in zone_motion", actions)
        self.assertIn("already_lit", actions)
        self.assertIn("lux_allowed", actions)
        self.assertIn("time_allowed", actions)
        self.assertIn("sun_allowed", actions)
        self.assertIn("zone_motion_status", actions)
        self.assertIn("zone_presence_status", actions)
        self.assertIn("zone_can_off", actions)
        self.assertIn("ns.all_known", actions)
        self.assertIn("ns.manual", actions)
        self.assertIn("homeassistant.turn_on", actions)
        self.assertIn("homeassistant.turn_off", actions)
        self.assertIn("zone_link_mode == 'hold'", actions)
        self.assertIn("zone_link_mode == 'extend'", actions)
        self.assertIn("linked_presence", actions)

    def test_english_docs_include_real_import_and_updater(self):
        doc = README.read_text(encoding="utf-8")
        self.assertIn("hallway", doc.lower())
        self.assertIn("bathroom", doc.lower())
        self.assertIn("Linked presence", doc)
        self.assertIn("blueprints_updater.reload", doc)
        self.assertIn("main/blueprints/automation/motion_lighting_multi_zone/", doc)
        catalog = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("motion_lighting_multi_zone/motion_lighting_multi_zone.yaml", catalog)


if __name__ == "__main__":
    unittest.main()
