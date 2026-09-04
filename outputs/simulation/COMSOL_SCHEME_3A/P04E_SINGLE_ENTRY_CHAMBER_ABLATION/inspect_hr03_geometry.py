"""Read-only inspection of the frozen P04B-N HR03 geometry tree."""

from pathlib import Path
import mph

MODEL = Path(r"D:\Bristol course\dissertation\program work\outputs\simulation\COMSOL_SCHEME_3A\P04B_NOMINAL_CROSS_MODULE_VALIDATION\P04BN_HR03_PRODUCTION.mph")

mph.option("session", "stand-alone")
client = mph.start(cores=2)
model = client.load(MODEL)
geom = model.java.component("comp1").geom("geom1")
for raw_tag in geom.feature().tags():
    tag = str(raw_tag)
    feature = geom.feature(tag)
    print(f"{tag}\t{feature.getType()}\t{feature.label()}")
    if tag.startswith("ch_"):
        for prop in ("pos", "r", "h", "selresult", "intbnd"):
            try:
                print(f"  {prop}={feature.getStringArray(prop) if prop == 'pos' else feature.getString(prop)}")
            except Exception:
                pass
print("SELECTIONS")
comp = model.java.component("comp1")
for raw_tag in comp.selection().tags():
    tag = str(raw_tag)
    if tag in {"sel_chamber", "sel_fixed_inner_000", "sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer", "sel_hr_module_all", "sel_fluid_all", "sel_mic_nominal", "bnd_port_000"}:
        selection = comp.selection(tag)
        print(f"{tag}\t{selection.getType()}\t{list(selection.entities())}")
        for prop in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax", "condition"):
            try:
                print(f"  {prop}={selection.getString(prop)}")
            except Exception:
                pass
try:
    measure = geom.measureFinal()
    measure.selection().geom("geom1", 3)
    measure.selection().set([int(x) for x in comp.selection("sel_chamber").entities()])
    print(f"CHAMBER_MEASURE_M3={measure.getVolume()}")
except Exception as error:
    print(f"CHAMBER_MEASURE_ERROR={error!r}")
    print([name for name in dir(geom.measureFinal().selection()) if not name.startswith("_")])
    print([name for name in dir(geom) if "meas" in name.lower()])
try:
    object_measure = geom.measure()
    object_measure.selection().set("ch_low_center", 3, [1])
    print(f"CHAMBER_OBJECT_MEASURE_M3={object_measure.getVolume()}")
except Exception as error:
    print(f"CHAMBER_OBJECT_MEASURE_ERROR={error!r}")
client.remove(model)
client.clear()
