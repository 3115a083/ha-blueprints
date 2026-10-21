"""Static and Jinja behavior tests for the Sunrise Alarm blueprint.

These tests do not replace validation on a running Home Assistant instance.
"""
from __future__ import annotations

import datetime as dt
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

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
        precise_offset="-00:30:00",
        home=True,
        sun="below_horizon",
        require_dark=True,
        mode="linear",
        duration=30,
        update_seconds=30,
        finish_by_alarm=True,
        post_alarm_minutes=0,
        alarm_last_changed=None,
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

        class StatesView:
            def __call__(self, entity):
                return entity_states.get(entity, "unknown")

            def __getitem__(self, entity):
                changed = dt.datetime.fromisoformat(
                    alarm_last_changed or current
                )
                return SimpleNamespace(
                    state=entity_states.get(entity, "unknown"),
                    last_changed=changed,
                )

        scope = {
            "alarm_sensor_id": "sensor.alarm",
            "wake_person": "person.user",
            "lead_minutes": lead,
            "precise_start_enabled": False,
            "precise_start_offset": precise_offset,
            "weekday_selection": weekday_selection,
            "require_dark": require_dark,
            "brightness_mode": mode,
            "initial_brightness": 1,
            "target_brightness": 85,
            "ramp_minutes": duration,
            "update_seconds": update_seconds,
            "finish_by_alarm": finish_by_alarm,
            "target_after_alarm_minutes": post_alarm_minutes,
            "trigger": {"id": "sunrise_start"},
            "now": lambda: now_time,
            "states": StatesView(),
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
        self.assertEqual(len(self.data["triggers"]), 3)
        self.assertEqual({t["id"] for t in self.data["triggers"]},
                         {"sunrise_start", "sunrise_precise", "alarm_time"})
        self.assertEqual(
            next(t for t in self.data["triggers"] if t["id"] == "alarm_time")["at"],
            "!input alarm_sensor",
        )

    def test_input_references_and_ui_sections(self):
        references = set(re.findall(r"!input\s+(\w+)", self.source))
        self.assertFalse(references - set(self.inputs))
        groups = self.data["blueprint"]["input"]
        self.assertEqual(list(groups), ["alarm", "light", "extra_actions", "safety", "precision"])
        self.assertTrue(groups["extra_actions"]["collapsed"])
        self.assertTrue(groups["safety"]["collapsed"])
        self.assertTrue(groups["precision"]["collapsed"])
        self.assertFalse(groups["alarm"].get("collapsed", False))
        self.assertFalse(groups["light"].get("collapsed", False))
        for group in ("extra_actions", "safety", "precision"):
            for key, spec in groups[group]["input"].items():
                self.assertIn("default", spec, key)
        self.assertIn("entity", self.inputs["alarm_sensor"]["selector"])
        self.assertIn("target", self.inputs["lights_target"]["selector"])
        self.assertIn("action", self.inputs["alarm_time_actions"]["selector"])
        self.assertEqual(self.inputs["weekday_selection"]["default"], "all")
        self.assertFalse(self.inputs["precise_start_enabled"]["default"])
        self.assertEqual(self.inputs["precise_start_offset"]["default"], "-00:30:00")
        self.assertTrue(self.inputs["finish_by_alarm"]["default"])
        self.assertIn("finish_by_alarm", self.data["variables"])
        self.assertEqual(self.inputs["target_after_alarm_minutes"]["default"], 0)
        self.assertIn("target_after_alarm_minutes", self.data["variables"])

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

    def test_event_driven_sunrise_trigger_instead_of_polling(self):
        """Time-dependent template fires on false -> true, not every 15 seconds."""
        sunrise = next(t for t in self.data["triggers"] if t["id"] == "sunrise_start")
        self.assertEqual(sunrise["trigger"], "template")
        self.assertIn("_precise_start_enabled", sunrise["enabled"])
        self.assertIn("_precise_start_offset", sunrise["enabled"])
        self.assertIn("_lead_minutes", sunrise["enabled"])
        self.assertNotIn("seconds", sunrise)
        self.assertFalse(any(t["trigger"] == "time_pattern" for t in self.data["triggers"]))
        self.assertIn("now()", sunrise["value_template"])
        self.assertIn("states(_alarm_sensor)", sunrise["value_template"])
        self.assertIn("_lead_minutes", sunrise["value_template"])
        self.assertEqual(self.data["trigger_variables"]["_alarm_sensor"], "!input alarm_sensor")
        self.assertEqual(self.data["trigger_variables"]["_lead_minutes"], "!input lead_minutes")
        self.assertEqual(self.data["trigger_variables"]["_precise_start_enabled"], "!input precise_start_enabled")
        self.assertEqual(self.data["trigger_variables"]["_precise_start_offset"], "!input precise_start_offset")

        def evaluated(current, alarm="2026-10-12T07:00:00+00:00", lead=30):
            scope = self.context(current=current, alarm=alarm, lead=lead)
            scope["_alarm_sensor"] = "sensor.alarm"
            scope["_lead_minutes"] = lead
            scope["_precise_start_enabled"] = False
            return self.truthy(self.render(sunrise["value_template"], scope))

        self.assertFalse(evaluated("2026-10-12T06:29:59+00:00"))
        self.assertTrue(evaluated("2026-10-12T06:30:00+00:00"))
        self.assertTrue(evaluated("2026-10-12T06:30:59+00:00"))
        self.assertFalse(evaluated("2026-10-12T06:31:00+00:00"))
        self.assertTrue(evaluated("2026-10-12T06:40:01+00:00", lead=20))
        self.assertFalse(evaluated("2026-10-12T06:30:01+00:00", alarm="unavailable"))

    def test_native_precise_offset_scheduled_event_without_clock_scan(self):
        """Native time trigger observes the timestamp sensor and exact configured offset."""
        sunrise = next(t for t in self.data["triggers"] if t["id"] == "sunrise_precise")
        self.assertEqual(sunrise["trigger"], "time")
        self.assertIn("_precise_start_enabled", sunrise["enabled"])
        self.assertIn("_precise_start_offset", sunrise["enabled"])
        self.assertIn("_lead_minutes", sunrise["enabled"])
        self.assertEqual(sunrise["at"]["entity_id"], "!input alarm_sensor")
        self.assertEqual(sunrise["at"]["offset"], "!input precise_start_offset")
        self.assertFalse(any(t["trigger"] == "time_pattern" for t in self.data["triggers"]))

        choose = self.data["actions"][-1]["choose"][0]
        condition = choose["conditions"][0]["value_template"]
        ctx = self.context(current="2026-10-12T06:30:00+00:00")
        ctx["trigger"] = {"id": "sunrise_precise"}
        ctx["precise_start_enabled"] = True
        self.assertTrue(self.truthy(self.render(condition, ctx)))
        ctx["precise_start_enabled"] = False
        self.assertFalse(self.truthy(self.render(condition, ctx)))

    def test_precise_mode_disables_minute_template_path(self):
        """Only one start trigger is enabled for each lead/offset pair."""
        native = next(t for t in self.data["triggers"] if t["id"] == "sunrise_precise")
        fallback = next(t for t in self.data["triggers"] if t["id"] == "sunrise_start")

        def enabled(lead, offset, precise):
            ctx = {
                "_lead_minutes": lead,
                "_precise_start_offset": offset,
                "_precise_start_enabled": precise,
            }
            return (
                self.truthy(self.render(native["enabled"], ctx)),
                self.truthy(self.render(fallback["enabled"], ctx)),
            )

        self.assertEqual(enabled(30, "-00:30:00", True), (True, False))
        self.assertEqual(enabled(30, "-00:10:30", True), (True, False))
        self.assertEqual(enabled(30, "00:00:00", True), (True, False))
        self.assertEqual(enabled(30, "-00:30:00", False), (False, True))
        # Core regression: five-minute lead must not become thirty minutes.
        self.assertEqual(enabled(5, "-00:30:00", True), (False, True))
        self.assertEqual(enabled(5, "-01:00:00", True), (False, True))
        self.assertEqual(enabled(30, "00:10:00", True), (False, True))

    def test_mismatched_precise_offset_never_starts_light_early(self):
        """Two independent values used to allow waking 25 minutes too early."""
        branch = self.data["actions"][-1]["choose"][0]
        condition = branch["conditions"][0]["value_template"]

        early = self.context(
            lead=5, precise_offset="-00:30:00",
            current="2026-10-12T06:30:00+00:00",
        )
        early["precise_start_enabled"] = True
        early["trigger"] = {"id": "sunrise_precise"}
        self.assertFalse(self.truthy(self.render(condition, early)))

        fallback = self.context(
            lead=5, precise_offset="-00:30:00",
            current="2026-10-12T06:55:00+00:00",
        )
        fallback["precise_start_enabled"] = True
        fallback["trigger"] = {"id": "sunrise_start"}
        self.assertTrue(self.truthy(self.render(condition, fallback)))

        too_soon = self.context(
            lead=30, precise_offset="-00:30:00",
            current="2026-10-12T06:15:00+00:00",
        )
        too_soon["precise_start_enabled"] = True
        too_soon["trigger"] = {"id": "sunrise_precise"}
        self.assertFalse(self.truthy(self.render(condition, too_soon)))

    def test_precise_start_requires_correct_alarm_timestamp(self):
        """Do not trust trigger ID alone when alarm sensor moves or reloads."""
        check = self.data["actions"][-1]["choose"][0]["conditions"][0]["value_template"]
        ctx = self.context(
            lead=30, precise_offset="-00:10:00",
            current="2026-10-12T06:50:00+00:00",
        )
        ctx["precise_start_enabled"] = True
        ctx["trigger"] = {"id": "sunrise_precise"}
        self.assertTrue(self.truthy(self.render(check, ctx)))

        for current in ("2026-10-12T06:20:00+00:00",
                        "2026-10-12T06:49:30+00:00",
                        "2026-10-12T06:52:00+00:00"):
            stale = self.context(
                lead=30, precise_offset="-00:10:00", current=current,
            )
            stale["precise_start_enabled"] = True
            stale["trigger"] = {"id": "sunrise_precise"}
            self.assertFalse(self.truthy(self.render(check, stale)))

        changed = self.context(
            alarm="2026-10-12T09:00:00+00:00",
            lead=30, precise_offset="-00:10:00",
            current="2026-10-12T06:50:00+00:00",
        )
        changed["precise_start_enabled"] = True
        changed["trigger"] = {"id": "sunrise_precise"}
        self.assertFalse(self.truthy(self.render(check, changed)))

    def test_before_alarm_window_and_darkness(self):
        branch = self.data["actions"][-1]["choose"][0]
        template = branch["conditions"][0]["value_template"]
        self.assertTrue(self.truthy(self.render(template, self.context())))
        self.assertFalse(self.truthy(self.render(
            template, self.context(current="2026-10-12T06:29:59+00:00")
        )))
        self.assertTrue(self.truthy(self.render(
            template, self.context(current="2026-10-12T06:30:59+00:00")
        )))
        self.assertFalse(self.truthy(self.render(
            template, self.context(current="2026-10-12T06:31:00+00:00")
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
        light_branch = branch["sequence"][4]["parallel"][1]["sequence"]
        repeat = light_branch[0]["default"][1]["repeat"]
        step_template = repeat["sequence"][2]["data"]["brightness_pct"]
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

    def fade_parameters(self, **context_options):
        branch = self.data["actions"][-1]["choose"][0]
        scope = self.context(**context_options)
        for block in branch["sequence"][:4]:
            for name, template in block["variables"].items():
                scope[name] = self.render(template, scope)
        return scope

    def test_ramp_duration_and_instant_mode(self):
        branch = self.data["actions"][-1]["choose"][0]
        c = self.fade_parameters(
            current="2026-10-12T06:30:00+00:00",
            duration=30, lead=30, update_seconds=30,
        )
        self.assertEqual(int(c["effective_ramp_seconds"]), 1800)
        self.assertEqual(int(c["total_steps"]), 60)
        self.assertEqual(int(float(c["interval_seconds"])), 30)
        self.assertEqual(int(c["total_steps"]) * int(float(c["interval_seconds"])), 1800)
        choice = branch["sequence"][4]["parallel"][1]["sequence"][0]["choose"][0]
        self.assertIn("instant", choice["conditions"][0]["value_template"])
        self.assertEqual(choice["sequence"][0]["action"], "light.turn_on")

    def test_short_lead_compresses_fade_to_finish_at_alarm(self):
        """Five minute lead must not leave light at 15-20% after a 30-minute fade."""
        c = self.fade_parameters(
            current="2026-10-12T06:55:00+00:00",
            lead=5, duration=30, update_seconds=30,
        )
        self.assertEqual(int(c["seconds_until_alarm"]), 300)
        self.assertEqual(int(c["requested_ramp_seconds"]), 1800)
        self.assertEqual(int(c["effective_ramp_seconds"]), 300)
        self.assertEqual(int(c["total_steps"]), 10)
        self.assertEqual(int(float(c["interval_seconds"])), 30)

        branch = self.data["actions"][-1]["choose"][0]
        repeat = branch["sequence"][4]["parallel"][1]["sequence"][0]["default"][1]["repeat"]
        steps = repeat["sequence"]
        self.assertEqual(steps[0]["delay"]["seconds"], "{{ interval_seconds | float }}")
        self.assertEqual(steps[1]["condition"], "template")
        self.assertEqual(steps[2]["action"], "light.turn_on")
        self.assertEqual(set(steps[2]["data"]), {"brightness_pct"})
        self.assertNotIn("transition", str(steps[2]))
        values = []
        for n in range(1, int(c["total_steps"]) + 1):
            sample = {**c, "safe_start": "1", "repeat": {"index": n}}
            values.append(int(self.render(steps[2]["data"]["brightness_pct"], sample)))
        self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))
        self.assertEqual(values[-1], 85)
        self.assertGreater(values[4], 1)

    def test_can_opt_out_of_finishing_by_alarm(self):
        c = self.fade_parameters(
            current="2026-10-12T06:55:00+00:00",
            lead=5, duration=30, finish_by_alarm=False,
        )
        self.assertEqual(int(c["effective_ramp_seconds"]), 1800)
        self.assertEqual(int(c["total_steps"]), 60)

    def test_no_time_left_uses_immediate_target_instead_of_dim_start(self):
        branch = self.data["actions"][-1]["choose"][0]
        condition = branch["sequence"][4]["parallel"][1]["sequence"][0]["choose"][0]["conditions"][0]["value_template"]
        c = self.fade_parameters(current="2026-10-12T07:00:00+00:00", lead=0)
        self.assertEqual(int(c["effective_ramp_seconds"]), 0)
        self.assertTrue(self.truthy(self.render(condition, c)))
        self.assertEqual(int(c["target_brightness"]), 85)

    def test_phone_next_alarm_rollover_does_not_abort_last_step(self):
        branch = self.data["actions"][-1]["choose"][0]
        light = branch["sequence"][4]["parallel"][1]["sequence"]
        guard = light[0]["default"][1]["repeat"]["sequence"][1]["value_template"]
        c = self.context(
            alarm="2026-10-13T07:00:00+00:00",
            current="2026-10-12T07:00:00+00:00",
        )
        c["anchor_alarm_timestamp"] = str(
            dt.datetime.fromisoformat("2026-10-12T07:00:00+00:00").timestamp()
        )
        c["fade_end_timestamp"] = str(float(c["anchor_alarm_timestamp"]) + 60)
        self.assertTrue(self.truthy(self.render(guard, c)))
        early = self.context(
            alarm="2026-10-13T07:00:00+00:00",
            current="2026-10-12T06:45:00+00:00",
        )
        early["anchor_alarm_timestamp"] = c["anchor_alarm_timestamp"]
        self.assertFalse(self.truthy(self.render(guard, early)))

    def test_post_alarm_target_override_delays_full_brightness(self):
        """The user chooses the *completion time*, not just a maximum fade."""
        for delay in (5, 10, 20, 60):
            with self.subTest(post_alarm_minutes=delay):
                c = self.fade_parameters(
                    current="2026-10-12T06:55:00+00:00",
                    lead=5, duration=3, finish_by_alarm=True,
                    post_alarm_minutes=delay, update_seconds=30,
                )
                planned = (5 + delay) * 60
                self.assertEqual(int(c["effective_ramp_seconds"]), planned)
                self.assertEqual(int(c["total_steps"]), planned // 30)
                expected_end = dt.datetime.fromisoformat(
                    "2026-10-12T07:00:00+00:00"
                ).timestamp() + delay * 60
                self.assertAlmostEqual(float(c["fade_end_timestamp"]), expected_end)

                branch = self.data["actions"][-1]["choose"][0]
                light = branch["sequence"][4]["parallel"][1]["sequence"]
                choice = light[0]["choose"][0]["conditions"][0]["value_template"]
                self.assertFalse(self.truthy(self.render(choice, c)))
                ramp = light[0]["default"][1]["repeat"]
                values = []
                for index in range(1, int(c["total_steps"]) + 1):
                    ctx = {**c, "safe_start": "1", "repeat": {"index": index}}
                    values.append(int(self.render(
                        ramp["sequence"][2]["data"]["brightness_pct"], ctx
                    )))
                self.assertLess(values[5], 85)
                self.assertEqual(values[-1], 85)

    def test_zero_post_alarm_offset_preserves_existing_scheduling(self):
        c = self.fade_parameters(
            current="2026-10-12T06:55:00+00:00",
            lead=5, duration=30, post_alarm_minutes=0,
        )
        self.assertEqual(int(c["effective_ramp_seconds"]), 300)
        self.assertTrue(c["finish_by_alarm"])
        explicit = self.fade_parameters(
            current="2026-10-12T06:55:00+00:00",
            lead=5, duration=30, finish_by_alarm=False,
            post_alarm_minutes=0,
        )
        self.assertEqual(int(explicit["effective_ramp_seconds"]), 1800)

    def test_post_alarm_fade_survives_phone_rollover_after_ten_minutes(self):
        """Do not cancel at +60 s when target is scheduled at +15 min."""
        current = "2026-10-12T07:10:00+00:00"
        yesterday_alarm = dt.datetime.fromisoformat(
            "2026-10-12T07:00:00+00:00"
        ).timestamp()
        c = self.context(
            alarm="2026-10-13T07:00:00+00:00", current=current,
            alarm_last_changed="2026-10-12T07:00:00+00:00",
            post_alarm_minutes=15,
        )
        c["anchor_alarm_timestamp"] = str(yesterday_alarm)
        c["fade_end_timestamp"] = str(yesterday_alarm + 15 * 60)
        ramp = self.data["actions"][-1]["choose"][0]["sequence"][4]["parallel"][1]["sequence"][0]["default"][1]["repeat"]
        guard = ramp["sequence"][1]["value_template"]
        self.assertTrue(self.truthy(self.render(guard, c)))
        completion = self.data["actions"][-1]["choose"][0]["sequence"][4]["parallel"][1]["sequence"][1]["if"][0]["value_template"]
        self.assertTrue(self.truthy(self.render(completion, c)))

        too_late = self.context(
            alarm="2026-10-13T07:00:00+00:00",
            current="2026-10-12T07:17:00+00:00",
            alarm_last_changed="2026-10-12T07:00:00+00:00",
        )
        too_late["anchor_alarm_timestamp"] = str(yesterday_alarm)
        too_late["fade_end_timestamp"] = str(yesterday_alarm + 15 * 60)
        self.assertFalse(self.truthy(self.render(guard, too_late)))

    def test_changed_alarm_early_stops_post_alarm_fade(self):
        original = dt.datetime.fromisoformat(
            "2026-10-12T07:00:00+00:00"
        ).timestamp()
        changed = self.context(
            alarm="2026-10-13T07:00:00+00:00",
            current="2026-10-12T07:05:00+00:00",
            alarm_last_changed="2026-10-12T06:45:00+00:00",
            post_alarm_minutes=15,
        )
        changed["anchor_alarm_timestamp"] = str(original)
        changed["fade_end_timestamp"] = str(original + 15 * 60)
        guard = self.data["actions"][-1]["choose"][0]["sequence"][4]["parallel"][1]["sequence"][0]["default"][1]["repeat"]["sequence"][1]["value_template"]
        self.assertFalse(self.truthy(self.render(guard, changed)))

    def test_delay_less_than_update_interval_still_waits_until_post_alarm_goal(self):
        # With the post-alarm setting, a short fade is not switched to instant.
        c = self.fade_parameters(
            current="2026-10-12T07:00:00+00:00", lead=0,
            post_alarm_minutes=1, update_seconds=120,
        )
        self.assertEqual(int(c["effective_ramp_seconds"]), 60)
        self.assertEqual(int(c["total_steps"]), 1)
        condition = self.data["actions"][-1]["choose"][0]["sequence"][4]["parallel"][1]["sequence"][0]["choose"][0]["conditions"][0]["value_template"]
        self.assertFalse(self.truthy(self.render(condition, c)))
        self.assertEqual(float(c["interval_seconds"]), 60.0)

    def test_additional_action_slots_and_parallel_alarm(self):
        branch = self.data["actions"][-1]["choose"][0]
        concurrent = branch["sequence"][4]["parallel"]
        self.assertEqual(concurrent[0]["sequence"], "!input sunrise_start_actions")
        self.assertIn("!input sunrise_complete_actions", str(concurrent[1]))
        alarm_branch = self.data["actions"][-1]["choose"][1]
        self.assertEqual(alarm_branch["sequence"], "!input alarm_time_actions")
        self.assertIn("alarm_time", alarm_branch["conditions"][0]["value_template"])
        self.assertNotIn("require_dark", alarm_branch["conditions"][0]["value_template"])
        self.assertIn("!input extra_conditions", str(alarm_branch["conditions"]))

    def test_changed_alarm_or_departure_aborts_gradual_fade(self):
        branch = self.data["actions"][-1]["choose"][0]
        light_branch = branch["sequence"][4]["parallel"][1]["sequence"]
        check = light_branch[0]["default"][1]["repeat"]["sequence"][1]["value_template"]
        c = self.context()
        c["anchor_alarm_timestamp"] = str(
            dt.datetime.fromisoformat("2026-10-12T07:00:00+00:00").timestamp()
        )
        c["fade_end_timestamp"] = c["anchor_alarm_timestamp"]
        self.assertTrue(self.truthy(self.render(check, c)))
        c["anchor_alarm_timestamp"] = "123456789"
        c["fade_end_timestamp"] = "123456789"
        self.assertFalse(self.truthy(self.render(check, c)))
        c = self.context(home=False)
        c["anchor_alarm_timestamp"] = str(
            dt.datetime.fromisoformat("2026-10-12T07:00:00+00:00").timestamp()
        )
        c["fade_end_timestamp"] = c["anchor_alarm_timestamp"]
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
