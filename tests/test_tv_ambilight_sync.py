"""Static and Jinja regression tests for TV/Ambilight synchronization."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import re
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/automation/tv_ambilight_sync/tv_ambilight_sync.yaml"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


class States:
    def __init__(self, state_data):
        self.entities = {
            key: SimpleNamespace(state=value, last_changed=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc))
            for key, value in state_data.items()
        }

    def __call__(self, key):
        return self.entities.get(key, SimpleNamespace(state="unknown")).state

    def __getitem__(self, key):
        return self.entities.get(key)


class TvAmbilightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PATH.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.source, Loader=Loader)
        cls.inputs = {
            name: value
            for section in cls.data["blueprint"]["input"].values()
            for name, value in section["input"].items()
        }
        cls.jinja = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        cls.jinja.filters["regex_match"] = lambda text, pattern: bool(re.match(pattern, text))

    def render(self, variable, **extra):
        state_data = extra.pop("state_data", {})
        states = States(state_data)
        context = {
            "states": states,
            "is_state": lambda eid, wanted: states(eid) == wanted,
            "this": SimpleNamespace(entity_id="automation.my_tv_ambilight"),
            "tv_entity": "media_player.lounge_tv",
            "ambilight_entity": "light.lounge_ambilight",
            "max_on_minutes": 0,
            "timeout_lockout": "",
            "mobile_notify_action": "",
            "now": lambda: datetime(2026, 11, 11, 12, 5, tzinfo=timezone.utc),
            "as_timestamp": lambda stamp, default=0: stamp.timestamp() if hasattr(stamp, "timestamp") else default,
            **extra,
        }
        return self.jinja.from_string(self.data["variables"][variable]).render(**context).strip()

    def test_inputs_and_supported_domains(self):
        bp = self.data["blueprint"]
        self.assertEqual(bp["domain"], "automation")
        self.assertEqual(bp["homeassistant"]["min_version"], "2026.11.0")
        self.assertIn("source_url", bp)
        self.assertEqual(list(bp["input"]), ["devices", "conditions_section", "safety_section"])
        self.assertEqual(self.inputs["tv_entity"]["selector"]["entity"]["filter"], [{"domain": "media_player"}])
        self.assertEqual(self.inputs["ambilight_entity"]["selector"]["entity"]["filter"],
                         [{"domain": "light"}, {"domain": "switch"}])
        self.assertEqual(self.inputs["enable_conditions"]["default"], [])
        self.assertEqual(self.inputs["enable_conditions"]["selector"], {"condition": {}})
        self.assertEqual(self.inputs["watch_entities"]["default"], ["sun.sun"])
        self.assertTrue(self.inputs["watch_entities"]["selector"]["entity"]["multiple"])
        self.assertEqual(self.inputs["max_on_minutes"]["default"], 0)
        self.assertEqual(self.inputs["timeout_lockout"]["default"], "")
        self.assertEqual({item["value"] for item in
                          self.inputs["timeout_behavior"]["selector"]["select"]["options"]},
                         {"turn_off", "notify"})
        self.assertTrue(bp["input"]["safety_section"]["collapsed"])

    def test_triggers_and_recheck_with_no_global_state_listener(self):
        triggers = self.data["triggers"]
        self.assertEqual(
            [(t["id"], t["trigger"]) for t in triggers],
            [
                ("tv_changed", "state"),
                ("ambilight_changed", "state"),
                ("dependency_changed", "state"),
                ("reconcile", "time_pattern"),
                ("startup", "homeassistant"),
                ("notification_action", "event"),
            ],
        )
        self.assertEqual(triggers[0]["entity_id"], "!input tv_entity")
        self.assertEqual(triggers[2]["entity_id"], "!input watch_entities")
        self.assertEqual(triggers[3]["minutes"], "/1")
        self.assertEqual(triggers[5]["event_type"], "mobile_app_notification_action")
        self.assertEqual(self.data["mode"], "restart")
        self.assertNotIn("event_type: state_changed", self.source)
        self.assertNotIn("delay:", self.source)

    def test_all_inputs_declared_and_templates_parse(self):
        references = set(re.findall(r"!input\s+([A-Za-z0-9_]+)", self.source))
        self.assertFalse(references - set(self.inputs))
        templates = 0
        for node in walk(self.data):
            if isinstance(node, dict):
                for value in node.values():
                    if isinstance(value, str) and ("{{" in value or "{%" in value):
                        self.jinja.parse(value)
                        templates += 1
        self.assertGreater(templates, 15)

    def test_tv_states_are_safe(self):
        for state in ("on", "playing", "paused", "idle", "buffering"):
            self.assertEqual(self.render("tv_is_active",
                             state_data={"media_player.lounge_tv": state}), "True")
        for state in ("off", "standby", "unknown", "unavailable"):
            self.assertEqual(self.render("tv_is_active",
                             state_data={"media_player.lounge_tv": state}), "False")

    def test_helper_and_action_ids_are_isolated(self):
        self.assertEqual(self.render("helper_configured"), "False")
        self.assertEqual(self.render("helper_configured",
                         timeout_lockout="input_boolean.ambilight_guard"), "True")
        self.assertEqual(self.render("lockout_is_on",
                         timeout_lockout="input_boolean.ambilight_guard",
                         helper_configured=True,
                         state_data={"input_boolean.ambilight_guard": "on"}), "True")
        self.assertEqual(self.render("off_action_key"),
                         "TV_AMBILIGHT_OFF_automation.my_tv_ambilight")
        self.assertEqual(self.render("timeout_notice_id"),
                         "tv_ambilight_timeout_automation_my_tv_ambilight")

    def test_safety_fallback_action_flow(self):
        self.assertIn("max_on_minutes | int(0) > 0 and not helper_configured", self.source)
        self.assertIn("input_boolean.turn_on", self.source)
        self.assertIn("input_boolean.turn_off", self.source)
        self.assertIn("not is_state(timeout_lockout, 'on')", self.source)
        self.assertIn("not lockout_is_on", self.source)
        self.assertIn("notify.mobile_app_", self.source)
        self.assertIn("Turn off Ambilight", self.source)
        self.assertIn("mobile_app_notification_action", self.source)
        self.assertIn("trigger.event.data.get('action') == off_action_key", self.source)
        self.assertIn("conditions: !input enable_conditions", self.source)
        self.assertIn("action: homeassistant.turn_off", self.source)
        self.assertIn("action: homeassistant.turn_on", self.source)
        self.assertTrue((PATH.parent / "README.md").exists())
        self.assertTrue((PATH.parent / "CHANGELOG.md").exists())
        guide = (PATH.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("input_boolean", guide)
        self.assertIn("blueprints_updater.reload", guide)
        self.assertIn("notify.mobile_app_", guide)


if __name__ == "__main__":
    unittest.main()
