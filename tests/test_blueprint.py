"""Offline validation of the occupancy blueprint. No Home Assistant runtime required."""
from __future__ import annotations

import datetime as dt
import re
import unittest
from pathlib import Path

import jinja2
import yaml

BLUEPRINT = Path(__file__).resolve().parents[1] / "blueprints/automation/occupancy/area_occupancy_manager.yaml"


class InputLoader(yaml.SafeLoader):
    pass


InputLoader.add_constructor("!input", lambda loader, node: ("!input " + loader.construct_scalar(node)))


class Entity:
    def __init__(self, state: str, age_minutes: int, now: dt.datetime):
        self.state = state
        self.last_changed = now - dt.timedelta(minutes=age_minutes)


class States:
    def __init__(self, entities: dict[str, Entity]):
        self.entities = entities

    def __getitem__(self, entity_id: str):
        return self.entities.get(entity_id)

    def __call__(self, entity_id: str):
        return self.entities.get(entity_id, Entity("unknown", 0, dt.datetime.now(dt.timezone.utc))).state


class BlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BLUEPRINT.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.text, Loader=InputLoader)
        cls.inputs = {
            name: spec
            for section in cls.data["blueprint"]["input"].values()
            for name, spec in section["input"].items()
        }
        cls.env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        cls.env.filters["bool"] = lambda v: str(v).lower() in ("true", "1", "on")

    def test_required_blueprint_structure(self):
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2024.10.0")
        self.assertEqual(self.data["mode"], "parallel")
        self.assertNotIn("default", self.inputs["occupancy_helper"])
        for name, spec in self.inputs.items():
            if name != "occupancy_helper":
                self.assertIn("default", spec, name)

    def test_all_blueprint_references_exist(self):
        references = re.findall(r"!input\s+([\w]+)", self.text)
        self.assertTrue(references)
        self.assertEqual(set(references) - set(self.inputs), set())

    def test_template_syntax(self):
        def visit(value):
            if isinstance(value, dict):
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, str) and ("{{" in value or "{%" in value):
                self.env.parse(value)

        visit(self.data)

    def test_status_listeners_and_user_trigger_lists(self):
        ids = [trigger.get("id") for trigger in self.data["triggers"]]
        self.assertIn("became_away", ids)
        self.assertIn("became_home", ids)
        self.assertIn("reconcile", ids)
        self.assertEqual(
            [t["triggers"] for t in self.data["triggers"] if "triggers" in t],
            ["!input extra_away_triggers", "!input extra_home_triggers"],
        )

    def evaluate(
        self,
        *,
        trackers: dict[str, tuple[str, int]] | None = None,
        activity: dict[str, tuple[str, int]] | None = None,
        blockers: dict[str, tuple[str, int]] | None = None,
        guest: str = "off",
        policy: str = "all",
        trigger: str = "tracker_away",
    ) -> dict:
        now = dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc)
        trackers = trackers or {}
        activity = activity or {}
        blockers = blockers or {}
        entities = {
            e: Entity(state, age, now)
            for d in (trackers, activity, blockers)
            for e, (state, age) in d.items()
        }
        entities["input_boolean.guests"] = Entity(guest, 1, now)
        states = States(entities)
        context = {
            "tracked_entities": list(trackers),
            "activity_sensors": list(activity),
            "blocking_sensors": list(blockers),
            "guest_mode": "input_boolean.guests",
            "tracked_away_minutes": 3,
            "inactive_minutes": 20,
            "evidence_policy": policy,
            "trigger": {"id": trigger},
            "states": states,
            "now": lambda: now,
            "as_timestamp": lambda x, default=0: x.timestamp() if hasattr(x, "timestamp") else default,
            "is_state": lambda e, wanted: states(e) == wanted,
            "expand": lambda entities: [states.entities[e] for e in entities if e in states.entities],
        }
        var_blocks = [action["variables"] for action in self.data["actions"] if "variables" in action]
        for block in var_blocks:
            for key, template in block.items():
                context[key] = self.env.from_string(template).render(**context).strip()
        return context

    @staticmethod
    def true(value):
        return str(value).lower() == "true"

    def test_vacancy_with_confirmed_absence(self):
        c = self.evaluate(
            trackers={"person.a": ("not_home", 10)},
            activity={"binary_sensor.motion": ("off", 30)},
            blockers={"binary_sensor.bed": ("off", 2)},
        )
        self.assertTrue(self.true(c["absence_evidence_ok"]))
        self.assertTrue(self.true(c["known_trackers_safe"]))
        self.assertTrue(self.true(c["activity_clear"]))
        self.assertTrue(self.true(c["blockers_clear"]))

    def test_someone_home_blocks_departure_even_in_any_mode(self):
        c = self.evaluate(
            trackers={"person.a": ("not_home", 10), "person.b": ("home", 40)},
            activity={"binary_sensor.motion": ("off", 30)},
            policy="any",
        )
        self.assertTrue(self.true(c["absence_evidence_ok"]))
        self.assertFalse(self.true(c["known_trackers_safe"]))

    def test_unknown_tracker_blocks_departure_even_in_any_mode(self):
        c = self.evaluate(
            trackers={"person.a": ("unavailable", 20)},
            activity={"binary_sensor.motion": ("off", 30)},
            policy="any",
        )
        self.assertFalse(self.true(c["known_trackers_safe"]))

    def test_active_or_unknown_motion_blocks_departure(self):
        for state in ("on", "unknown", "unavailable"):
            with self.subTest(state=state):
                c = self.evaluate(
                    trackers={"person.a": ("not_home", 10)},
                    activity={"binary_sensor.motion": (state, 30)},
                    policy="any",
                )
                self.assertFalse(self.true(c["activity_clear"]))

    def test_presence_blocker_disallows_away(self):
        for state in ("on", "unavailable"):
            with self.subTest(state=state):
                c = self.evaluate(
                    trackers={"person.a": ("not_home", 10)},
                    blockers={"binary_sensor.guestroom": (state, 10)},
                )
                self.assertFalse(self.true(c["blockers_clear"]))

    def test_guest_switch_must_be_off(self):
        c = self.evaluate(trackers={"person.a": ("not_home", 10)}, guest="on")
        auto_away = self.data["actions"][-1]["choose"][-1]
        template = next(
            item["value_template"] for item in auto_away["conditions"]
            if item.get("value_template", "").startswith("{{ guest_mode")
        )
        self.assertEqual(self.env.from_string(template).render(**c).strip(), "False")

    def test_minimum_durations_in_all_mode(self):
        c = self.evaluate(
            trackers={"person.a": ("not_home", 1)},
            activity={"binary_sensor.motion": ("off", 12)},
        )
        self.assertFalse(self.true(c["absence_evidence_ok"]))

    def test_custom_trigger_no_builtin_sources(self):
        c = self.evaluate(trigger="custom_away")
        self.assertTrue(self.true(c["absence_evidence_ok"]))


if __name__ == "__main__":
    unittest.main()
