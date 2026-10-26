"""Offline contract and safety regression checks for Unlock Sequence.

These checks do not claim that device actions were tested on a Home Assistant
instance. The existing integration_tests/test_catalog.py validates the schema
with the pinned real Home Assistant dependency on CI.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest
from datetime import datetime, timedelta, timezone

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/automation/unlock_sequence/unlock_sequence.yaml"
GUIDE = BLUEPRINT.parent / "README.md"


class BlueprintLoader(yaml.SafeLoader):
    pass


BlueprintLoader.add_constructor(
    "!input", lambda loader, node: "!input " + loader.construct_scalar(node)
)


def all_inputs(blueprint):
    return {
        name: spec
        for section in blueprint["blueprint"]["input"].values()
        for name, spec in section["input"].items()
    }


def walk(node):
    if isinstance(node, dict):
        yield node
        for val in node.values():
            yield from walk(val)
    elif isinstance(node, list):
        for val in node:
            yield from walk(val)


class UnlockSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BLUEPRINT.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.text, Loader=BlueprintLoader)
        cls.inputs = all_inputs(cls.data)
        cls.env = jinja2.Environment(
            trim_blocks=True, lstrip_blocks=True
        )
        cls.env.filters["bool"] = lambda v, default=False: str(v).lower() in (
            "true", "1", "on"
        )

    def code(self, **overrides):
        context = {
            "_mode": "advanced",
            "_simple_repeats": 4,
            "_advanced_code": "ABCD",
        }
        context.update(overrides)
        return self.env.from_string(self.data["variables"]["_code"]).render(**context).strip()

    def config(self, **overrides):
        context = {
            "_mode": "advanced",
            "_code": "ABCD",
            "_simple_triggers": [],
            "_simple_repeats": 4,
            "_advanced_triggers": [
                {"trigger": "event", "event_type": f"button_{n}", "id": n}
                for n in "ABCD"
            ],
            "_total_timeout": 30,
            "_step_timeout": 10,
        }
        context.update(overrides)
        return self.env.from_string(
            self.data["variables"]["_configuration_valid"]
        ).render(**context).strip() == "True"

    def test_blueprint_metadata_and_selectors(self):
        meta = self.data["blueprint"]
        self.assertEqual(meta["domain"], "automation")
        self.assertEqual(meta["homeassistant"]["min_version"], "2026.10.0")
        self.assertEqual(self.data["mode"], "single")
        self.assertEqual(self.data["max_exceeded"], "silent")
        self.assertTrue(meta["source_url"].endswith("/unlock_sequence.yaml"))
        self.assertIn("trigger", self.inputs["simple_triggers"]["selector"])
        self.assertIn("trigger", self.inputs["advanced_triggers"]["selector"])
        self.assertEqual(self.inputs["simple_repeats"]["selector"]["number"]["max"], 16)
        self.assertEqual(self.inputs["debounce_ms"]["default"], 300)
        self.assertEqual(self.inputs["success_cooldown_seconds"]["default"], 30)

    def test_every_referenced_input_is_defined(self):
        references = set(re.findall(r"!input\s+([A-Za-z_][\w]*)", self.text))
        self.assertEqual(references - set(self.inputs), set())
        self.assertEqual(set(self.inputs) - references, set())

    def test_all_jinja_templates_parse(self):
        for node in walk(self.data):
            for value in node.values():
                if isinstance(value, str) and ("{{" in value or "{%" in value):
                    self.env.parse(value)

    def test_simple_repetitions_between_one_and_sixteen(self):
        self.assertEqual(self.code(_mode="simple", _simple_repeats=1), "A")
        self.assertEqual(self.code(_mode="simple", _simple_repeats=16), "A" * 16)
        self.assertTrue(self.config(
            _mode="simple", _code="AAAA", _advanced_triggers=[],
            _simple_triggers=[{"trigger": "event", "event_type": "press"}]
        ))
        self.assertFalse(self.config(
            _mode="simple", _code="AAAA", _advanced_triggers=[],
            _simple_triggers=[]
        ))
        self.assertFalse(self.config(
            _mode="simple", _code="AAAA", _advanced_triggers=[],
            _simple_triggers=[{"trigger": "event", "event_type": "press"}] * 2
        ))

    def test_advanced_symbols_and_length(self):
        self.assertTrue(self.config())
        self.assertTrue(self.config(_code="A" * 16))
        self.assertFalse(self.config(_code="A" * 17))
        self.assertFalse(self.config(_code=""))
        self.assertFalse(self.config(_code="ABCE"))
        self.assertFalse(self.config(_advanced_triggers=[
            {"trigger": "event", "event_type": "a", "id": "A"},
            {"trigger": "event", "event_type": "b", "id": "A"},
        ]))
        self.assertFalse(self.config(_advanced_triggers=[
            {"trigger": "event", "event_type": "a", "id": "A"},
            {"trigger": "event", "event_type": "a", "id": "B"},
        ], _code="AB"))
        self.assertFalse(self.config(_advanced_triggers=[
            {"trigger": "event", "event_type": "b", "id": "Z"},
        ], _code="Z"))

    def test_at_least_one_deadline_is_required(self):
        self.assertTrue(self.config(_total_timeout=0, _step_timeout=10))
        self.assertTrue(self.config(_total_timeout=30, _step_timeout=0))
        self.assertFalse(self.config(_total_timeout=0, _step_timeout=0))

    def test_no_polling_or_parallel_input_runs(self):
        self.assertFalse(any("time_pattern" in node.get("trigger", "")
                             for node in walk(self.data)
                             if isinstance(node.get("trigger"), str)))
        self.assertEqual(self.data["mode"], "single")
        self.assertGreaterEqual(sum(
            1 for node in walk(self.data) if "wait_for_trigger" in node
        ), 2)
        self.assertNotIn("mode: queued", self.text)
        self.assertNotIn("mode: parallel", self.text)

    def test_fail_closed_and_confirmation_gates(self):
        actions = self.data["actions"]
        self.assertIn("fail", actions[0]["then"][0]["stop"].lower())
        self.assertIn("_helpers_valid", self.text)
        self.assertIn("_configuration_valid", self.text)
        self.assertIn("conditions: !input start_conditions", self.text)
        self.assertIn("conditions: !input success_conditions", self.text)
        self.assertIn("conditions: !input verify_conditions", self.text)
        self.assertIn("sequence: !input error_actions", self.text)
        self.assertIn("not _confirmed", self.text)
        self.assertNotIn("shell_command.", self.text)
        self.assertNotIn("command_line.", self.text)

    def test_failure_count_is_recorded_at_most_once_per_wrong_event(self):
        self.assertIn("_failure_recorded: true", self.text)
        self.assertIn("not _failure_recorded", self.text)
        self.assertIn("_failure_recorded: false", self.text)
        self.assertIn("and as_timestamp(states(_lock_helper)", self.text)
        self.assertEqual(self.text.count("sequence: !input failure_actions"), 3)

    def test_persistent_deadline_write_precedes_counter_increment(self):
        for node in walk(self.data):
            if "if" not in node or "then" not in node:
                continue
            if "_next_failure_count | int >= _maximum_failures" in str(node["if"]):
                self.assertEqual(
                    node["then"][0]["action"], "input_datetime.set_datetime"
                )
        self.assertIn("event: start", self.text)
        self.assertIn("id: \"__lock_expiry\"", self.text)

    def test_package_not_misidentified_as_installable_blueprint(self):
        self.assertTrue((BLUEPRINT.parent / "helpers-package.example.yml").exists())
        self.assertEqual(
            list(BLUEPRINT.parent.glob("*.yaml")), [BLUEPRINT]
        )

    def test_catalog_and_guide_match_existing_ci_contract(self):
        root = (ROOT / "README.md").read_text(encoding="utf-8")
        url = self.data["blueprint"]["source_url"]
        self.assertIn(f"\n{url}\n", root)
        self.assertIn(f"\n{url}\n", GUIDE.read_text(encoding="utf-8"))
        self.assertIn("blueprints_updater.reload", GUIDE.read_text(encoding="utf-8"))
        self.assertIn("Unlock Sequence", root)


if __name__ == "__main__":
    unittest.main()
