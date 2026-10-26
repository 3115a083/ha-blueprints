# Changelog

## 2026-10-26 — Initial release and security hardening

- Add ordered sequence recognition, independent authorization conditions, persistent failure lockouts and success cooldown, and event-driven result verification.
- Revalidate required helpers during collection and before success; reject fractional, invalid and undersized failure counters and reused active datetime helpers.
- Reject overlapping or unprovably disjoint trigger banks. Arbitrary HA integrations remain usable as a single reusable source.
- Keep ignored wrong inputs from extending the gap deadline.
- Persist and verify lockout records before running optional lock-start actions, so a notification error cannot lose a failure record.
- Round timestamp deadline writes up to a whole second.
- Add offline regression tests and real HA script tests. Native HA event delivery, arbitrary action exception handling, clock/DST restoration and non-atomic helper persistence remain documented limitations.
