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
        self.assertEqual(self.inputs["calendar_home_person"]["default"], "")
        self.assertEqual(self.inputs["calendar_open_conditions"]["default"], [])
        self.assertEqual(
            self.inputs["calendar_open_conditions"]["selector"], {"condition": {}}
        )
        self.assertEqual(self.inputs["open_conditions"]["selector"], {"condition": {}})
        self.assertEqual(self.inputs["close_conditions"]["selector"], {"condition": {}})
        self.assertEqual(self.inputs["close_after_minutes"]["default"], 20)
        self.assertEqual(self.inputs["safety_clear_sensor"]["default"], "")
        self.assertEqual(self.inputs["notify_entities"]["default"], [])
        self.assertEqual(
            self.inputs["notify_entities"]["selector"]["entity"]["filter"],
            [{"domain": "notify"}],
        )
        self.assertEqual(self.inputs["vehicle_nearby_meters"]["default"], 0)
        self.assertEqual(self.inputs["vehicle_proximity_direction"]["selector"]["entity"]["filter"], [{"domain": "sensor"}])
        self.assertEqual(self.inputs["vehicle_proximity_distance"]["selector"]["entity"]["filter"], [{"domain": "sensor"}])
        self.assertEqual(self.inputs["vehicle_max_gps_accuracy_meters"]["default"], 25)
        self.assertEqual(self.inputs["vehicle_min_connection_minutes"]["default"], 2)
        self.assertEqual(self.inputs["vehicle_min_approach_meters"]["default"], 300)
        self.assertEqual(
            self.inputs["vehicle_session_helper"]["selector"]["entity"]["filter"],
            [{"domain": "input_text"}],
        )
        self.assertEqual(self.inputs["vehicle_bluetooth_device"]["default"], "")
        self.assertEqual(self.inputs["vehicle_bluetooth_list_attribute"]["default"],
                         "connected_paired_devices")
        self.assertNotIn("vehicle_distance_sensor", self.inputs)

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

    def test_bluetooth_exact_device_attribute_matching(self):
        def expand(entities):
            return [SimpleNamespace(state=v) for v in entities]

        base = {
            "vehicle_connection_sensors": [],
            "vehicle_bluetooth_sensor": "sensor.phone_bluetooth_connection",
            "vehicle_bluetooth_device": "My Car",
            "vehicle_bluetooth_list_attribute": "connected_paired_devices",
            "expand": expand,
            "states": lambda e: "1",
            "state_attr": lambda e, a: ["AA:BB:CC (My Car)", "11:22 (Headphones)"],
        }
        self.assertEqual(self.render("car_connected", **base), "True")
        self.assertEqual(self.render(
            "car_connected", **(base | {"vehicle_bluetooth_device": "My"})), "False")
        self.assertEqual(self.render(
            "car_connected", **(base | {
                "vehicle_bluetooth_device": "My Car",
                "state_attr": lambda e, a: ["AA:BB:CC (Other Car)"],
            })), "False")
        self.assertEqual(self.render(
            "car_connected", **(base | {
                "vehicle_bluetooth_device": "AA:BB:CC",
            })), "True")
        self.assertEqual(self.render(
            "car_connected", **(base | {
                "vehicle_bluetooth_device": "my car",
                "states": lambda e: "unavailable",
            })), "False")
        self.assertEqual(self.render(
            "car_connected", **(base | {
                "vehicle_bluetooth_device": "",
                "vehicle_connection_sensors": ["on"],
            })), "True")

    def test_arrival_requires_proximity_arrived_trip_distance_and_connection_duration(self):
        base = {
            "trigger": SimpleNamespace(
                id="vehicle_approach",
                to_state=SimpleNamespace(state="arrived"),
            ),
            "vehicle_enabled": True,
            "trip_helper_ready": True,
            "car_connected": True,
            "gps_ready": True,
            "gps_home_distance_meters": 40,
            "proximity_distance_meters": 0,
            "trip_session": {"s": 1000, "d": 550},
            "trip_age_seconds": 180,
            "vehicle_min_connection_minutes": 2,
            "vehicle_min_approach_meters": 300,
            "vehicle_max_trip_minutes": 90,
            "vehicle_nearby_meters": 0,
        }
        self.assertEqual(self.render("arrival_match", **base), "True")
        self.assertEqual(self.render("arrival_match", **(
            base | {"trip_age_seconds": 30})), "False")
        self.assertEqual(self.render("arrival_match", **(
            base | {"trip_session": {"s": 1000, "d": 140}})), "False")
        self.assertEqual(self.render("arrival_match", **(
            base | {"car_connected": False})), "False")
        self.assertEqual(self.render("arrival_match", **(
            base | {"gps_ready": False})), "False")
        self.assertEqual(self.render("arrival_match", **(
            base | {"trip_age_seconds": 10000})), "False")
        self.assertEqual(self.render("arrival_match", **(
            base | {"vehicle_nearby_meters": 25})), "False")
        self.assertEqual(self.render("arrival_match", **(
            base | {"trigger": SimpleNamespace(
                id="vehicle_approach", to_state=SimpleNamespace(state="towards"))})), "False")

    def test_gps_accuracy_is_configurable_and_fresh(self):
        import datetime

        updated = datetime.datetime.fromtimestamp(
            10000, datetime.timezone.utc,
        )
        tracker = SimpleNamespace(
            state="home", last_updated=updated,
            attributes={
                "latitude": 52.52, "longitude": 13.405,
                "gps_accuracy": 18,
            },
        )
        base = {
            "states": {"device_tracker.phone": tracker},
            "vehicle_gps_tracker": "device_tracker.phone",
            "vehicle_max_gps_accuracy_meters": 25,
            "timestamp_now": 10050,
            "as_timestamp": lambda val, default=0: val.timestamp(),
            "is_number": lambda n: isinstance(n, (int, float)),
        }
        self.assertEqual(self.render("gps_ready", **base), "True")
        self.assertEqual(self.render("gps_ready", **(
            base | {"vehicle_max_gps_accuracy_meters": 10})), "False")
        self.assertEqual(self.render("gps_ready", **(
            base | {"timestamp_now": 10500})), "False")
        tracker.attributes.pop("gps_accuracy")
        self.assertEqual(self.render("gps_ready", **base), "False")

    def test_proximity_distance_units_and_towards_state(self):
        base = {
            "vehicle_proximity_distance": "sensor.driver_distance",
            "vehicle_ha_distance_unit": "km",
            "states": lambda eid: "0.65",
            "is_number": lambda s: True,
        }
        self.assertEqual(float(self.render("proximity_distance_meters", **base)), 650.0)
        self.assertAlmostEqual(float(self.render("proximity_distance_meters", **(
            base | {"vehicle_ha_distance_unit": "mi"}))), 1046.1, delta=0.2)
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
            "vehicle_bluetooth_changed", "vehicle_distance_changed",
            "vehicle_android_auto_changed",
            "deadline_changed", "minute_check", "mobile_action", "startup",
        })
        for trigger in self.data["triggers"]:
            if trigger["id"] in {
                "calendar_open", "schedule_open", "custom_open", "vehicle_approach",
                "vehicle_bluetooth_changed", "vehicle_distance_changed",
                "vehicle_android_auto_changed",
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
        self.assertIn("safety_sensor in ['', none]", source)
        self.assertIn("states(safety_sensor) == safe_state", source)
        self.assertNotIn("close_without_clearance_sensor", source)
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
            "input_text.set_value", "notify.send_message",
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
        self.assertIn("conditions: !input calendar_open_conditions", source)
        self.assertIn("is_state(calendar_home_person, 'home')", source)
        self.assertIn("trip_session.get('s', 0)", source)
        self.assertIn("trip_session.get('d', 0)", source)
        self.assertIn("input_text.garage_arrival_trip_placeholder", source)
        self.assertIn("action: notify.send_message", source)


if __name__ == "__main__":
    unittest.main()
