"""Static and Jinja behavior checks for multi-room contact alerts."""
from pathlib import Path
from types import SimpleNamespace
import re
import unittest
import jinja2
import yaml

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"blueprints/automation/multi_room_contact_watchdog/multi_room_contact_watchdog.yaml"

class Loader(yaml.SafeLoader):
    pass

Loader.add_constructor("!input",lambda loader,node:"!input "+loader.construct_scalar(node))

def walk(node):
    if isinstance(node,dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node,list):
        for value in node:
            yield from walk(value)

def find_var(node,key):
    for item in walk(node):
        if isinstance(item,dict) and isinstance(item.get("variables"),dict):
            if key in item["variables"]:
                return item["variables"][key]
    raise KeyError(key)

class ContactWatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=PATH.read_text(encoding="utf-8")
        cls.data=yaml.load(cls.source,Loader=Loader)
        cls.inputs={name:value for section in cls.data["blueprint"]["input"].values()
                    for name,value in section["input"].items()}
        cls.jinja=jinja2.Environment(trim_blocks=True,lstrip_blocks=True)
        cls.jinja.globals["is_number"]=lambda value: bool(re.fullmatch(r"[0-9]+(?:\\.[0-9]+)?",str(value).strip()))

    def render(self,key,**vars):
        return self.jinja.from_string(find_var(self.data["actions"],key)).render(**vars).strip()

    def test_blueprint_form_version_and_triggers(self):
        self.assertEqual(self.data["blueprint"]["homeassistant"]["min_version"],"2026.11.0")
        self.assertEqual(self.data["mode"],"queued")
        obj=self.inputs["room_entries"]["selector"]["object"]
        self.assertTrue(obj["multiple"])
        self.assertEqual(obj["label_field"],"name")
        self.assertEqual(self.inputs["room_entries"]["default"],[])
        self.assertTrue({"name","contacts","enabled","issue_state","open_after_minutes",
                         "offline_after_minutes","monitor_offline","last_seen_hours"}.issubset(obj["fields"]))
        self.assertEqual(obj["fields"]["last_seen_hours"]["default"],0)
        self.assertTrue(obj["fields"]["monitor_offline"]["default"])
        for field in obj["fields"].values():
            self.assertNotIn("description",field)
        triggers=self.data["triggers"]
        self.assertEqual([(t["id"],t["trigger"]) for t in triggers],
                         [("contact_changed","state"),("deadline_check","time_pattern"),
                          ("startup","homeassistant"),("startup","event")])
        self.assertEqual(triggers[0]["entity_id"],"!input monitored_contacts")
        self.assertEqual(triggers[1]["minutes"],"/1")
        self.assertNotIn("state_changed",self.source)

    def test_all_references_and_templates_parse(self):
        refs=set(re.findall(r"!input\s+([A-Za-z0-9_]+)",self.source))
        self.assertFalse(refs-set(self.inputs))
        n=0
        for node in walk(self.data):
            if isinstance(node,dict):
                for value in node.values():
                    if isinstance(value,str) and ("{{" in value or "{%" in value):
                        self.jinja.parse(value)
                        n+=1
        self.assertGreater(n,25)

    def test_independent_issue_types(self):
        cases=[
            ("open","on","on",True,0,0,True),
            ("open","off","on",True,0,0,False),
            ("open","off","off",True,0,0,True),
            ("offline","unavailable","on",True,0,0,True),
            ("offline","unknown","on",False,0,0,False),
            ("offline","on","on",True,0,0,False),
            ("silent","off","on",True,86400,1000,True),
            ("silent","off","on",True,86400,0,False),
            ("silent","unavailable","on",True,86400,1000,False),
        ]
        for kind,state,issue,monitor,silent,seen,expected in cases:
            self.assertEqual(self.render("alert_active",alert_type=kind,
                contact_state=state,issue_state=issue,offline_enabled=monitor,
                silent_seconds=silent,seen_since=seen),str(expected))

    def test_due_is_single_window_or_bounded_reminder(self):
        base=dict(alert_active=True,alert_started=1000,alert_delay=600,
                  trigger=SimpleNamespace(id="deadline_check"),repeat_minutes=0,
                  reminder_offsets_csv="")
        def due(age,**kw):
            return self.render("alert_due",elapsed_seconds=age,**(base|kw))=="True"
        self.assertFalse(due(599))
        self.assertTrue(due(600))
        self.assertTrue(due(659))
        self.assertFalse(due(660))
        self.assertFalse(due(1200))
        self.assertTrue(due(1200,repeat_minutes=10))
        self.assertFalse(due(1199,repeat_minutes=10))
        self.assertFalse(due(1260,repeat_minutes=10))
        self.assertFalse(due(1200,alert_active=False,repeat_minutes=10))
        self.assertTrue(due(1200,trigger=SimpleNamespace(id="startup")))

    def test_custom_notification_inputs_and_default_templates(self):
        notify_section=self.data["blueprint"]["input"]["notification_section"]["input"]
        advanced_section=self.data["blueprint"]["input"]["advanced_section"]["input"]
        for name in ("alert_title_template","alert_message_template"):
            self.assertIn(name,advanced_section)
            self.assertEqual(advanced_section[name]["selector"],{"template":{}})
        self.assertNotIn("on_alert_actions",notify_section)
        self.assertIn("on_alert_actions",advanced_section)
        self.assertIn("on_reminder_actions",advanced_section)
        self.assertEqual(self.inputs["on_reminder_actions"]["default"],[])
        self.assertNotIn("alert_title_template",notify_section)
        self.assertNotIn("alert_message_template",notify_section)
        self.assertEqual(self.inputs["on_alert_actions"]["default"],[])
        self.assertEqual(self.inputs["reminder_offsets_minutes"]["default"],"")
        self.assertEqual(self.inputs["reminder_offsets_minutes"]["selector"],{"text":{}})
        vars=dict(alert_type="open",room_name="Office",contact_label="Office window",
                  contact_id="binary_sensor.office_window",contact_state="on",
                  elapsed_minutes=12,issue_state="on")
        message=self.jinja.from_string(self.inputs["alert_message_template"]["default"]).render(**vars)
        title=self.jinja.from_string(self.inputs["alert_title_template"]["default"]).render(**vars)
        self.assertIn("Office window in Office has stayed open for 12 minutes",message)
        self.assertIn("Office: Office window left open",title)
        for kind in ("offline","silent"):
            rendered=self.jinja.from_string(self.inputs["alert_message_template"]["default"]).render(
                **(vars|{"alert_type":kind,"contact_state":"unavailable"}))
            self.assertIn("Office window",rendered)
        self.assertEqual(find_var(self.data["actions"],"alert_message"),"!input alert_message_template")
        self.assertEqual(find_var(self.data["actions"],"alert_title"),"!input alert_title_template")
        guide=(PATH.parent/"README.md").read_text()
        self.assertIn("{{ contact_label }}",guide)
        self.assertIn("Actions AFTER an initial warning",guide)
        self.assertIn("Actions AFTER each reminder",guide)

    def test_bundled_notification_and_separate_actions(self):
        self.assertIn("bundle_tag_prefix",self.data["variables"])
        self.assertIn("bundle_notification_message",self.source)
        self.assertIn("bundle_recovery_message",self.source)
        self.assertIn("!input on_reminder_actions",self.source)
        self.assertIn("!input on_alert_actions",self.source)
        self.assertIn('tag: "{{ bundle_tag }}"',self.source)
        self.assertIn('notification_id: "{{ bundle_tag }}"',self.source)
        self.assertIn('notification_id: "{{ alert_tag }}"',self.source)
        self.assertIn("Other unresolved {{ alert_type }} contacts",self.source)
        self.assertIn("Remaining {{ alert_type }} contacts",self.source)
        self.assertIn("bundle_members | count == 0",self.source)

    def test_specific_reminder_offsets_and_legacy_fallback(self):
        base=dict(alert_active=True,alert_started=1000,alert_delay=600,
                  trigger=SimpleNamespace(id="deadline_check"),repeat_minutes=2,
                  reminder_offsets_csv="5,15")
        def due(age,**kw):
            return self.render("alert_due",elapsed_seconds=age,**(base|kw))=="True"
        self.assertTrue(due(630))            # first alert at 10 minutes
        self.assertFalse(due(735))           # periodic interval suppressed
        self.assertTrue(due(930))            # 5 minutes after first deadline
        self.assertFalse(due(990))
        self.assertFalse(due(1230))
        self.assertTrue(due(1530))           # 15 minutes after first deadline
        self.assertFalse(due(1590))
        self.assertFalse(due(1830))          # no unexpected future repeats
        self.assertFalse(due(930,alert_active=False))
        self.assertTrue(due(930,reminder_offsets_csv="abc,-1,0,5,1500,15"))
        self.assertTrue(due(735,reminder_offsets_csv="invalid",repeat_minutes=2))
        self.assertFalse(due(930,reminder_offsets_csv="",repeat_minutes=0))

    def test_offline_and_last_seen_recovery(self):
        base=dict(prior_state="on",new_state="off",open_seconds=600,
                  offline_seconds=1200,silent_seconds=86400,
                  old_state_since=1000,old_last_seen=1000,
                  new_last_seen=99900,now=lambda:100000,as_timestamp=lambda x:x,
                  issue_state="on",offline_enabled=True)
        def recovered(kind,**kw):
            return self.render("recovered",alert_type=kind,**(base|kw))=="True"
        self.assertTrue(recovered("open"))
        self.assertFalse(recovered("open",new_state="on"))
        self.assertFalse(recovered("open",old_state_since=99990))
        self.assertTrue(recovered("offline",prior_state="unavailable",new_state="on"))
        self.assertTrue(recovered("offline",prior_state="unknown",new_state="off"))
        self.assertFalse(recovered("offline",prior_state="unknown",offline_enabled=False))
        self.assertTrue(recovered("silent"))
        self.assertFalse(recovered("silent",new_last_seen=1000))
        self.assertFalse(recovered("silent",old_last_seen=0))
        self.assertFalse(recovered("silent",silent_seconds=0))


    def test_notify_picker_and_independent_condition_sections(self):
        notify=self.inputs["notify_entities"]
        self.assertEqual(notify["default"],[])
        self.assertTrue(notify["selector"]["entity"]["multiple"])
        self.assertEqual(notify["selector"]["entity"]["filter"],[{"domain":"notify"}])
        self.assertEqual(self.inputs["notify_services"]["default"],"")  # migrated input
        self.assertEqual(self.inputs["open_alert_conditions"]["default"],[])
        self.assertEqual(self.inputs["health_alert_conditions"]["default"],[])
        self.assertIn("condition",self.inputs["open_alert_conditions"]["selector"])
        self.assertIn("condition",self.inputs["health_alert_conditions"]["selector"])
        sections=self.data["blueprint"]["input"]
        self.assertEqual(list(sections),["sensors_section","rooms_section",
                                         "notification_section","rules_section",
                                         "advanced_section"])
        self.assertIn("notify_entities",sections["notification_section"]["input"])
        self.assertIn("open_alert_conditions",sections["rules_section"]["input"])
        self.assertIn("health_alert_conditions",sections["rules_section"]["input"])
        self.assertIn("notify_services",sections["advanced_section"]["input"])
        self.assertIn("notify_conditions",sections["advanced_section"]["input"])
        self.assertIn("!input open_alert_conditions",self.source)
        self.assertIn("!input health_alert_conditions",self.source)
        self.assertIn("!input notify_conditions",self.source)
        self.assertRegex(self.source, r'target:\n\s+entity_id: "{{ notify_entity_ids }}"')
        self.assertIn("alert_type in ['offline', 'silent']",self.source)
        guide=(PATH.parent/"README.md").read_text()
        self.assertIn("outdoor temperature",guide)
        self.assertIn("not_home",guide)
        self.assertIn("one-shot behavior",guide.lower())

    def test_unique_tags_whitelisted_services_and_docs(self):
        self.assertEqual(self.render("alert_tag",contact_id="binary_sensor.bath",
                                     alert_type="open"),"contact_guard_binary_sensor_bath_open")
        self.assertEqual(self.render("alert_tag",contact_id="binary_sensor.bath",
                                     alert_type="offline"),"contact_guard_binary_sensor_bath_offline")
        actions={s["action"] for s in walk(self.data["actions"])
                 if isinstance(s,dict) and "action" in s}
        self.assertEqual(actions,{"system_log.write","persistent_notification.create",
                                  "persistent_notification.dismiss","{{ notify_action }}",
                                  "notify.send_message"})
        self.assertIn("notify_action | regex_match",self.source)
        self.assertTrue(self.inputs["persistent_enabled"]["default"])
        self.assertTrue(self.inputs["clear_on_recovery"]["default"])
        self.assertIn("2026.11.0",(PATH.parent/"README.md").read_text())
        self.assertIn("Multi-Room Door & Window Watchdog",(ROOT/"README.md").read_text())

if __name__=="__main__":
    unittest.main()
