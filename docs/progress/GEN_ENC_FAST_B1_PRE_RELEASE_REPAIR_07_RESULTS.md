# GEN-ENC FAST B1 PRE-RELEASE-REPAIR-07 Results

Status: `READY_FOR_INTERMEDIATE_AND_ADVISOR_B_RE_REVIEW_FORMAL_EXECUTION_BLOCKED`.

The Repair-07 suite passed 57 tests in 238.16 seconds and 244.52 seconds, then passed the final 58-test suite against the complete consumed-record runtime binding in 248.87 seconds. It includes the exact coherent three-Phase-A-path re-anchor falsifier, strict claim/count/missing/extra record attacks, consumed-record revalidation, verify-fail then same-run restore denial, mixed handoff/failure zero-copy denial, Phase-B post-copy rollback, eight-process one-use, twenty real target kills, and four commit-boundary recoveries.

Historical regression results are: Repair-06 41 passed in 179.26 seconds; Repair-05 59 passed in 140.67 seconds; Repair-04 28 passed in 47.26 seconds; Repair-03 48 passed in 73.24 seconds; Repair-02 31 passed in 2.82 seconds; Repair-01 51 passed in 24.15 seconds; original freeze 44 passed in 15.08 seconds. Historical regression total is 302; combined current validation total is 360.

Retained failed iterations include the initial Repair-07 copied-baseline run (40 passed, 1 failed: one-use error-order mismatch), the first focused run (9 passed, 1 failed: Windows path length), and the second focused run (1 passed, 9 failed: handoff schema/writer required-field synchronization). No cleanup was performed; task-owned basetemp residue remains.

Formal counters remain zero for authority reads, members, static runs, publications, Phase-A/B control records, handoffs, side records, commit pointers, and package terminals. The DRAFT remains attempt 0, non-authoritative, all permissions false, and run_id null. `final_test_read=false`.
