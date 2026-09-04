"""One-command exact-BREP build for Acoustic Ladder V1.0."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq

import v1_params as p
from acoustic_calcs import write_reports
from assemblies import save_all_assemblies
from bom import write_bom
from geometry_utils import bbox_tuple, export_step, export_stl, print_oriented
from package_v1 import PACKAGE_NAME, create_package
from parts.calibration_coupons import all_coupons
from parts.end_adapters import all_end_parts
from parts.joints import all_joint_parts
from parts.main_tubes import all_main_tubes
from parts.modules import all_modules
from parts.supports import all_support_parts
from validation import validate, write_dry_seal_report


ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
STEP_DIR = EXPORTS / "step"
STL_DIR = EXPORTS / "stl"
ASSEMBLY_DIR = EXPORTS / "assemblies"
REPORT_DIR = EXPORTS / "reports"
PRINT_PLATE_DIR = EXPORTS / "print_plates"
DELIVERY_DIR = ROOT.parents[1] / "outputs"


@dataclass
class PartRecord:
    name: str
    shape: cq.Workplane
    category: str
    print_axis: tuple | None = None
    print_degrees: float = 0.0


def _record_group(shapes, category, print_axis=None, print_degrees=0.0):
    return {
        name: PartRecord(name, shape, category, print_axis, print_degrees)
        for name, shape in shapes.items()
    }


def make_records(include_coupons: bool = True):
    records = {}
    tubes = all_main_tubes()
    for name, shape in tubes.items():
        degrees = 90.0 if "_TX_" in name else -90.0
        records[name] = PartRecord(name, shape, "tube", (1, 0, 0), degrees)
    records.update(_record_group(all_modules(), "module", (1, 0, 0), 90.0))
    records.update(_record_group(all_joint_parts(), "lock"))
    records.update(_record_group(all_end_parts(), "end"))
    records.update(_record_group(all_support_parts(), "support"))
    if include_coupons:
        records.update(_record_group(all_coupons(), "coupon"))
    return records


def _clean_generated_files():
    for directory in (STEP_DIR, STL_DIR, ASSEMBLY_DIR, REPORT_DIR, PRINT_PLATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.iterdir():
            if path.is_file():
                path.unlink()


def _json_safe_parameters():
    data = {}
    for key, value in vars(p).items():
        if not key.isupper():
            continue
        try:
            json.dumps(value)
        except TypeError:
            continue
        data[key] = value
    data["MODULE_PILOT_BASE_AND_TIP_CAD_DIAMETERS"] = list(p.module_pilot_diameters())
    data["JOINT_MALE_BASE_AND_TIP_CAD_DIAMETERS"] = list(p.joint_male_diameters())
    data["END_PLUG_BASE_AND_TIP_CAD_DIAMETERS"] = list(p.end_plug_diameters())
    return data


def write_parameter_json():
    path = REPORT_DIR / "params_v1.json"
    path.write_text(json.dumps(_json_safe_parameters(), indent=2,
                               ensure_ascii=False), encoding="utf-8")
    return path


def export_record(record: PartRecord):
    step_path = STEP_DIR / f"{record.name}_assembly.step"
    stl_path = STL_DIR / f"{record.name}_print.stl"
    export_step(record.shape, step_path)
    printable = print_oriented(record.shape, record.print_axis, record.print_degrees)
    export_stl(printable, stl_path, p.STL_LINEAR_TOLERANCE,
               p.STL_ANGULAR_TOLERANCE)
    if record.category == "coupon":
        shutil.copy2(stl_path, PRINT_PLATE_DIR / stl_path.name)
    return step_path, stl_path


def export_records(records):
    for index, record in enumerate(records.values(), start=1):
        print(f"[{index:02d}/{len(records):02d}] {record.name}", flush=True)
        export_record(record)


def _resolve_part(records, query: str):
    normalized = query.lower().replace("alv1_", "")
    matches = [record for name, record in records.items()
               if name.lower().replace("alv1_", "") == normalized or
               normalized in name.lower()]
    if len(matches) != 1:
        raise KeyError(f"Part query {query!r} matched {len(matches)} records")
    return matches[0]


def _copy_user_reports(package_path: Path, validation_path: Path,
                       acoustic_path: Path, dry_seal_path: Path):
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    targets = []
    for source in (package_path, validation_path, acoustic_path, dry_seal_path):
        target = DELIVERY_DIR / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        targets.append(target)
    return targets


def _print_summary(records, acoustic_data, validation_result, package_path):
    step_count = len(list(STEP_DIR.glob("*.step")))
    stl_count = len(list(STL_DIR.glob("*.stl")))
    assembly_count = len(list(ASSEMBLY_DIR.glob("*.step")))
    dimensions = {name: bbox_tuple(record.shape) for name, record in records.items()}
    largest_name, largest_dims = max(
        dimensions.items(), key=lambda row: max(row[1])
    )
    td = acoustic_data["main_teardrop"]
    print("\n" + "=" * 72)
    print(p.VERSION)
    print(f"Parts: {len(records)} | STEP: {step_count} | STL: {stl_count} | Assemblies: {assembly_count}")
    print(f"Watertight validation: PASS={validation_result['pass']} WARNING={validation_result['warning']} FAIL={validation_result['fail']}")
    print(f"Largest part: {largest_name} = {largest_dims[0]:.2f} x {largest_dims[1]:.2f} x {largest_dims[2]:.2f} mm")
    print(f"Main area / hydraulic diameter: {td['area_mm2']:.4f} mm^2 / {td['hydraulic_diameter_mm']:.4f} mm")
    for key, row in acoustic_data["bridges"].items():
        ratios = row["relative_impedance_magnitude"]
        print(f"{key}: Leff={row['effective_length_mm']:.3f} mm, Zratio@1k={ratios['1000']:.3f}, fq={row['quarter_wave_frequency_hz']:.1f} Hz")
    delays = acoustic_data["node_round_trip_delays"]
    print("Node round-trip delays (ms): " + ", ".join(
        f"{key}={row['round_trip_delay_ms']:.3f}" for key, row in delays.items()))
    print("Assembly collision policy: EXPECTED_INTERFERENCE only at the three calibrated cone-fit families")
    print(f"Module cone target interference: {p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE:.3f} mm")
    print(f"Split-joint cone target interference: {p.JOINT_DRY_SEAL_DIAMETRAL_INTERFERENCE:.3f} mm")
    print(f"End cone target interference: {p.END_DRY_SEAL_DIAMETRAL_INTERFERENCE:.3f} mm")
    print(f"Four calibration values generated: {p.DRY_SEAL_INTERFERENCE_TEST_VALUES}")
    print("Flexible-seal part count: 0")
    print(f"ZIP: {package_path}")
    print("=" * 72)


def full_build():
    _clean_generated_files()
    print("Generating exact OCCT BREP parts...", flush=True)
    records = make_records(include_coupons=True)
    export_records(records)
    write_parameter_json()
    write_bom(REPORT_DIR / "BOM.csv")
    _, acoustic_md, acoustic_data = write_reports(REPORT_DIR)
    _, dry_seal_txt = write_dry_seal_report(REPORT_DIR)
    print("Generating four assembly STEP files...", flush=True)
    save_all_assemblies({name: record.shape for name, record in records.items()}, ASSEMBLY_DIR)
    print("Validating BREP/STL geometry and design invariants...", flush=True)
    result = validate(ROOT, records)
    if result["fail"]:
        print(result["path"].read_text(encoding="utf-8"))
        raise RuntimeError(f"Validation failed with {result['fail']} failure(s)")
    package_path = create_package(DELIVERY_DIR / PACKAGE_NAME)
    _copy_user_reports(package_path, result["path"], acoustic_md, dry_seal_txt)
    _print_summary(records, acoustic_data, result, package_path)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="Build, validate and package everything")
    mode.add_argument("--part", help="Export one named part")
    mode.add_argument("--assemblies", action="store_true", help="Generate the four assembly STEP files")
    mode.add_argument("--coupons", action="store_true", help="Generate all calibration coupons")
    mode.add_argument("--validate", action="store_true", help="Validate existing exports")
    args = parser.parse_args(argv)

    if args.part:
        records = make_records(include_coupons=True)
        record = _resolve_part(records, args.part)
        export_record(record)
        print(record.name)
        return 0
    if args.assemblies:
        records = make_records(include_coupons=False)
        save_all_assemblies({name: record.shape for name, record in records.items()}, ASSEMBLY_DIR)
        return 0
    if args.coupons:
        records = _record_group(all_coupons(), "coupon")
        export_records(records)
        return 0
    if args.validate:
        records = make_records(include_coupons=True)
        result = validate(ROOT, records)
        print(result["path"])
        return 1 if result["fail"] else 0
    return full_build()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"BUILD FAIL: {exc}", file=sys.stderr)
        raise

