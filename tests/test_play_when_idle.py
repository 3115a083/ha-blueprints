"""Static and Jinja behavior tests for the Play When Idle blueprint."""

from pathlib import Path
from types import SimpleNamespace
import re
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/automation/play_when_idle/play_when_idle.yaml"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


def visit_templates(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from visit_templates(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from visit_templates(value)
    elif isinstance(obj, str) and ("{{" in obj or "{%" in obj):
        yield obj


def find_variable(data, key):
    if isinstance(data, dict):
        if isinstance(data.get("variables"), dict) and key in data["variables"]:
            return data["variables"][key]
        for value in data.values():
            found = find_variable(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = find_variable(value, key)
            if found is not None:
                return found
    return None


class PlayWhenIdleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BLUEPRINT.read_text(encoding="utf-8")
        cls.blueprint = yaml.load(cls.text, Loader=Loader)
        cls.inputs = {
            name: val for section in cls.blueprint["blueprint"]["input"].values()
            for name, val in section["input"].items()
        }
        cls.env = jinja2.Environment()

    def test_structure_and_inputs(self):
        metadata = self.blueprint["blueprint"]
        self.assertEqual(metadata["domain"], "automation")
        self.assertEqual(metadata["homeassistant"]["min_version"], "2025.7.0")
        self.assertTrue(metadata["source_url"].endswith("/play_when_idle/play_when_idle.yaml"))
        self.assertEqual(self.blueprint["mode"], "single")
        self.assertEqual(self.blueprint["max_exceeded"], "silent")
        self.assertTrue(self.inputs["detect_ha_play"]["default"])
        self.assertEqual(self.inputs["idle_check"]["default"], "idle")
        self.assertEqual(self.inputs["fallback_mode"]["default"], "music_assistant_radio")
        self.assertEqual(self.inputs["cooldown_seconds"]["default"], 3)
        self.assertEqual(self.inputs["additional_play_triggers"]["default"], [])
        self.assertTrue(self.inputs["monitored_players"]["selector"]["entity"]["multiple"])
        self.assertEqual(self.inputs["custom_actions"]["default"], [])
        self.assertIn("domain: media_player", self.text)
        self.assertIn("mass_player_type", self.text)

    def test_all_inputs_exist_and_templates_compile(self):
        referenced = set(re.findall(r"!input\s+([a-zA-Z0-9_]+)", self.text))
        self.assertFalse(referenced - set(self.inputs))
        for index, tmpl in enumerate(visit_templates(self.blueprint)):
            with self.subTest(index=index):
                self.env.parse(tmpl)

    def candidates(self, trigger, selected=None, fallback=""):
        tmpl = self.env.from_string(find_variable(self.blueprint["actions"], "candidate_players"))
        rendered = tmpl.render(
            trigger=trigger,
            selected_players=selected or ["media_player.ma_living", "media_player.ma_kitchen"],
            custom_trigger_player=fallback,
        ).strip()
        return yaml.safe_load(rendered)

    def test_ha_play_only_targets_selected_requested_player(self):
        event = SimpleNamespace(data={"service_data": {"entity_id": "media_player.ma_kitchen"}})
        result = self.candidates({"id": "ha_media_play", "event": event})
        self.assertEqual(result, ["media_player.ma_kitchen"])
        event.data["service_data"]["entity_id"] = [
            "media_player.ma_living", "media_player.other"
        ]
        self.assertEqual(
            self.candidates({"id": "ha_media_play_pause", "event": event}),
            ["media_player.ma_living"]
        )
        event.data["service_data"]["entity_id"] = "media_player.other"
        self.assertEqual(self.candidates({"id": "ha_media_play", "event": event}), [])
        # Unknown target must not fan out to all speakers.
        event.data["service_data"].pop("entity_id")
        self.assertEqual(
            self.candidates({"id": "ha_media_play", "event": event},
                            fallback="media_player.ma_living"), []
        )

    def test_external_button_routing_is_safe(self):
        trigger = {"id": "external_play", "entity_id": "media_player.ma_living"}
        self.assertEqual(self.candidates(trigger), ["media_player.ma_living"])
        self.assertEqual(self.candidates({"id": "button"}), [])
        self.assertEqual(
            self.candidates({"id": "button"}, fallback="media_player.ma_kitchen"),
            ["media_player.ma_kitchen"]
        )
        self.assertEqual(
            self.candidates({"id": "button"}, selected=["media_player.ma_living"]),
            ["media_player.ma_living"]
        )
        self.assertEqual(
            self.candidates({"id": "button", "event": SimpleNamespace(
                data={"entity_id": "media_player.ma_kitchen"})}),
            ["media_player.ma_kitchen"]
        )

    def test_paused_playing_and_off_are_not_eligible(self):
        check = next(
            condition["value_template"]
            for action in self.blueprint["actions"]
            if "repeat" in action
            for step in action["repeat"]["sequence"]
            if "if" in step
            for condition in step["if"]
            if isinstance(condition, dict) and "value_template" in condition
            and "playback_idle" in condition["value_template"]
        )
        template = self.env.from_string(check)
        for state in ["playing", "paused", "off", "buffering", "unknown", "unavailable"]:
            with self.subTest(state=state):
                eligible = template.render(
                    playback_idle=(state == "idle"),
                    idle_policy="idle",
                    no_media_loaded=True
                ).strip()
                self.assertEqual(eligible, "False")
        self.assertEqual(
            template.render(playback_idle=True, idle_policy="idle",
                            no_media_loaded=False).strip(), "True"
        )
        self.assertEqual(
            template.render(playback_idle=True, idle_policy="no_media",
                            no_media_loaded=False).strip(), "False"
        )

    def test_ma_queue_check_fails_closed(self):
        template = self.env.from_string(find_variable(
            self.blueprint["actions"], "queue_allowed"
        ))
        def allowed(response=None, *, defined=True):
            return template.render(
                ma_queue_info=response,
                play_target_player="media_player.ma_living",
            ).strip()
        # Find the second queue_allowed variable (the verification, not initializer).
        queue_guards = [
            value for value in visit_templates(self.blueprint["actions"])
            if "ma_queue_info.get" in value
        ]
        self.assertEqual(len(queue_guards), 1)
        strict = self.env.from_string(queue_guards[0])
        def check(response):
            return strict.render(
                ma_queue_info=response, play_target_player="media_player.ma_living"
            ).strip()
        self.assertEqual(check({"media_player.ma_living": {"items": 0}}), "True")
        self.assertEqual(check({"media_player.ma_living": {"items": 1}}), "False")
        self.assertEqual(check({"media_player.ma_living": {}}), "False")
        self.assertEqual(check({}), "False")

    def test_actions_and_no_auto_idle_trigger(self):
        trigger_types = [t.get("trigger") for t in self.blueprint["triggers"] if "trigger" in t]
        self.assertEqual(trigger_types, ["event", "event"])
        self.assertEqual(
            {t["event_data"]["service"] for t in self.blueprint["triggers"] if "event_data" in t},
            {"media_play", "media_play_pause"}
        )
        self.assertIn("!input additional_play_triggers", str(self.blueprint["triggers"]))
        actions = str(self.blueprint["actions"])
        self.assertIn("music_assistant.play_media", actions)
        self.assertIn("music_assistant.get_queue", actions)
        self.assertIn("media_player.play_media", actions)
        self.assertIn("!input custom_actions", actions)
        self.assertNotIn("media_player.media_play", actions)
        self.assertIn("media_type': 'radio'", actions)
        self.assertIn("enqueue': 'replace'", actions)
        self.assertIn("play_target_player", actions)

    def test_english_documentation(self):
        doc = (BLUEPRINT.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("physical Sonos", doc)
        self.assertIn("Music Assistant", doc)
        self.assertIn("call_service", doc)
        root_doc = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("play_when_idle/play_when_idle.yaml", root_doc)


if __name__ == "__main__":
    unittest.main()
