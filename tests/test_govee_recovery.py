"""Regression checks for the Govee2MQTT recovery automation blueprint.

Offline tests check YAML, Jinja, safety guards and unlimited optional device
entries. They are not a substitute for real Home Assistant/Supervisor testing.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/automation/govee_recovery/govee_recovery.yaml"


class InputLoader(yaml.SafeLoader):
    pass


InputLoader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


class GoveeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BLUEPRINT.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.text, Loader=InputLoader)
        cls.inputs = {
            key: definition
            for section in cls.data["blueprint"]["input"].values()
            for key, definition in section["input"].items()
        }
        cls.env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        cls.env.filters["bool"] = lambda x: str(x).strip().lower() in ("true", "on", "1")

    @staticmethod
    def truthy(x):
        return str(x).strip().lower() == "true"

    def render(self, template, lamps, entity_states=None, **values):
        states_map = entity_states or {}
        context = {
            "lamp_entries": lamps,
            "_lamp_entries": lamps,
            "states": lambda entity: states_map.get(entity, "unknown"),
            "is_state": lambda entity, state: states_map.get(entity) == state,
        }
        context.update(values)
        return self.env.from_string(template).render(**context).strip()

    def get_variable(self, name):
        for entry in self.data["actions"]:
            if name in entry.get("variables", {}):
                return entry["variables"][name]
        raise AssertionError(f"Missing variable {name}")

    def get_trigger(self, trigger_id):
        return next(t for t in self.data["triggers"] if t["id"] == trigger_id)

    def test_modern_blueprint_schema(self):
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2025.7.0")
        self.assertEqual(self.data["mode"], "single")
        self.assertIn("source_url", self.data["blueprint"])
        self.assertIn("triggers", self.data)
        self.assertIn("actions", self.data)
        self.assertNotIn("trigger", self.data)
        self.assertNotIn("action", self.data)

    def test_all_input_references_exist(self):
        references = set(re.findall(r"!input\s+([a-z0-9_]+)", self.text))
        self.assertEqual(references - set(self.inputs), set())
        self.assertEqual(set(self.inputs) & {"light_1", "relay_1", "light_2", "relay_2"}, set())
        self.assertNotIn("default", self.inputs["lamp_entries"])
        for name, spec in self.inputs.items():
            if name != "lamp_entries":
                self.assertIn("default", spec, name)

    def test_repeated_objects_with_optional_relay_and_ping(self):
        sections = self.data["blueprint"]["input"]
        self.assertEqual(list(sections),
                         ["devices", "recovery", "bridge", "diagnostics", "notifications"])
        schema = self.inputs["lamp_entries"]["selector"]["object"]
        self.assertTrue(schema["multiple"])
        self.assertEqual(schema["label_field"], "light")
        self.assertTrue(schema["fields"]["light"]["required"])
        self.assertFalse(schema["fields"]["relay"]["required"])
        self.assertFalse(schema["fields"]["ping"]["required"])
        self.assertEqual(schema["fields"]["light"]["selector"]["entity"]["filter"]["domain"], "light")
        self.assertEqual(schema["fields"]["relay"]["selector"]["entity"]["filter"]["domain"], "switch")
        self.assertEqual(schema["fields"]["ping"]["selector"]["entity"]["filter"]["domain"], "binary_sensor")
        self.assertTrue(sections["bridge"]["collapsed"])
        self.assertTrue(sections["diagnostics"]["collapsed"])
        self.assertTrue(sections["notifications"]["collapsed"])

    def test_defaults_disruptive_actions_off(self):
        self.assertTrue(self.inputs["restore_power"]["default"])
        self.assertFalse(self.inputs["power_cycle_enabled"]["default"])
        self.assertFalse(self.inputs["app_restart_enabled"]["default"])
        self.assertEqual(self.inputs["cooldown_minutes"]["default"], 60)
        self.assertEqual(self.inputs["cooldown_helper"]["default"], "")

    def test_all_templates_parse(self):
        def visit(value):
            if isinstance(value, str) and ("{{" in value or "{%" in value):
                self.env.parse(value)
            elif isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.data)

    def test_any_number_of_lights_detects_offline(self):
        t = self.get_trigger("some_light_offline")
        self.assertEqual(t["trigger"], "template")
        self.assertEqual(t["for"], {"minutes": "!input offline_minutes"})
        lamps = [
            {"light": "light.living", "relay": "switch.a", "ping": "binary_sensor.ping"},
            {"light": "light.bedroom"},
            {"light": "light.hallway", "relay": None},
            {"light": "light.office", "ping": "binary_sensor.ping_office"},
        ]
        healthy = {item["light"]: "off" for item in lamps}
        self.assertFalse(self.truthy(self.render(t["value_template"], lamps, healthy)))
        healthy["light.hallway"] = "unavailable"
        self.assertTrue(self.truthy(self.render(t["value_template"], lamps, healthy)))
        self.assertEqual(self.render(self.get_variable("initial_offline_count"), lamps, healthy), "1")
        healthy["light.bedroom"] = "unknown"
        self.assertEqual(self.render(self.get_variable("initial_offline_count"), lamps, healthy), "2")
        self.assertFalse(self.truthy(self.render(t["value_template"], [], {})))

    def test_absent_relay_is_not_interpreted_as_power_fault(self):
        t = self.get_trigger("some_relay_off")
        lamps = [
            {"light": "light.a"},
            {"light": "light.b", "relay": None},
            {"light": "light.c", "relay": "switch.c"},
        ]
        statuses = {"light.a": "unavailable", "light.b": "on",
                    "light.c": "off", "switch.c": "on"}
        self.assertFalse(self.truthy(self.render(t["value_template"], lamps, statuses)))
        self.assertFalse(self.truthy(self.render(self.get_variable("initial_relay_fault"), lamps, statuses)))
        statuses["switch.c"] = "off"
        self.assertTrue(self.truthy(self.render(t["value_template"], lamps, statuses)))
        self.assertTrue(self.truthy(self.render(self.get_variable("initial_relay_fault"), lamps, statuses)))

    def test_null_optional_fields_render_as_not_configured(self):
        lamps = [{"light": "light.no_relay", "relay": None, "ping": None},
                 {"light": "light.plain"}]
        value = self.render(self.get_variable("initial_snapshot"), lamps,
                            {"light.no_relay": "unavailable", "light.plain": "on"})
        self.assertIn("power=no relay", value)
        self.assertIn("ping=not configured", value)
        final_bad = self.render(self.get_variable("final_bad_relay"), lamps, {})
        self.assertFalse(self.truthy(final_bad))

    def test_one_relay_repair_loop_for_all_lights(self):
        loop_actions = [x for x in self.data["actions"]
                        if "if" in x and "initial_relay_fault" in str(x["if"])
                        and "then" in x and any("repeat" in sub for sub in x["then"])]
        self.assertEqual(len(loop_actions), 1)
        repeater = loop_actions[0]["then"][0]["repeat"]
        self.assertEqual(repeater["for_each"], "!input lamp_entries")
        self.assertIn("get('relay'", str(repeater["sequence"]))
        self.assertIn("current_relay != ''", str(repeater["sequence"]))
        self.assertIn("switch.turn_on", str(repeater["sequence"]))

    def test_power_cycle_only_when_single_failed_with_relay_and_ping(self):
        self.assertEqual(self.text.count("- action: switch.turn_off"), 1)
        outer = next(x for x in self.data["actions"] if "if" in x
                     and "power_cycle_enabled" in str(x["if"]))
        gate = outer["if"][0]["value_template"]
        self.assertIn("initial_offline_count | int == 1", gate)
        self.assertIn("not initial_relay_fault", gate)
        self.assertIn("cooldown_saved", gate)
        repeater = outer["then"][0]["repeat"]
        self.assertEqual(repeater["for_each"], "!input lamp_entries")
        inner = next(x for x in repeater["sequence"] if "if" in x)
        inner_gate = inner["if"][0]["value_template"]
        for phrase in ("current_relay != ''", "is_state(current_relay, 'on')",
                       "current_ping != ''", "is_state(current_ping, 'off')"):
            self.assertIn(phrase, inner_gate)
        self.assertEqual([x["action"] for x in inner["then"] if "action" in x],
                         ["switch.turn_off", "switch.turn_on"])

    def test_addon_restart_once_including_relayless_lights(self):
        self.assertEqual(self.text.count("- action: hassio.app_restart"), 1)
        app = next(x for x in self.data["actions"] if "if" in x
                   and "app_restart_enabled" in str(x["if"]))
        guard = app["if"][0]["value_template"]
        self.assertIn("relay == '' or is_state(relay, 'on')", guard)
        self.assertIn("cooldown_saved", guard)
        self.assertIn("app_slug | trim", guard)
        self.assertTrue(self.truthy(self.render(
            guard, [{"light": "light.norelay"}],
            {"light.norelay": "unavailable"},
            app_restart_enabled=True, cooldown_saved=True, app_slug="test_govee")))
        self.assertFalse(self.truthy(self.render(
            guard, [{"light": "light.norelay"}],
            {"light.norelay": "off"},
            app_restart_enabled=True, cooldown_saved=True, app_slug="test_govee")))
        self.assertNotIn("mqtt.publish", self.text)
        self.assertNotIn("homeassistant.restart", self.text)

    def test_persisted_cooldown_and_periodic_retry(self):
        self.assertEqual(self.get_trigger("periodic")["minutes"], "/30")
        self.assertIn("cooldown_ok", self.text)
        self.assertIn("cooldown_saved", self.text)
        self.assertIn("input_datetime.set_datetime", self.text)
        self.assertIn("cooldown_helper != ''", self.text)
        self.assertIn("trigger.id != 'periodic' or cooldown_helper != ''", self.text)

    def test_startup_configuration_notifications_and_failure(self):
        self.assertEqual(self.get_trigger("startup")["event"], "start")
        self.assertIn("Select at least one Govee light", self.text)
        self.assertIn('notification_id: govee_recovery_failed', self.text)
        self.assertIn("- action: notify.send_message", self.text)
        self.assertIn("initial_snapshot", self.text)
        self.assertIn("final_snapshot", self.text)
        self.assertIn("lamp_entries | count", self.text)

    def test_documentation_and_root_catalog(self):
        manual = (BLUEPRINT.parent / "README.md").read_text(encoding="utf-8")
        overview = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("any number", manual)
        self.assertIn("relay", manual.lower())
        self.assertIn("Migrating from an earlier version", manual)
        self.assertIn("govee_recovery/README.md", overview)


if __name__ == "__main__":
    unittest.main()
