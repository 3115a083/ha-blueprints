# Unlock Sequence

An event-driven Home Assistant automation blueprint for ordered button, bell, state, device, MQTT and event inputs. It can recognize **1–16 activations**, optionally lock out repeated failures, check independent authorization conditions, and perform user-configured actions only once.

**This is not a security-rated access-control system.** Door locks and alarm disarming require a separate trustworthy authorization factor, such as a physical access controller or explicitly verified local presence. Wireless buttons, doorbells, ordinary HA events, webhooks, and unauthenticated MQTT messages must **not** be treated as secrets.

## Import

Use **Settings → Automations & scenes → Blueprints → Import blueprint**:

\`\`\`text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/unlock_sequence/unlock_sequence.yaml
\`\`\`

[One-click import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Funlock_sequence%2Funlock_sequence.yaml)

Home Assistant **2026.10 or newer** is required. This blueprint uses merged trigger selector lists, action/condition selectors, limited-template time triggers, and a single running automation.

## First-run setup

1. Create an automation from the blueprint.
2. Choose exactly one input mode:
   - **Simple:** configure **one** Home Assistant trigger, set **repeat count** from 1 to 16. Example: a doorbell pressed four times.
   - **Advanced:** configure **distinct** Home Assistant triggers and assign each exactly one trigger ID from **A through P** in the trigger editor (use its YAML editor if necessary). Enter a code such as \`ABCD\`, \`ABCA\` or \`AAAA\` (max 16 characters). A repeated symbol reuses the same trigger subscription. **Do not configure a physical trigger more than once.**
3. Set the **whole-sequence timeout** and **maximum between-input gap** independently in seconds. Set either to zero to disable it. **At least one must be nonzero.**
4. Set debounce in milliseconds (300 by default), wrong-input policy, optional reuse of a wrong input as a fresh first step, start and final authorization conditions.
5. Configure persistent helpers if either failed-attempt protection or success cooldown is enabled. **The default success cooldown is 30 seconds, so its helper is required unless you set it to zero.**
6. Add the optional success/failure/lock-start/lock-end/result-error actions.
7. Test first using a notification, a test switch, or another harmless target.

The simple mode intentionally supports **one source repeated N times**. For different ordered buttons, use the advanced mode. Home Assistant blueprints cannot safely deduplicate arbitrary independently configured step-trigger lists while preserving unique, deterministic input identities; this limitation is preferred to silently counting one physical event multiple times.

### Advanced example

In the advanced trigger editor, configure these as two triggers (IDs must be written exactly):

\`\`\`yaml
- trigger: event
  event_type: demo_button
  event_data:
    button: one
  id: A
- trigger: event
  event_type: demo_button
  event_data:
    button: two
  id: B
\`\`\`

Set the advanced code to \`ABBA\`. Each distinct incoming event advances **at most one step**; repeated IDs in the code do not create extra subscriptions. Any duplicate trigger configurations or duplicate/undefined IDs are rejected at preflight. A pair of different, overlapping trigger definitions may still emit independent Home Assistant callbacks; choose disjoint trigger data and retain nonzero debounce. A true physical-event identity cannot be guaranteed for all integrations.

### Example: doorbell four times in ten seconds

- Simple trigger: an event corresponding to a single bell press.
- Repeat count: 4.
- Whole timeout: 10 s; per-input gap: 4 s; debounce: 300 ms.
- Start and final authorization: an independent trusted enablement condition.
- Successful action: initially a notification, **not a lock command**.
- Enable failed-attempt protection for a production installation, e.g. 3 failures within a fixed 15-minute window, followed by 5-minute lockout.

## Persistent helpers and setup

Home Assistant blueprints cannot create helpers automatically. Create the following **dedicated helpers for each automation**, either using **Settings → Devices & services → Helpers → Create helper** or the optional [sample package](helpers-package.example.yaml). Never share counters or deadline helpers between two automations.

| Helper | Type | Required when |
| --- | --- | --- |
| Failed-attempt counter | \`input_number\` (min 0, max at least 100, step 1) | Failure protection is enabled |
| Failure lock deadline | \`input_datetime\` with **date and time** | Failure protection is enabled |
| Failure-window start | \`input_datetime\` with **date and time** | Failure protection is enabled and fixed-window counting is selected |
| Success cooldown deadline | \`input_datetime\` with **date and time** | Success cooldown is above zero |

When creating helpers for the first time, initialize the counters to **0** and date/time helpers to a past date such as **2000-01-01 00:00:00** with Developer Tools → Actions (\`input_datetime.set_datetime\`). **Do not place \`initial:\` on helpers in the persistent package**, as it can override restored state after restarting. If the helpers show \`unknown\` or \`unavailable\`, the automation **fails closed** rather than allowing a success action. The automation does not initialize missing or unavailable protection helpers on its own.

For package-based setup, add \`homeassistant: packages: !include_dir_named packages\` to your HA configuration if not already configured, copy the example to \`packages/unlock_sequence.yaml\`, and adapt names. Restart/reload Home Assistant according to the normal helper lifecycle, initialize new helpers, and select the resulting entity IDs in the blueprint.

The **fixed** failure window starts on the first failure and does not slide with every failed attempt. For example, with 15 minutes configured, a failure at 12:00 starts a period ending at 12:15; the next failure after the period starts a new period. A successfully completed attempt can clear the counter either after final authorization or after an optional result confirmation. Failure-lock deadlines and success cooldown deadlines survive restarts when the helpers restore successfully. **Any incomplete code input is discarded** if Home Assistant or the automation restarts.

## Events, timeouts and action execution

- Wrong inputs can be ignored or counted as a failed attempt with reset. When reset is selected, a wrong input matching the first code symbol can optionally be reused to begin a fresh attempt. It still counts as a failure.
- Unrelated Home Assistant events that do **not** match configured source triggers are invisible to the blueprint. Only events from the selected trigger bank can be classified as wrong.
- The global debounce applies to physical events received less than the specified number of milliseconds since the last counted event. Very fast signals are discarded without failure.
- All starts and subsequent inputs are serialized by \`mode: single\` plus \`wait_for_trigger\`. Incoming triggers are ignored while user-defined success actions or result confirmation are in progress. Home Assistant scheduling can lose events in the tiny interval during rearming a wait; this is not a guaranteed lossless security keypad.
- After a correct sequence, final security conditions are evaluated immediately before the success action. If denied, no success action runs, and counting the rejection as a failure is configurable.
- Success actions run **once**, without retries. Success cooldown and failure-counter reset each support two timing choices: after successful final authorization, or after action and optional confirmation.
- Optional result verification requires **at least one confirmation condition** and **at least one trigger** that can change its truth value. The blueprint checks conditions immediately after actions and again on each confirmation trigger until the bounded timeout. If still unconfirmed, it executes \`error_actions\`. It does not poll.
- Home Assistant **cannot reliably catch arbitrary exceptions raised within a user-provided action sequence** to run another action. Such an exception stops the run and appears in HA traces/logs. The configured error action is specifically for confirmation timeout. Where a device can silently fail, enable result confirmation.
- A lock-expiry time trigger and a startup reconciliation clear expired failed-attempt lockouts and call \`lock_ended_actions\` once when the persisted count indicates a completed lockout. The success cooldown expires by deadline comparison, without polling.

### Limitations and security notes

- **Trigger spoofing:** use ACL-protected authenticated MQTT topics, trusted local integrations, and independent presence/authorization checks. No amount of button timing makes a doorbell code a strong credential.
- **Automation settings are trusted:** anyone who can edit this automation or selected helpers can bypass the protection. Protect Home Assistant administrator access and devices.
- **Time jumps/DST:** absolute local date-time helpers are converted to timestamps for comparison. Abrupt clock changes may shift wall-clock deadlines. Use reliable time synchronization.
- **Crash consistency:** writes to different Home Assistant helpers are not atomic. The blueprint writes the lockout deadline **before** raising the persistent failure counter, and refuses a future deadline even when the counter is smaller than the limit. However, a total shutdown during multi-helper writes may leave partly updated records. HA helpers are not an audited security transaction store.
- **High-rate inputs:** a 0 ms debounce disables its protection. Some integrations may deliver duplicates or near-simultaneous events independently, which cannot always be correlated. Configure disjoint triggers and a nonzero debounce.
- **Missed events and reloads:** ongoing sequences and waits do not resume on automation reload or HA restart; that is intentional. A lock-expiry notification missed during downtime is reconciled at startup only if helper values are available; if storage is unavailable then, a later eligible event can reconcile.
- **Physical safety:** Home Assistant scripts are not a failsafe or life-safety access controller. Validate on a test entity first. Add a physical/manual entry method and independent safeguards for real doors, garage actuators and alarms.

## Updating

Keep the canonical \`blueprint.source_url\` when importing. If you use [Blueprints Updater](https://github.com/luuquangvu/blueprints-updater), reload it with **Developer Tools → Actions → \`blueprints_updater.reload\`** after importing. Review changes before applying them to any live lock or alarm configuration.
