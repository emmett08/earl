# Reservation study fixture

Only `source/` and the current feature brief are copied to a coding
episode. The independent `host/` directory contains cumulative assessment
and a positive control. B reserves all rooms in a bundle atomically;
C moves that bundle while excluding its own booking IDs from availability
checks; D cancels all current bundle bookings after possible movement.

The source-derived premise exercised in C is the authority of
`InMemoryCalendar.bookings` for current availability. A historical
`BundleReceipt` records the original interval and cannot determine current
availability after a move. The safe choice is to check current active
bookings under the calendar lock, excluding only the bundle's own IDs.
This note specifies host-side assessment and is never copied to a coding
worktree.
