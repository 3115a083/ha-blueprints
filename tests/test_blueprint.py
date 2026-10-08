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
        self.assertEqual(self.inputs["occupancy_helper"]["default"], "")
        self.assertIn("input_boolean", str(self.inputs["occupancy_helper"]["selector"]))
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
        """Each deadline is evaluated independently against its own helpers."""
        import types

        main = self.data["actions"][-1]["choose"]
        due = next(b for b in main if b["alias"].startswith("Process all independent"))
        self.assertIn("temporary_tick", due["conditions"][0]["value_template"])
        branches = due["sequence"][0]["parallel"]
        self.assertEqual(len(branches), 3)
        now = dt.datetime(2026, 10, 8, 8, 0, tzinfo=dt.timezone.utc)

        def timestamp(value, default=0):
            try:
                return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp()
            except (ValueError, TypeError):
                return default

        for number, branch in enumerate(branches, start=1):
            with self.subTest(slot=number):
                prefix = "temporary_" if number == 1 else f"temporary_{number}_"
                check = self.env.from_string(branch["sequence"][0]["value_template"])
                pending_id = f"input_boolean.pending_{number}"
                deadline_id = f"input_datetime.deadline_{number}"

                def evaluate(*, pending="on", deadline="2026-10-08 07:59:00", unique=True):
                    entities = {pending_id: pending, deadline_id: deadline}
                    values = {
                        prefix + "enabled": True,
                        prefix + "deadline": deadline_id,
                        prefix + "pending": pending_id,
                        "temporary_helpers_unique": unique,
                        "is_state": lambda entity, state: entities[entity] == state,
                        "states": lambda entity: entities[entity],
                        "as_timestamp": timestamp,
                        "now": lambda: now,
                    }
                    return check.render(**values).strip().lower() == "true"

                self.assertTrue(evaluate())
                self.assertFalse(evaluate(pending="off"))
                self.assertFalse(evaluate(deadline="2026-10-08 08:01:00"))
                self.assertFalse(evaluate(deadline="unavailable"))
                self.assertFalse(evaluate(unique=False))

    def test_independent_timed_arrival_slots(self):
        """One arrival runs up to three isolated routines, with their own durations."""
        main = self.data["actions"][-1]["choose"]
        due = next(b for b in main if b["alias"].startswith("Process all independent"))
        branches = due["sequence"][0]["parallel"]
        arrival = next(b for b in main if b["alias"] == "Occupancy changed to occupied")
        parallel = next(action["parallel"] for action in arrival["sequence"] if "parallel" in action)
        self.assertEqual(len(parallel), 4)  # Home actions + 3 independent timer paths
        self.assertEqual(len(branches), 3)
        self.assertEqual(self.inputs["temporary_minutes"]["default"], 40)
        self.assertEqual(self.inputs["temporary_2_minutes"]["default"], 30)
        self.assertEqual(self.inputs["temporary_3_minutes"]["default"], 15)
        for i in (1, 2, 3):
            with self.subTest(slot=i):
                prefix = "temporary_" if i == 1 else f"temporary_{i}_"
                for name in ("enabled", "start_conditions", "start_actions", "minutes",
                             "deadline", "pending", "end_conditions", "end_actions"):
                    self.assertIn(prefix + name, self.inputs)
                    self.assertIn("default", self.inputs[prefix + name])
                self.assertIn(prefix + "deadline", str(branches[i-1]))
                self.assertIn(prefix + "pending", str(branches[i-1]))
                self.assertIn("input_boolean.turn_off", str(branches[i-1]))
                self.assertIn("!input " + prefix + "end_conditions", str(branches[i-1]))
                self.assertIn("!input " + prefix + "end_actions", str(branches[i-1]))
                self.assertIn("input_datetime.set_datetime", str(parallel[i]))
                self.assertIn("input_boolean.turn_on", str(parallel[i]))
                self.assertIn("!input " + prefix + "start_actions", str(parallel[i]))
                self.assertIn("!input " + prefix + "minutes", str(parallel[i]))

    def test_reject_shared_timed_helpers(self):
        """Reusing a helper in another slot must fail closed to prevent cross-action corruption."""
        value = self.data["variables"]["temporary_helpers_unique"]
        template = self.env.from_string(value)

        def good(deadlines, pendings):
            fields = {}
            for index, (deadline, pending) in enumerate(zip(deadlines, pendings), start=1):
                prefix = "temporary_" if index == 1 else f"temporary_{index}_"
                fields[prefix + "deadline"] = deadline
                fields[prefix + "pending"] = pending
            return template.render(**fields).strip().lower() == "true"

        self.assertTrue(good(["input_datetime.a", "input_datetime.b", "input_datetime.c"],
                             ["input_boolean.a", "input_boolean.b", "input_boolean.c"]))
        self.assertTrue(good(["", "", ""], ["", "", ""]))
        self.assertFalse(good(["input_datetime.a", "input_datetime.a", ""],
                              ["input_boolean.a", "input_boolean.b", ""]))
        self.assertFalse(good(["input_datetime.a", "input_datetime.b", ""],
                              ["input_boolean.a", "input_boolean.a", ""]))

    def test_persistent_timer_is_restart_recoverable_and_guarded(self):
        self.assertIn("temporary_tick", {t.get("id") for t in self.data["triggers"]})
        due = next(b for b in self.data["actions"][-1]["choose"]
                   if b["alias"].startswith("Process all independent"))
        self.assertIn("parallel", due["sequence"][0])
        for branch in due["sequence"][0]["parallel"]:
            sequence = branch["sequence"]
            self.assertLess(str(sequence).find("input_boolean.turn_off"),
                            str(sequence).find("end_actions"))
            self.assertIn("temporary_helpers_unique", str(sequence))

    def test_optional_occupancy_output_does_not_require_manual_toggle(self):
        """Input boolean is an optional published output; state triggers tolerate an empty input."""
        helper = self.inputs["occupancy_helper"]
        self.assertEqual(helper["default"], "")
        self.assertIn("OUTPUT", helper["description"])
        triggers = {t.get("id"): t for t in self.data["triggers"] if t.get("id")}
        for trigger_id, state in (("became_home", "on"), ("became_away", "off")):
            with self.subTest(trigger=trigger_id):
                spec = triggers[trigger_id]
                self.assertEqual(spec["trigger"], "template")
                self.assertIn("_occupancy_helper != ''", spec["value_template"])
                self.assertIn(f"'{state}'", spec["value_template"])
        self.assertEqual(self.data["trigger_variables"]["_occupancy_helper"], "!input occupancy_helper")

    def test_direct_mode_tracker_transitions_run_actions_with_guards(self):
        """Without a published switch, tracker transitions are sufficient, but guards still apply."""
        choose = self.data["actions"][-1]["choose"]
        vacant = next(b for b in choose if b["alias"] == "Occupancy changed to vacant")
        occupied = next(b for b in choose if b["alias"] == "Occupancy changed to occupied")
        self.assertEqual(vacant["sequence"], "!input away_actions")
        self.assertIn("tracker_away", str(vacant["conditions"]))
        self.assertIn("tracker_home", str(occupied["conditions"]))
        self.assertIn("!input away_conditions", str(vacant["conditions"]))
        self.assertIn("!input home_conditions", str(occupied["conditions"]))
        self.assertIn("guest_mode", str(vacant["conditions"]))
        self.assertIn("sleep_clear", str(vacant["conditions"]))
        direct = vacant["conditions"][0]["conditions"][1]["conditions"][0]["value_template"]
        tpl = self.env.from_string(direct)
        c = self.evaluate(
            trackers={"person.a": ("not_home", 15)},
            activity={"binary_sensor.motion": ("off", 30)},
        )
        c["occupancy_helper"] = ""
        self.assertEqual(tpl.render(**c).strip().lower(), "true")
        c["trigger"] = {"id": "tracker_home"}
        self.assertEqual(tpl.render(**c).strip().lower(), "false")
        c["trigger"] = {"id": "tracker_away"}
        c["guest_mode"] = "input_boolean.guests"
        c["states"].entities["input_boolean.guests"].state = "on"
        self.assertEqual(tpl.render(**c).strip().lower(), "false")

    def test_output_mode_requires_switch_before_writing(self):
        """No service target may be an empty literal entity_id with the output omitted."""
        choose = self.data["actions"][-1]["choose"]
        for name in ("Automatic arrival", "Automatic vacancy with safety checks"):
            branch = next(b for b in choose if b["alias"] == name)
            self.assertEqual(branch["conditions"][0]["value_template"],
                             "{{ occupancy_helper != '' }}")
            action = branch["sequence"][0]
            self.assertEqual(action["target"]["entity_id"], "{{ occupancy_helper }}")

    def test_direct_mode_diagnostics_use_derived_presence(self):
        """Dashboard status in tracker-only mode cannot depend on a missing input_boolean."""
        blocks = [a["variables"] for a in self.data["actions"] if "variables" in a]
        derived = next(x["derived_vacant"] for x in blocks if "derived_vacant" in x)
        diagnostics = next(x["diagnostic_line"] for x in blocks if "diagnostic_line" in x)
        self.assertIn("all_trackers_away_stable", derived)
        self.assertIn("occupancy_helper == ''", derived)
        self.assertIn("derived_vacant", diagnostics)
        c = self.evaluate(trackers={"person.a": ("not_home", 25)})
        c["occupancy_helper"] = ""
        result = self.env.from_string(derived).render(**c).strip().lower()
        self.assertEqual(result, "true")

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
        for value in strings:
            self.assertTrue(value.isascii(), f"Non-English UI character in: {value!r}")
        self.assertIn("Presence & Vacancy", self.data["blueprint"]["name"])
        self.assertIn("Automatic detection", str(strings))

    def test_vacancy_guards_remain_mandatory(self):
        checks = str(self.data["actions"][-1]["choose"][-1]["conditions"])
        for item in ("guest_mode", "sleep_clear", "blockers_clear",
                     "known_trackers_safe", "activity_clear",
                     "absence_evidence_ok", "!input away_conditions"):
            self.assertIn(item, checks)


if __name__ == "__main__":
    unittest.main()
