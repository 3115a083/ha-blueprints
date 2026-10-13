"""Regression tests for the Govee2MQTT recovery blueprint.

Validates static YAML, embedded Jinja, staged recovery and notification
formatting. These tests do not replace real Home Assistant hardware testing.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import jinja2
from jinja2.nativetypes import NativeEnvironment
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
            key: spec
            for section in cls.data["blueprint"]["input"].values()
            for key, spec in section["input"].items()
        }
        cls.env = NativeEnvironment(trim_blocks=True, lstrip_blocks=True)
        cls.env.filters["bool"] = lambda value: str(value).strip().lower() in ("true", "on", "1")

    def actions(self):
        return self.data["actions"]

    def action(self, name):
        return next(a for a in self.actions() if a.get("alias") == name)

    def formula(self, key):
        for item in self.actions():
            if key in item.get("variables", {}):
                return item["variables"][key]
        raise AssertionError(f"Missing blueprint variable: {key}")

    def render(self, template, entries=None, statuses=None, **vars):
        entries = entries or []
        statuses = statuses or {}
        ctx = {
            "lamp_entries": entries,
            "_lamp_entries": entries,
            "states": lambda entity: statuses.get(entity, "unknown"),
            "state_attr": lambda entity, attribute: (
                entity.split(".", 1)[-1].replace("_", " ").title()
                if attribute == "friendly_name" else None
            ),
            "is_state": lambda entity, state: statuses.get(entity) == state,
            "as_timestamp": lambda value, default=0: default if value in ["unknown", "unavailable", ""] else value,
        }
        ctx.update(vars)
        return self.env.from_string(template).render(**ctx)

    def test_schema_and_current_home_assistant_format(self):
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2026.2.0")
        self.assertEqual(self.data["mode"], "single")
        self.assertIn("source_url", self.data["blueprint"])
        self.assertIn("triggers", self.data)
        self.assertIn("actions", self.data)
        self.assertNotIn("trigger", self.data)
        self.assertNotIn("action", self.data)

    def test_all_references_and_repeated_lamp_entries(self):
        refs = set(re.findall(r"!input\s+([a-z0-9_]+)", self.text))
        self.assertFalse(refs - set(self.inputs))
        self.assertEqual(
            list(self.data["blueprint"]["input"]),
            ["devices", "recovery", "bridge", "diagnostics", "notifications"],
        )
        schema = self.inputs["lamp_entries"]["selector"]["object"]
        self.assertTrue(schema["multiple"])
        self.assertEqual(schema["label_field"], "light")
        self.assertTrue(schema["fields"]["light"]["required"])
        self.assertFalse(schema["fields"]["relay"]["required"])
        self.assertFalse(schema["fields"]["ping"]["required"])

    def test_installed_app_selector_instead_of_manually_typed_slug(self):
        """The native HA App selector returns an installed application's slug."""
        app_config = self.inputs["app_slug"]
        self.assertEqual(app_config["selector"], {"app": {}})
        self.assertEqual(app_config["default"], "")
        self.assertIn("installed apps", app_config["name"])
        restart = self.action("Step 1 - restart Govee2MQTT first")
        self.assertEqual(restart["then"][0]["action"], "hassio.app_restart")
        self.assertEqual(restart["then"][0]["data"]["app"], "!input app_slug")
        self.assertNotIn("homeassistant.restart", self.text)
        self.assertNotIn("hassio.host_reboot", self.text)

    def test_safe_defaults_and_languages(self):
        self.assertTrue(self.inputs["restore_power"]["default"])
        self.assertTrue(self.inputs["app_restart_enabled"]["default"])
        self.assertFalse(self.inputs["power_cycle_enabled"]["default"])
        self.assertFalse(self.inputs["require_ping_off"]["default"])
        self.assertEqual(self.inputs["max_power_cycles"]["default"], 2)
        self.assertEqual(self.inputs["cycle_off_seconds"]["default"], 3)
        self.assertEqual(self.inputs["notification_language"]["default"], "en")
        languages = self.inputs["notification_language"]["selector"]["select"]["options"]
        self.assertEqual([x["value"] for x in languages], ["en", "de"])

    def test_every_template_parses_in_jinja(self):
        def visit(value):
            if isinstance(value, str) and ("{{" in value or "{%" in value):
                self.env.parse(value)
            elif isinstance(value, dict):
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(self.data)

    def test_all_lamp_count_and_optional_relays(self):
        entries = [
            {"light": "light.kitchen", "relay": "switch.kitchen", "ping": "binary_sensor.kitchen"},
            {"light": "light.bedroom"},
            {"light": "light.hallway", "relay": None},
        ]
        statuses = {"light.kitchen": "unavailable", "switch.kitchen": "on",
                    "light.bedroom": "off", "light.hallway": "unknown"}
        self.assertEqual(self.render(self.formula("offline_count"), entries, statuses), 2)
        self.assertEqual(self.render(self.formula("relay_off_count"), entries, statuses), 0)
        statuses["switch.kitchen"] = "off"
        self.assertEqual(self.render(self.formula("relay_off_count"), entries, statuses), 1)

    def test_aggregate_trigger_and_periodic_reconciliation(self):
        ids = {t["id"] for t in self.data["triggers"]}
        self.assertEqual(ids, {"some_light_offline", "some_relay_off", "startup", "periodic"})
        periodic = next(x for x in self.data["triggers"] if x["id"] == "periodic")
        self.assertEqual(periodic["minutes"], "/10")
        self.assertIn("trigger.id != 'periodic' or cooldown_helper != ''", self.text)

    def test_restart_always_precedes_restoring_and_power_cut(self):
        app = self.action("Step 1 - restart Govee2MQTT first")
        restore = self.action("Step 2 - restore OFF relays that still need power")
        cycle = self.action("Step 3 - hard-reset remaining lamps one at a time")
        self.assertLess(self.actions().index(app), self.actions().index(restore))
        self.assertLess(self.actions().index(restore), self.actions().index(cycle))
        self.assertEqual(app["then"][0]["action"], "hassio.app_restart")
        self.assertEqual(restore["then"][0]["repeat"]["for_each"], "!input lamp_entries")
        self.assertEqual(cycle["repeat"]["for_each"], "{{ reset_candidates }}")

    def test_bridge_restart_without_datetime_helper(self):
        """An explicit bridge restart is allowed on a new outage with no helper."""
        formula = self.formula("restart_requested")
        fields = dict(
            offline_count=1,
            app_restart_enabled=True,
            app_slug="a0d7b954_govee2mqtt",
            cooldown_ready=True,
        )
        self.assertTrue(self.render(formula, **fields))
        self.assertFalse(self.render(formula, **{**fields, "app_restart_enabled": False}))
        self.assertFalse(self.render(formula, **{**fields, "app_slug": ""}))
        self.assertFalse(self.render(formula, **{**fields, "cooldown_ready": False}))

    def test_persist_cooldown_before_addon_and_hard_reset(self):
        write = self.action("Save the persistent retry timestamp")
        restart = self.action("Step 1 - restart Govee2MQTT first")
        cycle = self.action("Step 3 - hard-reset remaining lamps one at a time")
        self.assertLess(self.actions().index(write), self.actions().index(restart))
        self.assertLess(self.actions().index(write), self.actions().index(cycle))
        self.assertEqual(write["then"][0]["action"], "input_datetime.set_datetime")
        self.assertNotIn("continue_on_error", write["then"][0])
        self.assertIn("persistent_ready", self.formula("hard_reset_allowed"))

    def test_hard_reset_requires_restart_and_persistence(self):
        tmpl = self.formula("hard_reset_allowed")
        ctx = {
            "power_cycle_enabled": True,
            "restart_requested": True,
            "persistent_ready": True,
            "relay_off_count": 0,
        }
        self.assertTrue(self.render(tmpl, **ctx))
        for patch in (
            {"power_cycle_enabled": False},
            {"restart_requested": False},
            {"persistent_ready": False},
            {"relay_off_count": 1},
        ):
            self.assertFalse(self.render(tmpl, **{**ctx, **patch}))

    def test_targeted_hard_reset_without_ping_is_possible(self):
        entries = [
            {"light": "light.good", "relay": "switch.good"},
            {"light": "light.failed", "relay": "switch.failed"},
            {"light": "light.norelay"},
        ]
        status = {"light.good": "off", "switch.good": "on",
                  "light.failed": "unavailable", "switch.failed": "on",
                  "light.norelay": "unavailable"}
        result = self.render(
            self.formula("reset_candidates"), entries, status,
            hard_reset_allowed=True, max_power_cycles=2, require_ping_off=False
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["light"], "light.failed")

    def test_ping_can_be_required_as_an_additional_guard(self):
        entries = [
            {"light": "light.a", "relay": "switch.a"},
            {"light": "light.b", "relay": "switch.b", "ping": "binary_sensor.b"},
        ]
        states = {"light.a": "unavailable", "light.b": "unavailable",
                  "switch.a": "on", "switch.b": "on", "binary_sensor.b": "on"}
        args = {"hard_reset_allowed": True, "max_power_cycles": 2,
                "require_ping_off": True}
        self.assertEqual(self.render(self.formula("reset_candidates"), entries, states, **args), [])
        states["binary_sensor.b"] = "off"
        result = self.render(self.formula("reset_candidates"), entries, states, **args)
        self.assertEqual([e["light"] for e in result], ["light.b"])

    def test_shared_power_relay_is_never_hard_reset(self):
        entries = [
            {"light": "light.a", "relay": "switch.shared"},
            {"light": "light.b", "relay": "switch.shared"},
            {"light": "light.c", "relay": None},
        ]
        statuses = {
            "light.a": "unavailable", "light.b": "off",
            "light.c": "unavailable", "switch.shared": "on",
        }
        result = self.render(
            self.formula("reset_candidates"), entries, statuses,
            hard_reset_allowed=True, max_power_cycles=4, require_ping_off=False
        )
        self.assertEqual(result, [])
        self.assertIn("match.count == 1", self.formula("reset_candidates"))

    def test_limit_hard_reset_to_configured_number(self):
        entries = [
            {"light": f"light.{i}", "relay": f"switch.{i}"}
            for i in range(7)
        ]
        states = {item["light"]: "unavailable" for item in entries}
        states.update({item["relay"]: "on" for item in entries})
        for limit in (1, 2, 5):
            result = self.render(
                self.formula("reset_candidates"), entries, states,
                hard_reset_allowed=True, max_power_cycles=limit, require_ping_off=False
            )
            self.assertEqual(len(result), limit)
        self.assertEqual(self.text.count("- action: switch.turn_off"), 1)

    def test_relayless_lamps_are_safe_and_restore_only_on(self):
        restore = self.action("Step 2 - restore OFF relays that still need power")
        self.assertEqual(restore["then"][0]["repeat"]["for_each"], "!input lamp_entries")
        self.assertIn("current_relay != ''", str(restore["then"]))
        self.assertNotIn("switch.turn_off", str(restore["then"]))
        gate = self.action("Step 3 - hard-reset remaining lamps one at a time")
        self.assertIn("is_state(current_relay, 'on')", str(gate["repeat"]["sequence"]))
        self.assertEqual(
            [step["action"] for step in gate["repeat"]["sequence"][-1]["then"] if "action" in step],
            ["switch.turn_off", "switch.turn_on"],
        )

    def test_readable_per_lamp_reports_english_and_german(self):
        tmpl = self.formula("recovery_message")
        entries = [
            {"light": "light.living_room", "relay": "switch.power", "ping": "binary_sensor.ping"},
            {"light": "light.bedroom"},
        ]
        states = {"light.living_room": "unavailable", "switch.power": "on",
                  "binary_sensor.ping": "off", "light.bedroom": "off"}
        vars = dict(
            offline_count=1, starting_offline="Living Room", restart_requested=True,
            restore_power=True, relay_off_count=0, reset_candidate_names="Living Room",
            reset_candidates=[entries[0]], final_offline_count=1, final_relay_problem=False,
        )
        for lang, heading, missing_text in (
            ("en", "Govee connection check", "offline"),
            ("de", "Govee-Verbindungsprüfung", "nicht erreichbar"),
        ):
            report = str(self.render(
                tmpl, entries, states, notification_language=lang, **vars
            ))
            self.assertIn(heading, report)
            self.assertIn("Living Room", report)
            self.assertNotIn("**Bedroom**", report)
            self.assertIn("1/2", report)
            self.assertIn(missing_text, report)
            self.assertNotIn("initial_snapshot=", report)
            self.assertIn("Ping", report)

    def test_cooldown_does_not_hide_new_offline_errors(self):
        """Cooldown must block disruptive actions, not all diagnostic reporting."""
        aliases = [step.get("alias", "") for step in self.actions()]
        self.assertNotIn(
            "Explain an active cooldown instead of silently skipping recovery", aliases
        )
        self.assertNotIn(
            "Skip cooldown-only retries; still restore an OFF power relay", aliases
        )
        final = self.action("Collect readable final results")
        report = self.action("Build human-readable notification")
        self.assertLess(self.actions().index(final), self.actions().index(report))
        notify = self.action("Notify on remaining faults; clear old warnings after recovery")
        failure = notify["choose"][0]["sequence"]
        self.assertEqual(failure[0]["action"], "persistent_notification.create")
        self.assertIn("trigger.id != 'periodic' or cooldown_ready", str(failure))

    def test_readable_message_contains_only_affected_lamps(self):
        template = self.formula("recovery_message")
        entries = [
            {"light": "light.bedroom", "relay": "switch.bedroom", "ping": "binary_sensor.bedroom"},
            {"light": "light.office"},
            {"light": "light.hall"},
        ]
        states = {
            "light.bedroom": "unavailable", "switch.bedroom": "on",
            "binary_sensor.bedroom": "on", "light.office": "off",
            "light.hall": "on",
        }
        kwargs = {
            "final_offline_count": 1, "final_relay_problem": False,
            "restart_requested": True, "app_restart_enabled": True,
            "app_slug": "abc_govee2mqtt", "cooldown_ready": True,
            "relay_off_count": 0, "restore_power": True,
            "reset_candidates": [], "reset_candidate_names": "none",
            "hard_reset_skip_reason": "disabled", "notification_language": "en",
        }
        rendered = str(self.render(template, entries, states, **kwargs))
        self.assertIn("**Result:** 2/3 lights available", rendered)
        self.assertIn("**Affected lights:**", rendered)
        self.assertIn("Bedroom", rendered)
        self.assertNotIn("Office", rendered)
        self.assertNotIn("Hall", rendered)
        self.assertIn("Ping works: check Govee2MQTT/MQTT", rendered)
        self.assertIn("1. Govee2MQTT:", rendered)
        self.assertIn("2. Power relay:", rendered)
        self.assertIn("3. Hard reset:", rendered)
        self.assertIn("Restart requested; check the automation trace", rendered)
        self.assertNotIn("\\n", rendered)
        self.assertLess(rendered.count("\n\n\n"), 2)

    def test_failure_notification_and_clear_on_success(self):
        choose = self.action("Notify on remaining faults; clear old warnings after recovery")
        self.assertEqual(len(choose["choose"]), 2)
        failure, success = choose["choose"]
        self.assertEqual(failure["sequence"][0]["action"], "persistent_notification.create")
        self.assertEqual(success["sequence"][0]["action"], "persistent_notification.dismiss")
        self.assertEqual(
            failure["sequence"][0]["data"]["notification_id"],
            "govee_recovery_failed",
        )
        self.assertIn("final_offline_count", str(failure["conditions"]))
        self.assertIn("notification_language", str(failure["sequence"]))

    def test_cooldown_does_not_silence_persistent_failure_report(self):
        """Even if retry is blocked, the persistent report remains visible."""
        warning = self.action("Notify on remaining faults; clear old warnings after recovery")
        failure = warning["choose"][0]["sequence"]
        self.assertEqual(failure[0]["action"], "persistent_notification.create")
        self.assertEqual(failure[0]["data"]["notification_id"], "govee_recovery_failed")
        self.assertIn("cooldown_ready", str(failure[1]))
        self.assertIn("trigger.id != 'periodic'", str(failure[1]))
        self.assertFalse(any(x.get("stop") == "Waiting for the next safe retry" for x in self.actions()))

    def test_skip_reasons_and_candidate_names_available_for_report(self):
        candidates = self.action("Find still-offline lamps eligible for a hard reset")
        notes = self.action("Summarize the planned hard resets and skipped reasons")
        cycle = self.action("Step 3 - hard-reset remaining lamps one at a time")
        self.assertLess(self.actions().index(candidates), self.actions().index(notes))
        self.assertLess(self.actions().index(notes), self.actions().index(cycle))
        self.assertIn("reset_candidate_names", notes["variables"])
        self.assertIn("hard_reset_skip_reason", notes["variables"])
        self.assertIn("not power_cycle_enabled", notes["variables"]["hard_reset_skip_reason"])
        self.assertIn("Eligible targets", self.formula("recovery_message"))
        self.assertIn("vorgesehen", self.formula("recovery_message"))

    def test_documentation_and_catalog(self):
        readme = (BLUEPRINT.parent / "README.md").read_text(encoding="utf-8")
        catalog = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("restart Govee2MQTT first", readme)
        self.assertIn("Migrating", readme) if "Migrating" in readme else self.assertIn("Updating an existing automation", readme)
        self.assertIn("Hard-Reset", readme)
        self.assertIn("govee_recovery/README.md", catalog)


if __name__ == "__main__":
    unittest.main()
