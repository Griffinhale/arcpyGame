# Buyout Legibility Playtest Note

Date: 2026-06-04

## Purpose

Record the current closure evidence for district identity and buyout legibility.
This is not a balance-final report; it documents whether the first-pass system
is understandable enough to close the broad implementation issue and split
larger bidding design into follow-up work.

## Current Evidence

- District names remain the player-facing label while `cell_id` remains the
  stable save key.
- Docket generation varies by seed and district type distribution.
- Low-activity districts can refuse bids, enter contested buyout, stabilize, or
  convert through deterministic rules.
- Buyout reports now name the target district, bidder, bidder type, reason, and
  the player-facing control hint: office attention can still stabilize a
  contested district before conversion.
- Successful attention reduces hidden buyout pressure, with regression coverage
  for ordinary and mitigated approvals.
- Seed `2026` has automated 12-week coverage that reaches final audit and
  exercises buyout pressure without requiring the player to inspect raw ledger
  state.

## Closure Decision

The broad district-identity/buyout implementation is closeable with the current
first-pass rules, reports, persistence, and tests.

Keep larger bidding design as follow-up scope:

- richer round-robin or multi-bid negotiation,
- fuller RNG keys that include target/candidate/ledger snapshots,
- deeper balance tuning for how often conversions happen,
- live ArcGIS screenshots or recordings showing whether map symbols are enough
  for non-technical players.

## Verification

Automated checks:

```text
python -m pytest tests/test_permit_office_rules.py -q
```

Expected result:

```text
91 passed
```

Manual ArcGIS smoke testing should still record whether contested, vulnerable,
and converted districts are visually legible on the target presentation machine.
