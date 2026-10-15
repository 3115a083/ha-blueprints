# Changelog

## 1.0.0 - 2026-10-15

- Add an unlimited repeated-entry form for independent device targets and local conditions.
- Apply a global maximum runtime unless an entry supplies its own runtime.
- Support per-entry global conditions as AND, OR, or ignored, plus always-required safety conditions.
- Provide local state/away rules with hold times and ALL/ANY logic; complex per-device logic can use a Template Binary Sensor helper.
- Support lights, switches, thermostats, media players, fans, humidifiers and input booleans with explicit single-entity service targets.
- Default to preview; record one shutdown attempt per target state period with dedicated date/time helpers.
- Recheck rules and target state after recording the attempt; isolate failed commands and failed helper writes.
- Document minute-resolution timing, restart behavior, media action choices and real heating implications.
- Add real Home Assistant 2026.10.1 schema/selector/script tests, including concurrency guards, failed services, time boundaries and input failures.

Repository test maintenance: existing occupancy tests contained outdated label/condition-location assertions and a datetime-unaware timestamp stub. Existing Govee tests did not reproduce HA whitespace-to-native-value conversion. Correct those test fixtures without changing any older blueprint's runtime behavior or removing its safety assertions.
