"""Static regression checks for the Garage Automation Manager blueprint."""
from pathlib import Path
from types import SimpleNamespace
import re
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/automation/garage_automation_manager/garage_automation_manager.yaml"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def find_var(node, key):
    for item in walk(node):
        if isinstance(item, dict) and isinstance(item.get("variables"), dict):
            if key in item["variables"]:
                return item["variables"][key]
    raise KeyError(key)


class GarageManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PATH.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.text, Loader=Loader)
        cls.inputs = {
            key: spec
            for section in cls.data["blueprint"]["input"].values()
            for key, spec in section["input"].items()
        }
        cls.jinja = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        cls.jinja.filters["bool"] = lambda x, default=False: x in (True, "True", "true", "on", 1)
        cls.jinja.filters["regex_match"] = lambda x, pattern: bool(re.match(pattern, x))
        cls.jinja.globals["is_number"] = lambda x: bool(re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", str(x)))

    def render(self, name, **context):
        template = find_var(self.data["actions"], name)
        return self.jinja.from_string(template).render(**context).strip()

    def test_blueprint_inputs_and_disabled_routes(self):
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2026.11.0")
        self.assertEqual(self.data["mode"], "queued")
        for input_name in (
            "calendar_enabled", "schedule_enabled", "custom_open_enabled",
            "vehicle_enabled", "automatic_closing_enabled", "door_open_close_enabled",
            "custom_close_enabled",
        ):
            self.assertIs(self.inputs[input_name]["default"], False, input_name)
        self.assertEqual(self.inputs["calendar_summary_filter"]["default"], "Garage")
        self.assertEqual(self.inputs["calendar_offset"]["default"], {"minutes": -15})
        self.assertEqual(self.inputs["calendar_allow_all_day"]["default"], False)
        self.assertEqual(self.inputs["open_conditions"]["selector"], {"condition": {}})
        self.assertEqual(self.inputs["close_conditions"]["selector"], {"condition": {}})
        self.assertEqual(self.inputs["close_after_minutes"]["default"], 20)
        self.assertEqual(self.inputs["safety_clear_sensor"]["default"],
                         "binary_sensor.garage_clearance_placeholder")

    def test_calendar_filter_and_all_day_guard(self):
        trigger = SimpleNamespace(
            id="calendar_open",
            calendar_event=SimpleNamespace(summary="GarAge service visit", all_day=False),
        )
        common = dict(trigger=trigger, calendar_enabled=True, calendar_all_day=False)
        self.assertEqual(self.render("calendar_match", **common, calendar_filter="garage"), "True")
        self.assertEqual(self.render("calendar_match", **common, calendar_filter="holiday"), "False")
        self.assertEqual(self.render("calendar_match", **common, calendar_filter=""), "True")
        trigger.calendar_event.all_day = True
        self.assertEqual(self.render("calendar_match", **common, calendar_filter="Garage"), "False")
        self.assertEqual(self.render("calendar_match", **(common | {"calendar_all_day": True}),
                                     calendar_filter="Garage"), "True")
        self.assertEqual(self.render("calendar_match",
                                     trigger=SimpleNamespace(id="schedule_open"),
                                     calendar_enabled=True, calendar_all_day=False,
                                     calendar_filter="Garage"), "False")

    def test_arrival_requires_threshold_crossing_direction_and_car(self):
        def expand(items):
            return [SimpleNamespace(state=x) for x in items]
        base = dict(
            trigger=SimpleNamespace(
                id="vehicle_approach",
                from_state=SimpleNamespace(state="1.0"),
                to_state=SimpleNamespace(state="0.4"),
            ),
            vehicle_enabled=True, distance_threshold=0.5,
            vehicle_connection_sensors=["on", "off"],
            direction_sensor="sensor.direction",
            states=lambda eid: "towards",
            is_number=lambda x: bool(re.fullmatch(r"\d+(?:\.\d+)?", str(x))),
            expand=expand,
        )
        self.assertEqual(self.render("arrival_match", **base), "True")
        self.assertEqual(self.render(
            "arrival_match", **(base | {"vehicle_connection_sensors": ["off"]})), "False")
        self.assertEqual(self.render(
            "arrival_match", **(base | {"states": lambda eid: "stationary"})), "False")
        self.assertEqual(self.render(
            "arrival_match", **(base | {"trigger": SimpleNamespace(
                id="vehicle_approach", from_state=SimpleNamespace(state="0.2"),
                to_state=SimpleNamespace(state="0.1"))})), "False")
        self.assertEqual(self.render(
            "arrival_match", **(base | {"trigger": SimpleNamespace(
                id="vehicle_approach", from_state=SimpleNamespace(state="unknown"),
                to_state=SimpleNamespace(state="0.4"))})), "False")

    def test_all_template_inputs_declared_and_parse(self):
        refs = set(re.findall(r"!input\s+([A-Za-z0-9_]+)", self.text))
        self.assertFalse(refs - set(self.inputs))
        parsed = 0
        for node in walk(self.data):
            if isinstance(node, dict):
                for value in node.values():
                    if isinstance(value, str) and ("{{" in value or "{%" in value):
                        self.jinja.parse(value)
                        parsed += 1
        self.assertGreater(parsed, 15)
        ids = {t["id"] for t in self.data["triggers"]}
        self.assertEqual(ids, {
            "calendar_open", "schedule_open", "custom_open", "vehicle_approach",
            "garage_opened", "house_door_opened", "custom_close",
            "deadline_changed", "minute_check", "mobile_action", "startup",
        })
        for trigger in self.data["triggers"]:
            if trigger["id"] in {
                "calendar_open", "schedule_open", "custom_open", "vehicle_approach",
                "house_door_opened", "custom_close", "deadline_changed",
            }:
                self.assertIn("enabled", trigger)
        self.assertNotIn("state_changed", self.text)

    def test_all_closing_routes_enforce_safety(self):
        source = self.text
        self.assertEqual(source.count("action: cover.close_cover"), 1)
        self.assertIn("and clearance_ready | bool(false)", source)
        self.assertIn("conditions: !input close_conditions", source)
        self.assertIn("is_state(garage, 'open')", source)
        self.assertIn("binary_sensor.garage_clearance_placeholder", source)
        self.assertIn("as_timestamp(states(deadline_helper), 0)", source)
        self.assertIn("timestamp_now | float(0) - 86400", source)
        self.assertIn("timestamp_now | float(0) >= deadline_ts | float(0)", source)
        self.assertIn("<= 300", source)
        self.assertIn("trigger.event.data.get('action') == action_extend", source)
        self.assertIn("trigger.event.data.get('action') == action_close_now", source)
        self.assertIn("trigger.event.data.get('action') == action_cancel", source)
        allowed = {
            "cover.open_cover", "cover.close_cover", "input_datetime.set_datetime",
            "persistent_notification.create", "{{ notify_action }}",
            "{{ action_extend }}", "{{ action_cancel }}", "{{ action_close_now }}",
        }
        self.assertEqual(
            {s["action"] for s in walk(self.data["actions"])
             if isinstance(s, dict) and "action" in s}, allowed
        )
        self.assertIn("calendar_match | bool(false)", source)
        self.assertIn("arrival_match | bool(false)", source)
        self.assertIn("open_requested | bool(false)", source)
        self.assertIn("close_requested | bool(false)", source)


if __name__ == "__main__":
    unittest.main()
