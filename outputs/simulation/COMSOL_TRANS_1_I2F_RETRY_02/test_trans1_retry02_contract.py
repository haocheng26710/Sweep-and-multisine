from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OLD = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_01/run_trans1_retry01.py"
NEW = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02/run_trans1_retry02.py"


def test_retry01_reproduces_stale_study_order():
    source = OLD.read_text(encoding="utf-8")
    build = source.index("R0.build_model(")
    refine = source.index("refine_mesh(model", build)
    assert build < refine
    assert "java.study().remove(\"std_freq\")" not in source


def test_retry02_recreates_study_after_fine_mesh():
    source = NEW.read_text(encoding="utf-8")
    remove = source.index('java.study().remove("std_freq")')
    mesh = source.index("refine_mesh(model", remove)
    recreate = source.index('create_frequency_study(model', mesh)
    assert remove < mesh < recreate


def test_retry02_audits_solution_and_explicit_dataset():
    source = NEW.read_text(encoding="utf-8")
    assert "java.sol().tags()" in source
    assert ".isEmpty()" in source
    assert "java.result().dataset().tags()" in source
    assert "dataset_tag=dataset_tag" in source
    assert "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET" in source


def test_frozen_identifiers_and_scope():
    source = NEW.read_text(encoding="utf-8")
    assert "FORMAL_FREQ = 200.0 * 2.0 ** (np.arange(256) / 48.0)" in source
    assert "WINDOW_HALF_OCTAVE = 1.0 / 6.0" in source
    assert "final_test_read" in source
    assert "external" not in source.lower()
