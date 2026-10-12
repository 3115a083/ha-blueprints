"""Static tests for the Music Assistant / Blackymas NSPanel companion blueprint."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/automation/music_assistant_nspanel/music_assistant_nspanel.yaml"


class BlueprintLoader(yaml.SafeLoader):
    pass


BlueprintLoader.add_constructor(
    "!input", lambda loader, node: "!input " + loader.construct_scalar(node)
)


class MusicAssistantNSPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BLUEPRINT.read_text(encoding="utf-8")
        cls.blueprint = yaml.load(cls.text, Loader=BlueprintLoader)
        cls.inputs = {
            name: cfg
            for section in cls.blueprint["blueprint"]["input"].values()
            for name, cfg in section["input"].items()
        }
        cls.jinja = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)

    def get_choice(self, alias_fragment):
        return next(
            choice for choice in self.blueprint["actions"][-1]["choose"]
            if alias_fragment in choice["alias"]
        )

    def test_up_to_date_blueprint_syntax(self):
        self.assertEqual(self.blueprint["blueprint"]["domain"], "automation")
        self.assertEqual(self.blueprint["blueprint"]["homeassistant"]["min_version"], "2025.7.0")
        self.assertEqual(self.blueprint["mode"], "queued")
        self.assertIn("triggers", self.blueprint)
        self.assertIn("actions", self.blueprint)
        self.assertIn("variables", self.blueprint)
        self.assertNotIn("trigger", self.blueprint)
        self.assertNotIn("action", self.blueprint)
        self.assertIn("source_url", self.blueprint["blueprint"])

    def test_references_and_sections(self):
        refs = set(re.findall(r"!input\s+([a-z0-9_]+)", self.text))
        self.assertFalse(refs - set(self.inputs))
        self.assertEqual(
            list(self.blueprint["blueprint"]["input"]),
            ["library", "speakers", "helpers"],
        )
        self.assertEqual(set(self.inputs), {
            "media_entries", "player_entries", "preset_select", "speaker_select",
            "next_preset_button", "next_speaker_button", "play_button", "transfer_button",
        })

    def test_repeatable_preset_and_speaker_lists(self):
        media = self.inputs["media_entries"]["selector"]["object"]
        players = self.inputs["player_entries"]["selector"]["object"]
        self.assertTrue(media["multiple"])
        self.assertTrue(players["multiple"])
        self.assertEqual(media["label_field"], "label")
        self.assertEqual(players["label_field"], "label")
        self.assertEqual(media["fields"]["media_type"]["selector"]["select"]["options"][0]["value"], "radio")
        self.assertEqual(media["fields"]["media_type"]["selector"]["select"]["options"][1]["value"], "playlist")
        self.assertEqual(players["fields"]["player"]["selector"]["entity"]["filter"]["domain"], "media_player")
        for key in ("label", "media_type", "media_id"):
            self.assertTrue(media["fields"][key]["required"])
        self.assertTrue(players["fields"]["player"]["required"])

    def test_all_helper_inputs_have_entity_selectors(self):
        for name in ("preset_select", "speaker_select"):
            self.assertEqual(
                self.inputs[name]["selector"]["entity"]["filter"]["domain"],
                "input_select",
            )
        for name in ("next_preset_button", "next_speaker_button", "play_button", "transfer_button"):
            self.assertEqual(
                self.inputs[name]["selector"]["entity"]["filter"]["domain"],
                "input_button",
            )

    def test_button_press_triggers_are_one_shot(self):
        triggers = self.blueprint["triggers"]
        self.assertEqual({x["id"] for x in triggers}, {
            "next_preset", "next_speaker", "play_selection", "transfer_queue",
            "initialize", "reload",
        })
        self.assertEqual(sum(x["trigger"] == "state" for x in triggers), 4)
        self.assertFalse(any(x["trigger"] == "time_pattern" for x in triggers))
        buttons = {"next_preset_button", "next_speaker_button", "play_button", "transfer_button"}
        self.assertEqual(
            {x["entity_id"].removeprefix("!input ") for x in triggers if x["trigger"] == "state"},
            buttons,
        )

    def test_templates_parse(self):
        def visit(obj):
            if isinstance(obj, str) and ("{{" in obj or "{%" in obj):
                self.jinja.parse(obj)
            elif isinstance(obj, list):
                for value in obj:
                    visit(value)
            elif isinstance(obj, dict):
                for value in obj.values():
                    visit(value)
        visit(self.blueprint)

    def test_dynamic_select_options_and_deduplication(self):
        actions = self.blueprint["actions"]
        txt = str(actions)
        self.assertIn("input_select.set_options", txt)
        self.assertIn("media_labels | unique | list | count", txt)
        self.assertIn("player_labels | unique | list | count", txt)
        self.assertIn("input_select.select_next", txt)
        self.assertIn("persistent_notification.create", txt)

    def test_selection_changes_do_not_start_playback(self):
        for label in ("Select next radio", "Select next Music Assistant speaker"):
            choice = self.get_choice(label)
            self.assertIn("input_select.select_next", str(choice["sequence"]))
            self.assertNotIn("music_assistant.play_media", str(choice["sequence"]))
            self.assertNotIn("music_assistant.transfer_queue", str(choice["sequence"]))

    def test_play_uses_selected_radio_or_playlist(self):
        choice = self.get_choice("Play the selected")
        actions = choice["sequence"]
        self.assertEqual(actions[-1]["action"], "music_assistant.play_media")
        self.assertEqual(actions[-1]["data"]["media_type"], "{{ selected_media_type }}")
        self.assertEqual(actions[-1]["data"]["media_id"], "{{ selected_media_id }}")
        self.assertEqual(actions[-1]["data"]["enqueue"], "play")
        self.assertEqual(actions[-1]["target"]["entity_id"], "{{ selected_player }}")
        self.assertIn("chosen_speaker", str(actions))
        self.assertIn("chosen_preset", str(actions))
        self.assertIn("media_player.", str(actions))

    def test_queue_transfer_explicitly_targets_selected_speaker(self):
        choice = self.get_choice("Transfer playing music")
        actions = choice["sequence"]
        self.assertEqual(actions[-1]["action"], "music_assistant.transfer_queue")
        self.assertEqual(actions[-1]["target"]["entity_id"], "{{ selected_player }}")
        self.assertEqual(actions[-1]["data"]["source_player"], "{{ source_player }}")
        self.assertTrue(actions[-1]["data"]["auto_play"])
        self.assertIn("is_state(item.player, 'playing')", str(actions))

    def test_documentation_and_catalog(self):
        guide = (BLUEPRINT.parent / "README.md").read_text(encoding="utf-8")
        catalog = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Blackymas", guide)
        self.assertIn("Music Assistant", guide)
        self.assertIn("**Display limitation:**", guide)
        self.assertIn("music_assistant_nspanel/README.md", catalog)


if __name__ == "__main__":
    unittest.main()
