"""Static and Jinja behavior tests for the Sunrise Alarm blueprint.

These tests do not replace validation on a running Home Assistant instance.
"""
from __future__ import annotations

import datetime as dt
import re
import unittest
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/automation/alarm_light/alarm_light.yaml"


class BlueprintLoader(yaml.SafeLoader):
    pass


BlueprintLoader.add_constructor(
    "!input", lambda loader, node: "!input " + loader.construct_scalar(node)
)


class AlarmLightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BLUEPRINT.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.source, Loader=BlueprintLoader)
        cls.inputs = {
            name: config
            for group in cls.data["blueprint"]["input"].values()
            for name, config in group["input"].items()
        }
        cls.env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        cls.env.filters["bool"] = lambda value: str(value).lower() in ("true", "yes", "1", "on")

    @staticmethod
    def truthy(value):
        return str(value).strip().lower() == "true"

    def render(self, text, context):
        return self.env.from_string(text).render(**context).strip()

    def context(
        self,
        *,
        alarm="2026-10-12T07:00:00+00:00",
        current="2026-10-12T06:30:01+00:00",
        weekday_selection="all",
        lead=30,
        home=True,
        sun="below_horizon",
        require_dark=True,
        mode="linear",
        duration=30,
        update_seconds=30,
    ):
        now_time = dt.datetime.fromisoformat(current)
        entity_states = {
            "sensor.alarm": alarm,
            "person.user": "home" if home else "not_home",
            "sun.sun": sun,
        }

        def timestamp(value, default=0):
            try:
                if isinstance(value, (float, int)):
                    return float(value)
                if isinstance(value, dt.datetime):
                    return value.timestamp()
                return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError, OverflowError):
                return default

        scope = {
            "alarm_sensor_id": "sensor.alarm",
            "wake_person": "person.user",
            "lead_minutes": lead,
            "weekday_selection": weekday_selection,
            "require_dark": require_dark,
            "brightness_mode": mode,
            "initial_brightness": 1,
            "target_brightness": 85,
            "ramp_minutes": duration,
            "update_seconds": update_seconds,
            "trigger": {"id": "sunrise_start"},
            "now": lambda: now_time,
            "states": lambda entity: entity_states.get(entity, "unknown"),
            "as_timestamp": timestamp,
            "as_datetime": lambda string: dt.datetime.fromisoformat(
                string.replace("Z", "+00:00")
            ),
            "as_local": lambda timestamp_value: timestamp_value.astimezone(dt.timezone.utc),
            "is_state": lambda entity, expected: entity_states.get(entity) == expected,
        }
        for action in self.data["actions"]:
            if "variables" not in action:
                continue
            for key, value in action["variables"].items():
                scope[key] = self.render(value, scope) if isinstance(value, str) else value
        return scope

    def test_modern_blueprint_schema(self):
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2024.10.0")
        self.assertEqual(self.data["mode"], "parallel")
        self.assertIn("source_url", self.data["blueprint"])
        for key in ("triggers", "actions", "variables"):
            self.assertIn(key, self.data)
        for old_key in ("trigger", "condition", "action"):
            self.assertNotIn(old_key, self.data)
        self.assertEqual(len(self.data["triggers"]), 2)
        self.assertEqual({t["id"] for t in self.data["triggers"]}, {"sunrise_start", "alarm_time"})
        self.assertEqual(
            next(t for t in self.data["triggers"] if t["id"] == "alarm_time")["at"],
            "!input alarm_sensor",
        )

    def test_input_references_and_ui_sections(self):
        references = set(re.findall(r"!input\s+(\w+)", self.source))
        self.assertFalse(references - set(self.inputs))
        groups = self.data["blueprint"]["input"]
        self.assertEqual(list(groups), ["alarm", "light", "extra_actions", "safety"])
        self.assertTrue(groups["extra_actions"]["collapsed"])
        self.assertTrue(groups["safety"]["collapsed"])
        self.assertFalse(groups["alarm"].get("collapsed", False))
        self.assertFalse(groups["light"].get("collapsed", False))
        for group in ("extra_actions", "safety"):
            for key, spec in groups[group]["input"].items():
                self.assertIn("default", spec, key)
        self.assertIn("entity", self.inputs["alarm_sensor"]["selector"])
        self.assertIn("target", self.inputs["lights_target"]["selector"])
        self.assertIn("action", self.inputs["alarm_time_actions"]["selector"])
        self.assertEqual(self.inputs["weekday_selection"]["default"], "all")

    def test_every_jinja_template_parses(self):
        def visit(item):
            if isinstance(item, str) and ("{{" in item or "{%" in item):
                self.env.parse(item)
            elif isinstance(item, dict):
                for value in item.values():
                    visit(value)
            elif isinstance(item, list):
                for value in item:
                    visit(value)
        visit(self.data)

    def test_before_alarm_window_and_darkness(self):
        branch = self.data["actions"][-1]["choose"][0]
        template = branch["conditions"][0]["value_template"]
        self.assertTrue(self.truthy(self.render(template, self.context())))
        self.assertFalse(self.truthy(self.render(
            template, self.context(current="2026-10-12T06:29:59+00:00")
        )))
        self.assertFalse(self.truthy(self.render(
            template, self.context(current="2026-10-12T06:30:15+00:00")
        )))
        self.assertFalse(self.truthy(self.render(template, self.context(home=False))))
        self.assertFalse(self.truthy(self.render(template, self.context(sun="above_horizon"))))
        self.assertTrue(self.truthy(self.render(
            template, self.context(sun="above_horizon", require_dark=False)
        )))
        self.assertTrue(self.truthy(self.render(
            template, self.context(current="2026-10-12T06:40:01+00:00", lead=20)
        )))

    def test_weekday_uses_alarm_day_even_when_sunrise_begins_prior_day(self):
        context = self.context(
            alarm="2026-10-12T00:10:00+00:00",  # Monday
            current="2026-10-11T23:40:02+00:00",  # Sunday
            weekday_selection="weekdays",
        )
        self.assertEqual(context["alarm_weekday"], "0")
        self.assertTrue(self.truthy(context["active_weekday"]))
        self.assertTrue(self.truthy(self.render(
            self.data["actions"][-1]["choose"][0]["conditions"][0]["value_template"],
            context,
        )))
        context_weekends = self.context(
            alarm="2026-10-12T00:10:00+00:00",
            current="2026-10-11T23:40:02+00:00",
            weekday_selection="weekends",
        )
        self.assertFalse(self.truthy(context_weekends["active_weekday"]))

    def test_linear_and_ease_in_curves(self):
        branch = self.data["actions"][-1]["choose"][0]
        light_branch = branch["sequence"][2]["parallel"][1]["sequence"]
        repeat = light_branch[0]["default"][1]["repeat"]
        step_template = repeat["sequence"][1]["data"]["brightness_pct"]
        results = {}
        for curve in ("linear", "ease_in"):
            values = []
            for step in (1, 10, 20):
                c = self.context(mode=curve)
                c["safe_start"] = "1"
                c["total_steps"] = "20"
                c["repeat"] = {"index": step}
                values.append(int(self.render(step_template, c)))
            results[curve] = values
        self.assertLess(results["ease_in"][0], results["linear"][0])
        self.assertLess(results["ease_in"][1], results["linear"][1])
        self.assertEqual(results["linear"][-1], 85)
        self.assertEqual(results["ease_in"][-1], 85)

    def test_ramp_duration_and_instant_mode(self):
        branch = self.data["actions"][-1]["choose"][0]
        duration_variables = branch["sequence"][0]["variables"]
        interval_variables = branch["sequence"][1]["variables"]
        c = self.context(duration=30, update_seconds=30)
        for name, formula in duration_variables.items():
            c[name] = self.render(formula, c)
        for name, formula in interval_variables.items():
            c[name] = self.render(formula, c)
        self.assertEqual(int(c["total_steps"]), 60)
        self.assertEqual(int(c["interval_seconds"]), 30)
        self.assertEqual(int(c["total_steps"]) * int(c["interval_seconds"]), 1800)
        choice = branch["sequence"][2]["parallel"][1]["sequence"][0]["choose"][0]
        self.assertIn("instant", choice["conditions"][0]["value_template"])
        self.assertEqual(choice["sequence"][0]["action"], "light.turn_on")

    def test_additional_action_slots_and_parallel_alarm(self):
        branch = self.data["actions"][-1]["choose"][0]
        concurrent = branch["sequence"][2]["parallel"]
        self.assertEqual(concurrent[0]["sequence"], "!input sunrise_start_actions")
        self.assertIn("!input sunrise_complete_actions", str(concurrent[1]))
        alarm_branch = self.data["actions"][-1]["choose"][1]
        self.assertEqual(alarm_branch["sequence"], "!input alarm_time_actions")
        self.assertIn("alarm_time", alarm_branch["conditions"][0]["value_template"])
        self.assertNotIn("require_dark", alarm_branch["conditions"][0]["value_template"])
        self.assertIn("!input extra_conditions", str(alarm_branch["conditions"]))

    def test_changed_alarm_or_departure_aborts_gradual_fade(self):
        branch = self.data["actions"][-1]["choose"][0]
        light_branch = branch["sequence"][2]["parallel"][1]["sequence"]
        check = light_branch[0]["default"][1]["repeat"]["sequence"][0]["value_template"]
        c = self.context()
        c["anchor_alarm_timestamp"] = str(
            dt.datetime.fromisoformat("2026-10-12T07:00:00+00:00").timestamp()
        )
        self.assertTrue(self.truthy(self.render(check, c)))
        c["anchor_alarm_timestamp"] = "123456789"
        self.assertFalse(self.truthy(self.render(check, c)))
        c = self.context(home=False)
        c["anchor_alarm_timestamp"] = str(
            dt.datetime.fromisoformat("2026-10-12T07:00:00+00:00").timestamp()
        )
        self.assertFalse(self.truthy(self.render(check, c)))

    def test_documentation_and_catalog(self):
        local = BLUEPRINT.parent / "README.md"
        catalog = ROOT / "README.md"
        self.assertTrue(local.is_file())
        self.assertTrue(catalog.is_file())
        manual = local.read_text(encoding="utf-8")
        root = catalog.read_text(encoding="utf-8")
        self.assertIn("Linear", manual)
        self.assertIn("Ramp-up", manual)
        self.assertIn("Instant", manual)
        self.assertIn("alarm_light/README.md", root)


if __name__ == "__main__":
    unittest.main()
