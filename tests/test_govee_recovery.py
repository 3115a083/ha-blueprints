"""Static regression checks for the Govee/ESPHome recovery blueprint.

The checks do not simulate Supervisor, MQTT, ESPHome or physical power switching.
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
            name: spec
            for group in cls.data["blueprint"]["input"].values()
            for name, spec in group["input"].items()
        }
        cls.env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        cls.env.filters["bool"] = lambda value: str(value).strip().lower() in ("true", "on", "1")

    def test_modern_automation_blueprint(self):
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2024.10.0")
        self.assertEqual(self.data["mode"], "single")
        self.assertIn("source_url", self.data["blueprint"])
        self.assertIn("triggers", self.data)
        self.assertIn("actions", self.data)
        self.assertNotIn("trigger", self.data)
        self.assertNotIn("action", self.data)

    def test_all_inputs_declared(self):
        references = set(re.findall(r"!input\s+([a-z0-9_]+)", self.text))
        self.assertEqual(references - set(self.inputs), set())
        self.assertNotIn("default", self.inputs["light_1"])
        self.assertNotIn("default", self.inputs["relay_1"])
        for name, spec in self.inputs.items():
            if name not in ("light_1", "relay_1"):
                self.assertIn("default", spec, name)

    def test_ui_order_and_safe_defaults(self):
        sections = self.data["blueprint"]["input"]
        self.assertEqual(
            list(sections), ["devices", "recovery", "bridge", "diagnostics", "notify"]
        )
        self.assertEqual(self.inputs["restore_power"]["default"], True)
        self.assertEqual(self.inputs["power_cycle_enabled"]["default"], False)
        self.assertEqual(self.inputs["app_restart_enabled"]["default"], False)
        self.assertEqual(self.inputs["cooldown_minutes"]["default"], 60)
        self.assertEqual(self.inputs["light_2"]["default"], "")
        self.assertTrue(sections["bridge"]["collapsed"])
        self.assertTrue(sections["diagnostics"]["collapsed"])
        self.assertTrue(sections["notify"]["collapsed"])

    def test_all_templates_parse(self):
        def visit(value):
            if isinstance(value, str) and ("{{" in value or "{%" in value):
                self.env.parse(value)
            elif isinstance(value, dict):
                for v in value.values():
                    visit(v)
            elif isinstance(value, list):
                for v in value:
                    visit(v)

        visit(self.data)

    def test_watch_both_lamps_relays_startup_and_periodic(self):
        ids = {trigger["id"] for trigger in self.data["triggers"]}
        self.assertEqual(
            ids,
            {"lamp_1_unavailable", "lamp_2_unavailable", "relay_1_off",
             "relay_2_off", "startup", "periodic"},
        )
        triggers = self.data["triggers"]
        self.assertEqual(next(x for x in triggers if x["id"] == "periodic")["minutes"], "/30")
        for trig_id in ("lamp_1_unavailable", "lamp_2_unavailable"):
            self.assertEqual(next(x for x in triggers if x["id"] == trig_id)["for"],
                             {"minutes": "!input offline_minutes"})
        self.assertTrue(any("startup" in str(x) for x in self.data["actions"]))

    def test_incomplete_second_pair_notifies_and_stops(self):
        body = str(self.data["actions"])
        self.assertIn("pair_2_valid", body)
        self.assertIn("Govee recovery configuration incomplete", body)
        self.assertIn("Configure both the second light and its relay.", body)

    def test_cooldown_allows_soft_relay_restoration_only(self):
        body = str(self.data["actions"])
        self.assertIn("cooldown_ok", body)
        self.assertIn("initial_relay_1_off", body)
        self.assertIn("initial_relay_2_off", body)
        self.assertIn("cooldown_saved", body)
        self.assertIn("as_timestamp(states(cooldown_helper)", body)
        self.assertIn("input_datetime.set_datetime", body)

    def test_no_unattended_power_cycle_without_guard(self):
        """Exactly two deliberate OFF commands, each guarded by ping and cooldown."""
        turn_off = [x for x in self.text.split("- action: switch.turn_off")[1:]]
        self.assertEqual(len(turn_off), 2)
        for field in ("power_cycle_enabled", "cooldown_ok", "cooldown_saved",
                      "not (both_missing_initially", "is_state(ping_1, 'off')"):
            self.assertIn(field, self.text)
        self.assertIn("is_state(ping_2, 'off')", self.text)
        self.assertEqual(self.text.count("and cooldown_saved | bool"), 2)
        self.assertEqual(self.text.count("not (both_missing_initially | bool)"), 2)
        self.assertEqual(self.text.count("- action: switch.turn_on"), 4)

    def test_one_optional_app_restart(self):
        self.assertEqual(self.text.count("- action: hassio.app_restart"), 1)
        self.assertIn("app_restart_enabled and cooldown_ok", self.text)
        self.assertIn("app: \"{{ app_slug | trim }}\"", self.text)
        self.assertNotIn("hassio.host_reboot", self.text)
        self.assertNotIn("homeassistant.restart", self.text)
        self.assertNotIn("mqtt.publish", self.text)

    def test_failure_is_reported_without_mobile_notification_target(self):
        self.assertIn("- action: persistent_notification.create", self.text)
        self.assertIn("notification_id: govee_recovery_failed", self.text)
        self.assertIn("- action: notify.send_message", self.text)
        self.assertIn("notify_entity != ''", self.text)
        self.assertIn("initial_snapshot", self.text)
        self.assertIn("final_snapshot", self.text)

    def test_safety_templates_for_power_cycle(self):
        guards = [
            x["if"][0]["value_template"]
            for x in self.data["actions"]
            if isinstance(x, dict)
            and "if" in x
            and isinstance(x["if"], list)
            and x["if"]
            and "value_template" in x["if"][0]
            and "power_cycle_enabled" in x["if"][0]["value_template"]
        ]
        self.assertEqual(len(guards), 2)
        for i, expr in enumerate(guards, start=1):
            with self.subTest(lamp=i):
                self.assertIn(f"states(light_{i}) in ['unavailable', 'unknown']", expr)
                self.assertIn(f"is_state(relay_{i}, 'on')", expr)
                self.assertIn(f"is_state(ping_{i}, 'off')", expr)
                self.assertIn("cooldown_saved", expr)

    def test_own_documentation_and_catalog(self):
        local = BLUEPRINT.parent / "README.md"
        root = ROOT / "README.md"
        self.assertTrue(local.is_file())
        self.assertIn("Govee", local.read_text(encoding="utf-8"))
        self.assertIn("govee_recovery/README.md", root.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
