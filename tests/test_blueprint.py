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
        sleep: str = "off",
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
        entities["input_boolean.sleep"] = Entity(sleep, 1, now)
        entities["input_boolean.area"] = Entity("on", 10, now)
        states = States(entities)
        context = {
            "tracked_entities": list(trackers),
            "activity_sensors": list(activity),
            "blocking_sensors": list(blockers),
            "guest_mode": "input_boolean.guests",
            "sleep_mode": "input_boolean.sleep",
            "occupancy_helper": "input_boolean.area",
            "diagnostics_text": "",
            "diagnostics_enabled": False,
            "diagnostics_log": False,
            "tracked_away_minutes": 3,
            "inactive_minutes": 20,
            "evidence_policy": policy,
            "trigger": {"id": trigger},
            "states": states,
            "now": lambda: now,
            "as_timestamp": lambda x, default=0: x.timestamp() if hasattr(x, "timestamp") else default,
            "is_state": lambda e, wanted: states(e) == wanted,
            "state_attr": lambda e, attr: None,
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

    def test_sleep_mode_blocks_away_and_reports_reason(self):
        for sleep_state in ("on", "unknown", "unavailable"):
            with self.subTest(state=sleep_state):
                c = self.evaluate(trackers={"person.a": ("not_home", 40)}, sleep=sleep_state)
                self.assertFalse(self.true(c["sleep_clear"]))
                self.assertIn("Sleep mode", c["diagnostic_line"])
        c = self.evaluate(trackers={"person.a": ("not_home", 40)}, sleep="off")
        self.assertTrue(self.true(c["sleep_clear"]))

    def test_sleep_mode_works_as_arrival_evidence(self):
        self.assertIn("sleep_home", {t.get("id") for t in self.data["triggers"]})
        c = self.evaluate(sleep="on")
        self.assertTrue(self.true(c["anyone_home_now"]))
        arrival = next(b for b in self.data["actions"][-1]["choose"] if b["alias"] == "Automatic arrival")
        self.assertIn("sleep_home", arrival["conditions"][0]["value_template"])
        away = self.data["actions"][-1]["choose"][-1]
        self.assertTrue(any("sleep_clear" in str(cond) for cond in away["conditions"]))

    def test_diagnosis_contains_blocker_reasons(self):
        c = self.evaluate(
            trackers={"person.a": ("home", 10)},
            activity={"binary_sensor.motion": ("unavailable", 10)},
            guest="on",
        )
        self.assertIn("Guest mode=on", c["diagnostic_line"])
        self.assertIn("person.a=home", c["diagnostic_line"])
        self.assertIn("binary_sensor.motion=unavailable", c["diagnostic_line"])
        self.assertIn("OCCUPIED", c["diagnostic_line"])
        self.assertIn("255", next(a["variables"]["diagnostic_value"] for a in self.data["actions"] if "diagnostic_value" in a.get("variables", {})))

    def test_no_invalid_bare_sequence_actions(self):
        """A sequence mapping is valid inside parallel, but not as a standalone action."""
        invalid = []

        def visit(node, parent=None):
            if isinstance(node, list):
                for item in node:
                    if isinstance(item, dict) and list(item) == ["sequence"] and parent != "parallel":
                        invalid.append((parent, item))
                    visit(item, parent)
            elif isinstance(node, dict):
                for key, value in node.items():
                    visit(value, key)

        visit(self.data["actions"])
        self.assertEqual(invalid, [])

    def test_persistent_timer_due_guard(self):
        import types

        due = next(
            b for b in self.data["actions"][-1]["choose"]
            if "deadline reached" in b["alias"]
        )
        template = self.env.from_string(due["conditions"][0]["value_template"])
        now = dt.datetime(2026, 10, 8, 8, 0, tzinfo=dt.timezone.utc)

        def timestamp(value, default=0):
            try:
                if isinstance(value, dt.datetime):
                    return value.timestamp()
                return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp()
            except (ValueError, TypeError):
                return default

        def evaluate(*, pending="on", deadline="2026-10-08 07:59:00", trigger="temporary_tick"):
            entities = {"input_boolean.pending": pending, "input_datetime.deadline": deadline}
            return template.render(
                trigger=types.SimpleNamespace(id=trigger),
                temporary_enabled=True,
                temporary_deadline="input_datetime.deadline",
                temporary_pending="input_boolean.pending",
                is_state=lambda entity, value: entities[entity] == value,
                states=lambda entity: entities[entity],
                as_timestamp=timestamp,
                now=lambda: now,
            ).strip().lower() == "true"

        self.assertTrue(evaluate())
        self.assertFalse(evaluate(pending="off"))
        self.assertFalse(evaluate(deadline="2026-10-08 08:01:00"))
        self.assertFalse(evaluate(deadline="unavailable"))
        self.assertFalse(evaluate(trigger="reconcile"))

    def test_persistent_timer_is_restart_recoverable_and_guarded(self):
        self.assertEqual(self.inputs["temporary_deadline"]["default"], "")
        self.assertEqual(self.inputs["temporary_pending"]["default"], "")
        self.assertEqual(self.inputs["temporary_enabled"]["default"], False)
        self.assertIn("temporary_tick", {t.get("id") for t in self.data["triggers"]})
        main = self.data["actions"][-1]["choose"]
        due = next(b for b in main if "deadline reached" in b["alias"])
        text = str(due)
        self.assertIn("temporary_pending", text)
        self.assertIn("temporary_deadline", text)
        self.assertIn("input_boolean.turn_off", text)
        self.assertIn("!input temporary_end_conditions", text)
        self.assertIn("!input temporary_end_actions", text)
        self.assertLess(text.find("input_boolean.turn_off"), text.find("!input temporary_end_actions"))
        arrival = next(b for b in main if b["alias"] == "Occupancy changed to occupied")
        arrival_text = str(arrival)
        self.assertIn("input_datetime.set_datetime", arrival_text)
        self.assertIn("input_boolean.turn_on", arrival_text)
        self.assertIn("!input temporary_start_actions", arrival_text)
        self.assertIn("!input temporary_minutes", arrival_text)  # legacy fallback

    def test_custom_trigger_no_builtin_sources(self):
        c = self.evaluate(trigger="custom_away")
        self.assertTrue(self.true(c["absence_evidence_ok"]))


    def test_optional_diagnostics_never_block_state_changes(self):
        display = next(a for a in self.data["actions"]
                       if isinstance(a, dict) and "then" in a
                       and "input_text.set_value" in str(a.get("then")))
        condition = self.env.from_string(display["if"][0]["value_template"])
        for status in ("unknown", "unavailable"):
            with self.subTest(status=status):
                result = condition.render(
                    diagnostics_enabled=True,
                    diagnostics_text="input_text.occupancy_reason",
                    diagnostic_value="OCCUPIED | Guest mode=on",
                    states=lambda _: status,
                ).strip().lower()
                self.assertEqual(result, "false")
        self.assertTrue(display["then"][0]["continue_on_error"])

    def test_guest_and_blocker_can_restore_occupancy(self):
        ids = {item.get("id") for item in self.data["triggers"]}
        self.assertIn("guest_home", ids)
        self.assertIn("blocker_home", ids)
        guest = self.evaluate(guest="on")
        blocked = self.evaluate(blockers={"binary_sensor.bed": ("on", 10)})
        self.assertTrue(self.true(guest["anyone_home_now"]))
        self.assertTrue(self.true(blocked["anyone_home_now"]))
        arrival = next(b for b in self.data["actions"][-1]["choose"]
                       if b["alias"] == "Automatic arrival")
        self.assertIn("guest_home", str(arrival))
        self.assertIn("blocker_home", str(arrival))

    def test_english_blueprint_labels_and_messages(self):
        strings = [self.data["blueprint"]["name"], self.data["blueprint"]["description"]]
        for group in self.data["blueprint"]["input"].values():
            strings.append(group["name"])
            for spec in group["input"].values():
                strings.extend([spec.get("name", ""), spec.get("description", "")])
        forbidden = ("Anwesenheit", "Abwesenheit", "Belegung", "Gäste",
                     "Schlafmodus", "Türfolge", "Aktionen", "Neustartfest")
        for value in strings:
            for word in forbidden:
                self.assertNotIn(word, value)

    def test_vacancy_guards_remain_mandatory(self):
        checks = str(self.data["actions"][-1]["choose"][-1]["conditions"])
        for item in ("guest_mode", "sleep_clear", "blockers_clear",
                     "known_trackers_safe", "activity_clear",
                     "absence_evidence_ok", "!input away_conditions"):
            self.assertIn(item, checks)


if __name__ == "__main__":
    unittest.main()
