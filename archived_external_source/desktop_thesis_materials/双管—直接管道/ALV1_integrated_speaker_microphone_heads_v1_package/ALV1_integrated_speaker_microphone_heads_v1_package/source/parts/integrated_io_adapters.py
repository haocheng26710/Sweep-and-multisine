"""Direct V1.3 end-plug adapters for the speaker and microphone heads."""

from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq

import v1_params as p
from geometry_utils import cone, cylinder
from parts.end_adapters import _end_plug_shell


@dataclass(frozen=True)
class IntegratedAdapterSpec:
    socket_id_mm: float
    socket_od_mm: float
    socket_depth_mm: float = 10.0
    transition_length_mm: float = 4.0
    acoustic_bore_mm: float = 2.8
    main_tube_bore_mm: float = (
        p.BARB_INTERNAL_BORE + p.FDM_ACOUSTIC_HOLE_COMPENSATION
    )
    external_extension_mm: float = 16.0


ADAPTER_SPECS = {
    "speaker": IntegratedAdapterSpec(socket_id_mm=6.2, socket_od_mm=10.2),
    "microphone": IntegratedAdapterSpec(socket_id_mm=8.8, socket_od_mm=13.0),
}


def make_integrated_io_adapter(kind: str) -> cq.Workplane:
    """Join one device socket directly to the calibrated V1.3 end plug.

    The original 10 mm soft-tube spigot and the V1.3 10 mm hose barb are both
    omitted.  A four-millimetre structural transition remains, but it is part
    of the same printed solid.  The device socket and calibrated tube interface
    retain their original dimensions.
    """

    key = kind.strip().lower()
    if key not in ADAPTER_SPECS:
        raise ValueError(f"Unknown integrated adapter kind: {kind!r}")
    spec = ADAPTER_SPECS[key]

    device_face_x = -spec.external_extension_mm
    socket_back_x = device_face_x + spec.socket_depth_mm
    transition_end_x = socket_back_x + spec.transition_length_mm
    if abs(transition_end_x + 2.0) > 1.0e-9:
        raise ValueError("Integral transition must meet the V1.3 flange at x=-2 mm")

    body = _end_plug_shell()
    socket_shell = cylinder(
        (device_face_x, 0.0, 0.0),
        (1, 0, 0),
        spec.socket_od_mm,
        spec.socket_depth_mm,
    )
    outer_transition = cone(
        (socket_back_x, 0.0, 0.0),
        (1, 0, 0),
        spec.socket_od_mm,
        p.END_LOCAL_COLLAR_OD,
        spec.transition_length_mm,
    )
    body = body.union(socket_shell).union(outer_transition)

    # Preserve the original 10 mm device insertion depth.  A flat shoulder
    # from the large socket to the 2.8 mm bore would create an internal bridge
    # in the upright print orientation, so the required four-millimetre outer
    # transition also carries a self-supporting tapered internal passage.
    device_socket = cylinder(
        (device_face_x - 0.2, 0.0, 0.0),
        (1, 0, 0),
        spec.socket_id_mm,
        spec.socket_depth_mm + 0.2,
    )
    socket_to_bore = cone(
        (socket_back_x, 0.0, 0.0),
        (1, 0, 0),
        spec.socket_id_mm,
        spec.acoustic_bore_mm,
        spec.transition_length_mm,
    )
    bore_transition = cone(
        (-2.0, 0.0, 0.0),
        (1, 0, 0),
        spec.acoustic_bore_mm,
        spec.main_tube_bore_mm,
        2.0,
    )
    main_bore = cylinder(
        (-0.05, 0.0, 0.0),
        (1, 0, 0),
        spec.main_tube_bore_mm,
        p.END_SOCKET_DEPTH + 0.25,
    )
    return (
        body
        .cut(device_socket)
        .cut(socket_to_bore)
        .cut(bore_transition)
        .cut(main_bore)
        .clean()
    )


def make_integrated_speaker_adapter() -> cq.Workplane:
    return make_integrated_io_adapter("speaker")


def make_integrated_microphone_adapter() -> cq.Workplane:
    return make_integrated_io_adapter("microphone")


def all_integrated_io_adapters() -> dict[str, cq.Workplane]:
    return {
        "ALV1_integrated_speaker_socket_6p2_end_plug": (
            make_integrated_speaker_adapter()
        ),
        "ALV1_integrated_microphone_socket_8p8_end_plug": (
            make_integrated_microphone_adapter()
        ),
    }
