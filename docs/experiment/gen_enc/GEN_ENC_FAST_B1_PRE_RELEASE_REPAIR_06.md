# GEN-ENC FAST B1 PRE-RELEASE-REPAIR-06 contract

Repair-06 is an additive implementation of the common two-phase guardian posterior-anchor protocol for task `01a049a7-15ca-79e1-92a2-d3822ba8609d`, batch B1, and mode `FORMAL_B1_EXACT_20_TYPED_CAD`.

The Phase-A release is a new three-command, zero-publication contract. It binds the task/batch/run, exact roots, FAST-0 authority allowlist, source/schema/command manifests, typed CAD projection, dependency matrix and structure hashes, expiry/revocation, and distinct Phase-A dispatch. Successful verification creates a canonical 27-subject control seal and 31-artifact staging graph, then writes the canonical handoff and stops.

Phase-B commands require six explicit external arguments: guardian authorization path and expected SHA256, guardian attestation path and expected SHA256, and controller dispatch path and expected SHA256. Paths are frozen; hashes must be supplied externally. Only after byte hash, canonical, schema, complete binding, handoff, subject-seal, and current 31-graph validation may `publish`, `recover`, or `package-results` proceed. Phase-B dispatch has a distinct id and exclusive one-time consumption.

Technical fixtures exist only under task-owned temporary roots. They are non-authoritative mirrors and cannot be promoted. No formal authority was read and no formal control record or scientific artifact was created during this freeze.
