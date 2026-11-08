"""Multi-room contact reminder and Zigbee monitoring regression tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import unittest

import yaml
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/automation/multi_room_contact_watch/multi_room_contact_watch.yaml"


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: "!input " + loader.construct_scalar(node))


class State:
    def __init__(self, value, changed):
        self.state = str(value)
        self.last_changed = changed


class States:
    def __init__(self, values):
        self.values = values

    def __call__(self, entity):
        item = self.values.get(entity)
        return item.state if item else "unknown"

    def __getitem__(self, entity):
        return self.values.get(entity)


def as_timestamp(value, default=0):
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return default


def walk(data):
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from walk(value)
    elif isinstance(data, list):
        for value in data:
            yield from walk(value)


def room_variables(actions):
    return next(n["variables"] for n in walk(actions)
                if isinstance(n, dict) and isinstance(n.get("variables"), dict)
                and "opened_now" in n["variables"] and "unhealthy_now" in n["variables"])


class ContactWatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PATH.read_text(encoding="utf-8")
        cls.data = yaml.load(cls.source, Loader=Loader)
        cls.entries = {key: value for section in cls.data["blueprint"]["input"].values()
                       for key, value in section["input"].items()}
        cls.fields = cls.entries["rooms"]["selector"]["object"]["fields"]
        cls.env = NativeEnvironment()
        cls.env.tests["match"] = lambda s, regex: bool(re.match(regex, s))
        cls.current = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc).timestamp()
        cls.vars = room_variables(cls.data["actions"])

    def context(self, data, **updates):
        states = States(data)
        ctx = dict(
            states=states, current_ts=self.current,
            is_state=lambda eid, state: states(eid) == state,
            has_value=lambda eid: states(eid) not in ("unknown", "unavailable"),
            state_attr=lambda eid, key: eid if key == "friendly_name" else None,
            as_timestamp=as_timestamp,
            is_number=lambda x: bool(re.fullmatch(r"\d+(\.\d+)?", str(x))),
            contacts=[], connectivity=[], batteries=[], last_seen_entities=[],
            issue_state="on", first_open=10, repeat_open=30,
            offline_delay=15, repeat_health=360,
            battery_threshold=20, last_seen_hours=48, trigger={"id": "minute"},
        )
        ctx.update(updates)
        return ctx

    def render(self, field, data, **updates):
        return self.env.from_string(self.vars[field]).render(**self.context(data, **updates))

    def test_schema_and_ui(self):
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"], "2026.11.0")
        self.assertEqual(self.data["blueprint"]["domain"], "automation")
        self.assertTrue(self.entries["rooms"]["selector"]["object"]["multiple"])
        self.assertEqual(self.entries["rooms"]["selector"]["object"]["label_field"], "name")
        self.assertTrue({"name", "contacts", "open_minutes", "issue_state",
                         "availability", "batteries", "last_seen", "enabled"}
                        .issubset(self.fields))
        self.assertTrue(all("description" not in field for field in self.fields.values()))
        self.assertTrue(self.entries["persistent_notifications"]["default"])
        self.assertEqual(self.entries["repeat_open_minutes"]["default"], 30)
        self.assertEqual(self.entries["unavailable_after_minutes"]["default"], 15)

    def test_event_model_and_template_contract(self):
        self.assertEqual({x["trigger"] for x in self.data["triggers"]},
                         {"time_pattern", "homeassistant", "event"})
        self.assertEqual(self.data["triggers"][0]["minutes"], "/1")
        self.assertEqual(self.data["mode"], "queued")
        self.assertFalse(any(key in node for node in walk(self.data["actions"])
                             if isinstance(node, dict)
                             for key in ("delay", "wait_template", "wait_for_trigger")))
        keys = set(re.findall(r"!input\s+(\w+)", self.source))
        self.assertFalse(keys - self.entries.keys())
        compiled = 0
        for obj in walk(self.data):
            if isinstance(obj, str) and ("{{" in obj or "{%" in obj):
                self.env.parse(obj)
                compiled += 1
        self.assertGreater(compiled, 25)

    def test_open_and_repeat_timing(self):
        eid = "binary_sensor.kitchen_window"
        examples = [(9, False), (10, True), (11, False),
                    (39, False), (40, True), (41, False), (70, True)]
        for minutes, due in examples:
            with self.subTest(minutes=minutes):
                state = {eid: State("on", self.current-minutes*60)}
                result = self.render("opened_now", state, contacts=[eid])
                self.assertEqual(bool(result["due"]), due)
                self.assertEqual(result["names"], [eid])
        result = self.render("opened_now", {eid: State("on", self.current-40*60)},
                             contacts=[eid], repeat_open=0)
        self.assertEqual(result["due"], [])

    def test_inverted_contact_and_multiple_rooms(self):
        a, b = "binary_sensor.hall", "binary_sensor.bath"
        data = {a: State("off", self.current-10*60),
                b: State("on", self.current-5*60)}
        one = self.render("opened_now", data, contacts=[a], issue_state="off")
        two = self.render("opened_now", data, contacts=[b])
        self.assertEqual(one["due"], [a])
        self.assertEqual(two["due"], [])

    def test_unknown_and_unavailable_are_health_not_open(self):
        eid = "binary_sensor.door"
        for minutes, due in ((14, False), (15, True), (16, False)):
            state = {eid: State("unavailable", self.current-minutes*60)}
            self.assertEqual(bool(self.render("unhealthy_now", state, contacts=[eid])["due"]), due)
            self.assertEqual(self.render("opened_now", state, contacts=[eid])["due"], [])
        state = {eid: State("unknown", self.current-15*60)}
        self.assertEqual(self.render("unhealthy_now", state, contacts=[eid])["due"], [eid])

    def test_availability_battery_and_last_seen(self):
        link, bat, seen = "binary_sensor.link", "sensor.battery", "sensor.last_seen"
        old = datetime.fromtimestamp(self.current-48*3600, timezone.utc).isoformat()
        data = {link: State("off", self.current-15*60),
                bat: State("17", self.current-27*60),
                seen: State(old, self.current-5*60)}
        result = self.render("unhealthy_now", data, connectivity=[link],
                             batteries=[bat], last_seen_entities=[seen], trigger={"id": "startup"})
        self.assertEqual(set(result["due"]), {link, bat, seen})
        healthy = {link: State("on", self.current),
                   bat: State("80", self.current),
                   seen: State(datetime.fromtimestamp(self.current, timezone.utc).isoformat(),
                               self.current)}
        self.assertEqual(self.render("unhealthy_now", healthy, connectivity=[link],
                          batteries=[bat], last_seen_entities=[seen])["names"], [])

    def test_closed_and_health_recovery_do_not_mask_other_issues(self):
        names = ["binary_sensor.hall", "binary_sensor.bath"]
        ctx = self.context({eid: State("off", self.current) for eid in names},
                           contacts=names)
        for name in ("all_contacts_closed", "all_health_ok"):
            template = next(n["variables"][name] for n in walk(self.data["actions"])
                            if isinstance(n, dict) and isinstance(n.get("variables"), dict)
                            and name in n["variables"])
            self.assertTrue(self.env.from_string(template).render(**ctx))
        ctx["states"].values[names[1]] = State("unavailable", self.current)
        for name in ("all_contacts_closed", "all_health_ok"):
            template = next(n["variables"][name] for n in walk(self.data["actions"])
                            if isinstance(n, dict) and isinstance(n.get("variables"), dict)
                            and name in n["variables"])
            self.assertFalse(self.env.from_string(template).render(**ctx))

    def test_service_whitelist_and_docs(self):
        result = self.env.from_string(
            "{{ recipient is match('^notify\\.mobile_app_[a-z0-9_]+$') }}"
        )
        self.assertTrue(result.render(recipient="notify.mobile_app_person"))
        for action in ("notify.notify", "shell_command.evil", "notify.mobile_app_x;bad"):
            self.assertFalse(result.render(recipient=action))
        guide = (PATH.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn(self.data["blueprint"]["source_url"], guide)
        self.assertIn("blueprints_updater.reload", guide)
        self.assertIn("cannot prove", guide.lower())


if __name__ == "__main__":
    unittest.main()
