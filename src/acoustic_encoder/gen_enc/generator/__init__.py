"""Pure GEN-ENC-2B technical generator primitives.

The public surface is intentionally restricted to the names exported by
``api``.  All returned records are technical conformance objects, not
scientific identities.
"""

from .api import (
    audit_abstract_cad,
    canonical_json_bytes,
    load_literal_family_table,
    map_volume_partition,
    open_interval_uniform53,
    physics_midpoint_lhs,
    random_parameters,
    sha256_lower_hex,
    solve_cavity_length_bisection,
    splitmix64,
    validate_source_bundle,
)

__all__ = [
    "audit_abstract_cad",
    "canonical_json_bytes",
    "load_literal_family_table",
    "map_volume_partition",
    "open_interval_uniform53",
    "physics_midpoint_lhs",
    "random_parameters",
    "sha256_lower_hex",
    "solve_cavity_length_bisection",
    "splitmix64",
    "validate_source_bundle",
]
