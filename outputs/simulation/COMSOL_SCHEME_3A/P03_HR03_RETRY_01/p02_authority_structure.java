/*
 * p02_authority_structure.java
 */

import com.comsol.model.*;
import com.comsol.model.util.*;

/** Model exported on Aug 25 2026, 11:17 by COMSOL 6.4.0.293. */
public class p02_authority_structure {

  public static Model run() {
    Model model = ModelUtil.create("Model");

    model
         .modelPath("D:\\Bristol course\\dissertation\\program work\\outputs\\simulation\\COMSOL_SCHEME_3A\\P02_P05_BASELINE");

    model.label("P02_P05_BASELINE");

    model.component().create("comp1", true);

    model.component("comp1").geom().create("geom1", 3);

    model.param().set("r_ch", "18[mm]");
    model.param().set("r_ch", "18[mm]", "Nominal central chamber radius");
    model.param().set("z_fixed", "3[mm]");
    model.param().set("z_fixed", "3[mm]", "Base floor / fixed-air lower z");
    model.param().set("h_fixed", "9.2[mm]");
    model.param().set("h_fixed", "9.2[mm]", "Nominal fixed passage and chamber air height");
    model.param().set("r_inner_start", "17[mm]");
    model.param().set("r_inner_start", "17[mm]", "Fixed inner passage start; 1 mm overlap into chamber");
    model.param().set("r_module_inner", "32[mm]");
    model.param().set("r_module_inner", "32[mm]", "Module inner interface radius");
    model.param().set("r_module_outer", "88[mm]");
    model.param().set("r_module_outer", "88[mm]", "Module outer interface radius");
    model.param().set("r_outer_face", "105[mm]");
    model.param().set("r_outer_face", "105[mm]", "Outer face radius");
    model.param().set("w_fixed", "8[mm]");
    model.param().set("w_fixed", "8[mm]", "Fixed inner passage width");
    model.param().set("w_outer", "16[mm]");
    model.param().set("w_outer", "16[mm]", "Outer port width");
    model.param().set("z_module", "4.2[mm]");
    model.param().set("z_module", "4.2[mm]", "Module air lower z = base floor + tray bottom skin");
    model.param().set("h_module", "6.4[mm]");
    model.param().set("h_module", "6.4[mm]", "P05 channel air height");
    model.param().set("w_module", "9.4[mm]");
    model.param().set("w_module", "9.4[mm]", "P05 straight channel width");
    model.param().set("p10_depth", "12[mm]");
    model.param().set("p10_depth", "12[mm]", "Nominal P10 insertion depth");
    model.param().set("r_p10_tip", "93[mm]");
    model.param().set("r_p10_tip", "93[mm]", "Nominal blocked branch fluid end = 105-12 mm");
    model.param().set("r_mic", "4.4[mm]");
    model.param().set("r_mic", "4.4[mm]", "Nominal microphone disk radius from measured 8.8 mm front diameter");
    model.param().set("z_mic", "7[mm]");
    model.param().set("z_mic", "7[mm]", "Nominal microphone sampling plane");
    model.param().set("c0_nom", "343[m/s]");
    model.param().set("c0_nom", "343[m/s]", "Nominal speed of sound");
    model.param().set("rho0_nom", "1.2041[kg/m^3]");
    model.param().set("rho0_nom", "1.2041[kg/m^3]", "Nominal air density");
    model.param().set("p_inc", "1[Pa]");
    model.param().set("p_inc", "1[Pa]", "Sparse diagnostic incident/source pressure");
    model.param().set("f_diag_max", "7000[Hz]");
    model.param().set("f_diag_max", "7000[Hz]", "Sparse diagnostic maximum frequency");

    model.component("comp1").geom("geom1").feature().create("ch_low_center", "Cylinder");
    model.component("comp1").geom("geom1").feature("ch_low_center").set("pos", new String[]{"0.0", "0.0", "0.003"});
    model.component("comp1").geom("geom1").feature("ch_low_center").set("r", "0.0044");
    model.component("comp1").geom("geom1").feature("ch_low_center").set("h", "0.004");
    model.component("comp1").geom("geom1").feature().create("ch_low_outer", "Cylinder");
    model.component("comp1").geom("geom1").feature("ch_low_outer").set("pos", new String[]{"0.0", "0.0", "0.003"});
    model.component("comp1").geom("geom1").feature("ch_low_outer").set("r", "0.018");
    model.component("comp1").geom("geom1").feature("ch_low_outer").set("h", "0.004");
    model.component("comp1").geom("geom1").feature().create("ch_low_hole", "Cylinder");
    model.component("comp1").geom("geom1").feature("ch_low_hole").set("pos", new String[]{"0.0", "0.0", "0.003"});
    model.component("comp1").geom("geom1").feature("ch_low_hole").set("r", "0.0044");
    model.component("comp1").geom("geom1").feature("ch_low_hole").set("h", "0.004");
    model.component("comp1").geom("geom1").feature().create("ch_low_annulus", "Difference");
    model.component("comp1").geom("geom1").feature("ch_low_annulus").selection("input").set("ch_low_outer");
    model.component("comp1").geom("geom1").feature("ch_low_annulus").selection("input2").set("ch_low_hole");
    model.component("comp1").geom("geom1").feature().create("ch_up_center", "Cylinder");
    model.component("comp1").geom("geom1").feature("ch_up_center").set("pos", new String[]{"0.0", "0.0", "0.007"});
    model.component("comp1").geom("geom1").feature("ch_up_center").set("r", "0.0044");
    model.component("comp1").geom("geom1").feature("ch_up_center").set("h", "0.0052");
    model.component("comp1").geom("geom1").feature().create("ch_up_outer", "Cylinder");
    model.component("comp1").geom("geom1").feature("ch_up_outer").set("pos", new String[]{"0.0", "0.0", "0.007"});
    model.component("comp1").geom("geom1").feature("ch_up_outer").set("r", "0.018");
    model.component("comp1").geom("geom1").feature("ch_up_outer").set("h", "0.0052");
    model.component("comp1").geom("geom1").feature().create("ch_up_hole", "Cylinder");
    model.component("comp1").geom("geom1").feature("ch_up_hole").set("pos", new String[]{"0.0", "0.0", "0.007"});
    model.component("comp1").geom("geom1").feature("ch_up_hole").set("r", "0.0044");
    model.component("comp1").geom("geom1").feature("ch_up_hole").set("h", "0.0052");
    model.component("comp1").geom("geom1").feature().create("ch_up_annulus", "Difference");
    model.component("comp1").geom("geom1").feature("ch_up_annulus").selection("input").set("ch_up_outer");
    model.component("comp1").geom("geom1").feature("ch_up_annulus").selection("input2").set("ch_up_hole");
    model.component("comp1").geom("geom1").feature().create("inner_000", "Block");
    model.component("comp1").geom("geom1").feature("inner_000").set("pos", new String[]{"-0.004", "0.017", "0.003"});
    model.component("comp1").geom("geom1").feature("inner_000")
         .set("size", new String[]{"0.008", "0.015", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("p05_000", "Block");
    model.component("comp1").geom("geom1").feature("p05_000").set("pos", new String[]{"-0.0047", "0.032", "0.0042"});
    model.component("comp1").geom("geom1").feature("p05_000").set("size", new String[]{"0.0094", "0.056", "0.0064"});
    model.component("comp1").geom("geom1").feature().create("inner_090", "Block");
    model.component("comp1").geom("geom1").feature("inner_090").set("pos", new String[]{"0.017", "-0.004", "0.003"});
    model.component("comp1").geom("geom1").feature("inner_090")
         .set("size", new String[]{"0.015", "0.008", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("p05_090", "Block");
    model.component("comp1").geom("geom1").feature("p05_090").set("pos", new String[]{"0.032", "-0.0047", "0.0042"});
    model.component("comp1").geom("geom1").feature("p05_090").set("size", new String[]{"0.056", "0.0094", "0.0064"});
    model.component("comp1").geom("geom1").feature().create("inner_180", "Block");
    model.component("comp1").geom("geom1").feature("inner_180")
         .set("pos", new String[]{"-0.004", "-0.032", "0.003"});
    model.component("comp1").geom("geom1").feature("inner_180")
         .set("size", new String[]{"0.008", "0.015", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("p05_180", "Block");
    model.component("comp1").geom("geom1").feature("p05_180")
         .set("pos", new String[]{"-0.0047", "-0.088", "0.0042"});
    model.component("comp1").geom("geom1").feature("p05_180").set("size", new String[]{"0.0094", "0.056", "0.0064"});
    model.component("comp1").geom("geom1").feature().create("inner_270", "Block");
    model.component("comp1").geom("geom1").feature("inner_270")
         .set("pos", new String[]{"-0.032", "-0.004", "0.003"});
    model.component("comp1").geom("geom1").feature("inner_270")
         .set("size", new String[]{"0.015", "0.008", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("p05_270", "Block");
    model.component("comp1").geom("geom1").feature("p05_270")
         .set("pos", new String[]{"-0.088", "-0.0047", "0.0042"});
    model.component("comp1").geom("geom1").feature("p05_270").set("size", new String[]{"0.056", "0.0094", "0.0064"});
    model.component("comp1").geom("geom1").feature().create("outer_000_01", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_01")
         .set("pos", new String[]{"-0.004", "0.088", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_01")
         .set("size", new String[]{"0.008", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_02", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_02")
         .set("pos", new String[]{"-0.00425", "0.089", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_02")
         .set("size", new String[]{"0.0085", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_03", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_03")
         .set("pos", new String[]{"-0.0045", "0.09", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_03")
         .set("size", new String[]{"0.009", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_04", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_04")
         .set("pos", new String[]{"-0.00475", "0.091", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_04")
         .set("size", new String[]{"0.0095", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_05", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_05")
         .set("pos", new String[]{"-0.005", "0.092", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_05")
         .set("size", new String[]{"0.01", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_06", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_06")
         .set("pos", new String[]{"-0.00525", "0.093", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_06")
         .set("size", new String[]{"0.0105", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_07", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_07")
         .set("pos", new String[]{"-0.0055", "0.094", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_07")
         .set("size", new String[]{"0.011", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_08", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_08")
         .set("pos", new String[]{"-0.00575", "0.095", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_08")
         .set("size", new String[]{"0.0115", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_09", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_09")
         .set("pos", new String[]{"-0.006", "0.096", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_09")
         .set("size", new String[]{"0.012", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_10", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_10")
         .set("pos", new String[]{"-0.00625", "0.097", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_10")
         .set("size", new String[]{"0.0125", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_11", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_11")
         .set("pos", new String[]{"-0.0065", "0.09799999999999999", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_11")
         .set("size", new String[]{"0.013", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_12", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_12")
         .set("pos", new String[]{"-0.00675", "0.09899999999999999", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_12")
         .set("size", new String[]{"0.0135", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_13", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_13")
         .set("pos", new String[]{"-0.007", "0.09999999999999999", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_13")
         .set("size", new String[]{"0.014", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_14", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_14")
         .set("pos", new String[]{"-0.00725", "0.10099999999999999", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_14")
         .set("size", new String[]{"0.0145", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_15", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_15")
         .set("pos", new String[]{"-0.0075", "0.102", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_15")
         .set("size", new String[]{"0.015", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_16", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_16")
         .set("pos", new String[]{"-0.00775", "0.103", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_16")
         .set("size", new String[]{"0.0155", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_000_17", "Block");
    model.component("comp1").geom("geom1").feature("outer_000_17")
         .set("pos", new String[]{"-0.008", "0.104", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_000_17")
         .set("size", new String[]{"0.016", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_090_01", "Block");
    model.component("comp1").geom("geom1").feature("outer_090_01")
         .set("pos", new String[]{"0.088", "-0.004", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_090_01")
         .set("size", new String[]{"0.001", "0.008", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_090_02", "Block");
    model.component("comp1").geom("geom1").feature("outer_090_02")
         .set("pos", new String[]{"0.089", "-0.004294117647058823", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_090_02")
         .set("size", new String[]{"0.001", "0.008588235294117647", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_090_03", "Block");
    model.component("comp1").geom("geom1").feature("outer_090_03")
         .set("pos", new String[]{"0.09", "-0.0045882352941176464", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_090_03")
         .set("size", new String[]{"0.001", "0.009176470588235293", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_090_04", "Block");
    model.component("comp1").geom("geom1").feature("outer_090_04")
         .set("pos", new String[]{"0.091", "-0.004882352941176471", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_090_04")
         .set("size", new String[]{"0.001", "0.009764705882352943", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_090_05", "Block");
    model.component("comp1").geom("geom1").feature("outer_090_05")
         .set("pos", new String[]{"0.092", "-0.0051764705882352945", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_090_05")
         .set("size", new String[]{"0.001", "0.010352941176470589", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_180_01", "Block");
    model.component("comp1").geom("geom1").feature("outer_180_01")
         .set("pos", new String[]{"-0.004", "-0.089", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_180_01")
         .set("size", new String[]{"0.008", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_180_02", "Block");
    model.component("comp1").geom("geom1").feature("outer_180_02")
         .set("pos", new String[]{"-0.004294117647058823", "-0.09", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_180_02")
         .set("size", new String[]{"0.008588235294117647", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_180_03", "Block");
    model.component("comp1").geom("geom1").feature("outer_180_03")
         .set("pos", new String[]{"-0.0045882352941176464", "-0.091", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_180_03")
         .set("size", new String[]{"0.009176470588235293", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_180_04", "Block");
    model.component("comp1").geom("geom1").feature("outer_180_04")
         .set("pos", new String[]{"-0.004882352941176471", "-0.092", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_180_04")
         .set("size", new String[]{"0.009764705882352943", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_180_05", "Block");
    model.component("comp1").geom("geom1").feature("outer_180_05")
         .set("pos", new String[]{"-0.0051764705882352945", "-0.093", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_180_05")
         .set("size", new String[]{"0.010352941176470589", "0.001", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_270_01", "Block");
    model.component("comp1").geom("geom1").feature("outer_270_01")
         .set("pos", new String[]{"-0.089", "-0.004", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_270_01")
         .set("size", new String[]{"0.001", "0.008", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_270_02", "Block");
    model.component("comp1").geom("geom1").feature("outer_270_02")
         .set("pos", new String[]{"-0.09", "-0.004294117647058823", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_270_02")
         .set("size", new String[]{"0.001", "0.008588235294117647", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_270_03", "Block");
    model.component("comp1").geom("geom1").feature("outer_270_03")
         .set("pos", new String[]{"-0.091", "-0.0045882352941176464", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_270_03")
         .set("size", new String[]{"0.001", "0.009176470588235293", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_270_04", "Block");
    model.component("comp1").geom("geom1").feature("outer_270_04")
         .set("pos", new String[]{"-0.092", "-0.004882352941176471", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_270_04")
         .set("size", new String[]{"0.001", "0.009764705882352943", "0.0092"});
    model.component("comp1").geom("geom1").feature().create("outer_270_05", "Block");
    model.component("comp1").geom("geom1").feature("outer_270_05")
         .set("pos", new String[]{"-0.093", "-0.0051764705882352945", "0.003"});
    model.component("comp1").geom("geom1").feature("outer_270_05")
         .set("size", new String[]{"0.001", "0.010352941176470589", "0.0092"});
    model.component("comp1").geom("geom1").run();
    model.component("comp1").geom("geom1").run();

    model.component("comp1").selection().create("sel_fluid_all", "Box");
    model.component("comp1").selection("sel_fluid_all").geom("geom1", 3);
    model.component("comp1").selection("sel_fluid_all").set("xmin", "-106[mm]");
    model.component("comp1").selection("sel_fluid_all").set("xmax", "106[mm]");
    model.component("comp1").selection("sel_fluid_all").set("ymin", "-106[mm]");
    model.component("comp1").selection("sel_fluid_all").set("ymax", "106[mm]");
    model.component("comp1").selection("sel_fluid_all").set("zmin", "2.9[mm]");
    model.component("comp1").selection("sel_fluid_all").set("zmax", "12.3[mm]");
    model.component("comp1").selection("sel_fluid_all").set("condition", "inside");
    model.component("comp1").selection().create("sel_chamber", "Box");
    model.component("comp1").selection("sel_chamber").geom("geom1", 3);
    model.component("comp1").selection("sel_chamber").set("xmin", "-18.01[mm]");
    model.component("comp1").selection("sel_chamber").set("xmax", "18.01[mm]");
    model.component("comp1").selection("sel_chamber").set("ymin", "-18.01[mm]");
    model.component("comp1").selection("sel_chamber").set("ymax", "18.01[mm]");
    model.component("comp1").selection("sel_chamber").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_chamber").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_chamber").set("condition", "inside");
    model.component("comp1").selection().create("sel_mic_nominal", "Box");
    model.component("comp1").selection("sel_mic_nominal").geom("geom1", 2);
    model.component("comp1").selection("sel_mic_nominal").set("xmin", "-4.401[mm]");
    model.component("comp1").selection("sel_mic_nominal").set("xmax", "4.401[mm]");
    model.component("comp1").selection("sel_mic_nominal").set("ymin", "-4.401[mm]");
    model.component("comp1").selection("sel_mic_nominal").set("ymax", "4.401[mm]");
    model.component("comp1").selection("sel_mic_nominal").set("zmin", "6.999[mm]");
    model.component("comp1").selection("sel_mic_nominal").set("zmax", "7.001[mm]");
    model.component("comp1").selection("sel_mic_nominal").set("condition", "inside");
    model.component("comp1").selection().create("bnd_wall_all", "Box");
    model.component("comp1").selection("bnd_wall_all").geom("geom1", 2);
    model.component("comp1").selection("bnd_wall_all").set("xmin", "-106[mm]");
    model.component("comp1").selection("bnd_wall_all").set("xmax", "106[mm]");
    model.component("comp1").selection("bnd_wall_all").set("ymin", "-106[mm]");
    model.component("comp1").selection("bnd_wall_all").set("ymax", "106[mm]");
    model.component("comp1").selection("bnd_wall_all").set("zmin", "2.9[mm]");
    model.component("comp1").selection("bnd_wall_all").set("zmax", "12.3[mm]");
    model.component("comp1").selection("bnd_wall_all").set("condition", "inside");
    model.component("comp1").selection().create("bnd_port_000", "Box");
    model.component("comp1").selection("bnd_port_000").geom("geom1", 2);
    model.component("comp1").selection("bnd_port_000").set("xmin", "-8.01[mm]");
    model.component("comp1").selection("bnd_port_000").set("xmax", "8.01[mm]");
    model.component("comp1").selection("bnd_port_000").set("ymin", "104.999[mm]");
    model.component("comp1").selection("bnd_port_000").set("ymax", "105.001[mm]");
    model.component("comp1").selection("bnd_port_000").set("zmin", "2.99[mm]");
    model.component("comp1").selection("bnd_port_000").set("zmax", "12.21[mm]");
    model.component("comp1").selection("bnd_port_000").set("condition", "inside");
    model.component("comp1").selection().create("bnd_p10_090", "Box");
    model.component("comp1").selection("bnd_p10_090").geom("geom1", 2);
    model.component("comp1").selection("bnd_p10_090").set("xmin", "92.999[mm]");
    model.component("comp1").selection("bnd_p10_090").set("xmax", "93.001[mm]");
    model.component("comp1").selection("bnd_p10_090").set("ymin", "-5.18[mm]");
    model.component("comp1").selection("bnd_p10_090").set("ymax", "5.18[mm]");
    model.component("comp1").selection("bnd_p10_090").set("zmin", "2.99[mm]");
    model.component("comp1").selection("bnd_p10_090").set("zmax", "12.21[mm]");
    model.component("comp1").selection("bnd_p10_090").set("condition", "inside");
    model.component("comp1").selection().create("bnd_p10_180", "Box");
    model.component("comp1").selection("bnd_p10_180").geom("geom1", 2);
    model.component("comp1").selection("bnd_p10_180").set("xmin", "-5.18[mm]");
    model.component("comp1").selection("bnd_p10_180").set("xmax", "5.18[mm]");
    model.component("comp1").selection("bnd_p10_180").set("ymin", "-93.001[mm]");
    model.component("comp1").selection("bnd_p10_180").set("ymax", "-92.999[mm]");
    model.component("comp1").selection("bnd_p10_180").set("zmin", "2.99[mm]");
    model.component("comp1").selection("bnd_p10_180").set("zmax", "12.21[mm]");
    model.component("comp1").selection("bnd_p10_180").set("condition", "inside");
    model.component("comp1").selection().create("bnd_p10_270", "Box");
    model.component("comp1").selection("bnd_p10_270").geom("geom1", 2);
    model.component("comp1").selection("bnd_p10_270").set("xmin", "-93.001[mm]");
    model.component("comp1").selection("bnd_p10_270").set("xmax", "-92.999[mm]");
    model.component("comp1").selection("bnd_p10_270").set("ymin", "-5.18[mm]");
    model.component("comp1").selection("bnd_p10_270").set("ymax", "5.18[mm]");
    model.component("comp1").selection("bnd_p10_270").set("zmin", "2.99[mm]");
    model.component("comp1").selection("bnd_p10_270").set("zmax", "12.21[mm]");
    model.component("comp1").selection("bnd_p10_270").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_inner_000", "Box");
    model.component("comp1").selection("sel_fixed_inner_000").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_inner_000").set("xmin", "-4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_000").set("xmax", "4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_000").set("ymin", "16.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_000").set("ymax", "32.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_000").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_000").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_inner_000").set("condition", "inside");
    model.component("comp1").selection().create("sel_module_000", "Box");
    model.component("comp1").selection("sel_module_000").geom("geom1", 3);
    model.component("comp1").selection("sel_module_000").set("xmin", "-4.71[mm]");
    model.component("comp1").selection("sel_module_000").set("xmax", "4.71[mm]");
    model.component("comp1").selection("sel_module_000").set("ymin", "31.99[mm]");
    model.component("comp1").selection("sel_module_000").set("ymax", "88.01[mm]");
    model.component("comp1").selection("sel_module_000").set("zmin", "4.19[mm]");
    model.component("comp1").selection("sel_module_000").set("zmax", "10.61[mm]");
    model.component("comp1").selection("sel_module_000").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_outer_000", "Box");
    model.component("comp1").selection("sel_fixed_outer_000").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_outer_000").set("xmin", "-8.01[mm]");
    model.component("comp1").selection("sel_fixed_outer_000").set("xmax", "8.01[mm]");
    model.component("comp1").selection("sel_fixed_outer_000").set("ymin", "87.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_000").set("ymax", "105.01[mm]");
    model.component("comp1").selection("sel_fixed_outer_000").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_000").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_outer_000").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_inner_090", "Box");
    model.component("comp1").selection("sel_fixed_inner_090").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_inner_090").set("xmin", "16.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_090").set("xmax", "32.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_090").set("ymin", "-4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_090").set("ymax", "4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_090").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_090").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_inner_090").set("condition", "inside");
    model.component("comp1").selection().create("sel_module_090", "Box");
    model.component("comp1").selection("sel_module_090").geom("geom1", 3);
    model.component("comp1").selection("sel_module_090").set("xmin", "31.99[mm]");
    model.component("comp1").selection("sel_module_090").set("xmax", "88.01[mm]");
    model.component("comp1").selection("sel_module_090").set("ymin", "-4.71[mm]");
    model.component("comp1").selection("sel_module_090").set("ymax", "4.71[mm]");
    model.component("comp1").selection("sel_module_090").set("zmin", "4.19[mm]");
    model.component("comp1").selection("sel_module_090").set("zmax", "10.61[mm]");
    model.component("comp1").selection("sel_module_090").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_outer_090", "Box");
    model.component("comp1").selection("sel_fixed_outer_090").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_outer_090").set("xmin", "87.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_090").set("xmax", "93.01[mm]");
    model.component("comp1").selection("sel_fixed_outer_090").set("ymin", "-5.19[mm]");
    model.component("comp1").selection("sel_fixed_outer_090").set("ymax", "5.19[mm]");
    model.component("comp1").selection("sel_fixed_outer_090").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_090").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_outer_090").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_inner_180", "Box");
    model.component("comp1").selection("sel_fixed_inner_180").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_inner_180").set("xmin", "-4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_180").set("xmax", "4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_180").set("ymin", "-32.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_180").set("ymax", "-16.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_180").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_180").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_inner_180").set("condition", "inside");
    model.component("comp1").selection().create("sel_module_180", "Box");
    model.component("comp1").selection("sel_module_180").geom("geom1", 3);
    model.component("comp1").selection("sel_module_180").set("xmin", "-4.71[mm]");
    model.component("comp1").selection("sel_module_180").set("xmax", "4.71[mm]");
    model.component("comp1").selection("sel_module_180").set("ymin", "-88.01[mm]");
    model.component("comp1").selection("sel_module_180").set("ymax", "-31.99[mm]");
    model.component("comp1").selection("sel_module_180").set("zmin", "4.19[mm]");
    model.component("comp1").selection("sel_module_180").set("zmax", "10.61[mm]");
    model.component("comp1").selection("sel_module_180").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_outer_180", "Box");
    model.component("comp1").selection("sel_fixed_outer_180").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_outer_180").set("xmin", "-5.19[mm]");
    model.component("comp1").selection("sel_fixed_outer_180").set("xmax", "5.19[mm]");
    model.component("comp1").selection("sel_fixed_outer_180").set("ymin", "-93.01[mm]");
    model.component("comp1").selection("sel_fixed_outer_180").set("ymax", "-87.99[mm]");

    return model;
  }

  public static Model run2(Model model) {
    model.component("comp1").selection("sel_fixed_outer_180").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_180").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_outer_180").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_inner_270", "Box");
    model.component("comp1").selection("sel_fixed_inner_270").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_inner_270").set("xmin", "-32.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_270").set("xmax", "-16.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_270").set("ymin", "-4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_270").set("ymax", "4.01[mm]");
    model.component("comp1").selection("sel_fixed_inner_270").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_inner_270").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_inner_270").set("condition", "inside");
    model.component("comp1").selection().create("sel_module_270", "Box");
    model.component("comp1").selection("sel_module_270").geom("geom1", 3);
    model.component("comp1").selection("sel_module_270").set("xmin", "-88.01[mm]");
    model.component("comp1").selection("sel_module_270").set("xmax", "-31.99[mm]");
    model.component("comp1").selection("sel_module_270").set("ymin", "-4.71[mm]");
    model.component("comp1").selection("sel_module_270").set("ymax", "4.71[mm]");
    model.component("comp1").selection("sel_module_270").set("zmin", "4.19[mm]");
    model.component("comp1").selection("sel_module_270").set("zmax", "10.61[mm]");
    model.component("comp1").selection("sel_module_270").set("condition", "inside");
    model.component("comp1").selection().create("sel_fixed_outer_270", "Box");
    model.component("comp1").selection("sel_fixed_outer_270").geom("geom1", 3);
    model.component("comp1").selection("sel_fixed_outer_270").set("xmin", "-93.01[mm]");
    model.component("comp1").selection("sel_fixed_outer_270").set("xmax", "-87.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_270").set("ymin", "-5.19[mm]");
    model.component("comp1").selection("sel_fixed_outer_270").set("ymax", "5.19[mm]");
    model.component("comp1").selection("sel_fixed_outer_270").set("zmin", "2.99[mm]");
    model.component("comp1").selection("sel_fixed_outer_270").set("zmax", "12.21[mm]");
    model.component("comp1").selection("sel_fixed_outer_270").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_inner_000", "Box");
    model.component("comp1").selection("bnd_if_inner_000").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_inner_000").set("xmin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_000").set("xmax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_000").set("ymin", "31.999[mm]");
    model.component("comp1").selection("bnd_if_inner_000").set("ymax", "32.001[mm]");
    model.component("comp1").selection("bnd_if_inner_000").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_inner_000").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_inner_000").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_outer_000", "Box");
    model.component("comp1").selection("bnd_if_outer_000").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_outer_000").set("xmin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_000").set("xmax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_000").set("ymin", "87.999[mm]");
    model.component("comp1").selection("bnd_if_outer_000").set("ymax", "88.001[mm]");
    model.component("comp1").selection("bnd_if_outer_000").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_outer_000").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_outer_000").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_inner_090", "Box");
    model.component("comp1").selection("bnd_if_inner_090").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_inner_090").set("xmin", "31.999[mm]");
    model.component("comp1").selection("bnd_if_inner_090").set("xmax", "32.001[mm]");
    model.component("comp1").selection("bnd_if_inner_090").set("ymin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_090").set("ymax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_090").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_inner_090").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_inner_090").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_outer_090", "Box");
    model.component("comp1").selection("bnd_if_outer_090").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_outer_090").set("xmin", "87.999[mm]");
    model.component("comp1").selection("bnd_if_outer_090").set("xmax", "88.001[mm]");
    model.component("comp1").selection("bnd_if_outer_090").set("ymin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_090").set("ymax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_090").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_outer_090").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_outer_090").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_inner_180", "Box");
    model.component("comp1").selection("bnd_if_inner_180").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_inner_180").set("xmin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_180").set("xmax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_180").set("ymin", "-32.001[mm]");
    model.component("comp1").selection("bnd_if_inner_180").set("ymax", "-31.999[mm]");
    model.component("comp1").selection("bnd_if_inner_180").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_inner_180").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_inner_180").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_outer_180", "Box");
    model.component("comp1").selection("bnd_if_outer_180").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_outer_180").set("xmin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_180").set("xmax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_180").set("ymin", "-88.001[mm]");
    model.component("comp1").selection("bnd_if_outer_180").set("ymax", "-87.999[mm]");
    model.component("comp1").selection("bnd_if_outer_180").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_outer_180").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_outer_180").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_inner_270", "Box");
    model.component("comp1").selection("bnd_if_inner_270").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_inner_270").set("xmin", "-32.001[mm]");
    model.component("comp1").selection("bnd_if_inner_270").set("xmax", "-31.999[mm]");
    model.component("comp1").selection("bnd_if_inner_270").set("ymin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_270").set("ymax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_inner_270").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_inner_270").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_inner_270").set("condition", "inside");
    model.component("comp1").selection().create("bnd_if_outer_270", "Box");
    model.component("comp1").selection("bnd_if_outer_270").geom("geom1", 2);
    model.component("comp1").selection("bnd_if_outer_270").set("xmin", "-88.001[mm]");
    model.component("comp1").selection("bnd_if_outer_270").set("xmax", "-87.999[mm]");
    model.component("comp1").selection("bnd_if_outer_270").set("ymin", "-4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_270").set("ymax", "4.71[mm]");
    model.component("comp1").selection("bnd_if_outer_270").set("zmin", "4.199[mm]");
    model.component("comp1").selection("bnd_if_outer_270").set("zmax", "10.601[mm]");
    model.component("comp1").selection("bnd_if_outer_270").set("condition", "inside");

    model.component("comp1").physics().create("acpr", "PressureAcoustics", "geom1");
    model.component("comp1").physics("acpr").selection()
         .set(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52);
    model.component("comp1").physics("acpr").create("pressure_1", "Pressure", 2);
    model.component("comp1").physics("acpr").feature("pressure_1").selection().named("bnd_port_000");
    model.component("comp1").physics("acpr").feature("pressure_1").set("p0", "p_inc");
    model.component("comp1").physics("acpr").feature("pressure_1").label("Pressure (Selection bnd_port_000)");
    model.component("comp1").physics("acpr").create("soundhard_1", "SoundHard", 2);
    model.component("comp1").physics("acpr").feature("soundhard_1").selection().named("bnd_p10_090");
    model.component("comp1").physics("acpr").feature("soundhard_1").label("SoundHard (Selection bnd_p10_090)");
    model.component("comp1").physics("acpr").create("soundhard_2", "SoundHard", 2);
    model.component("comp1").physics("acpr").feature("soundhard_2").selection().named("bnd_p10_180");
    model.component("comp1").physics("acpr").feature("soundhard_2").label("SoundHard (Selection bnd_p10_180)");
    model.component("comp1").physics("acpr").create("soundhard_3", "SoundHard", 2);
    model.component("comp1").physics("acpr").feature("soundhard_3").selection().named("bnd_p10_270");
    model.component("comp1").physics("acpr").feature("soundhard_3").label("SoundHard (Selection bnd_p10_270)");

    model.component("comp1").cpl().create("aveop_mic", "Average");
    model.component("comp1").cpl("aveop_mic").selection().named("sel_mic_nominal");

    model.component("comp1").physics("acpr").feature("fpam1").set("c_mat", "userdef");
    model.component("comp1").physics("acpr").feature("fpam1").set("c", "c0_nom");
    model.component("comp1").physics("acpr").feature("fpam1").set("rho_mat", "userdef");
    model.component("comp1").physics("acpr").feature("fpam1").set("rho", "rho0_nom");

    model.component("comp1").mesh().create("mesh1", "geom1");

    model.component("comp1").physics("acpr").prop("MeshControl").set("SizeControlParameter", "Frequency");
    model.component("comp1").physics("acpr").prop("MeshControl")
         .set("PhysicsControlledMeshMaximumFrequency", "24000[Hz]");

    model.component("comp1").mesh("mesh1").automatic(true);
    model.component("comp1").mesh("mesh1").autoMeshSize(6);
    model.component("comp1").mesh("mesh1").run();

    model.component("comp1").physics("acpr").prop("MeshControl").set("SizeControlParameter", "Frequency");
    model.component("comp1").physics("acpr").prop("MeshControl")
         .set("PhysicsControlledMeshMaximumFrequency", "36000[Hz]");

    model.component("comp1").mesh("mesh1").automatic(true);
    model.component("comp1").mesh("mesh1").autoMeshSize(5);
    model.component("comp1").mesh("mesh1").run();

    model.component("comp1").geom("geom1").run();

    model.component("comp1").cpl().create("aveop_mic_rebuildcheck", "Average");
    model.component("comp1").cpl("aveop_mic_rebuildcheck").selection().named("sel_mic_nominal");
    model.component("comp1").cpl().create("aveop_port_rebuildcheck", "Average");
    model.component("comp1").cpl("aveop_port_rebuildcheck").selection().named("bnd_port_000");
    model.component("comp1").cpl().create("aveop_fluid_rebuildcheck", "Average");
    model.component("comp1").cpl("aveop_fluid_rebuildcheck").selection().named("sel_fluid_all");

    model.component("comp1").mesh("mesh1").run();

    model.study().create("std_freq");
    model.study("std_freq").feature().create("step1", "Frequency");
    model.study("std_freq").feature("step1").set("plist", "500 1000 2000 4000 7000");
    model.study("std_freq").run();

    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "aveop_mic(acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "at3(0,0,z_mic,acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "aveop_port_rebuildcheck(acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().create("pg_geometry_inspection", "PlotGroup3D");
    model.result().export().create("img_geometry_inspection", "pg_geometry_inspection", "Image");
    model.result().export("img_geometry_inspection").set("target", "file");
    model.result().export("img_geometry_inspection").set("imagetype", "png");
    model.result().export("img_geometry_inspection")
         .set("pngfilename", "D:\\Bristol course\\dissertation\\program work\\outputs\\simulation\\COMSOL_SCHEME_3A\\P02_P05_BASELINE\\geometry_surface_inspection.png");
    model.result().export("img_geometry_inspection").run();
    model.result().create("pg_pressure_7000", "PlotGroup3D");
    model.result().export().create("img_pressure_7000", "pg_pressure_7000", "Image");
    model.result().export("img_pressure_7000").set("target", "file");
    model.result().export("img_pressure_7000").set("imagetype", "png");
    model.result().export("img_pressure_7000")
         .set("pngfilename", "D:\\Bristol course\\dissertation\\program work\\outputs\\simulation\\COMSOL_SCHEME_3A\\P02_P05_BASELINE\\pressure_field_7000hz.png");
    model.result().export("img_pressure_7000").run();
    model.result().create("pg_geometry_verified", "PlotGroup3D");
    model.result("pg_geometry_verified").feature().create("surf_geometry_verified", "Surface");
    model.result("pg_geometry_verified").feature("surf_geometry_verified").set("expr", "1");
    model.result("pg_geometry_verified").run();
    model.result().export().create("img_geometry_verified", "pg_geometry_verified", "Image");
    model.result().export("img_geometry_verified").set("target", "file");
    model.result().export("img_geometry_verified").set("imagetype", "png");
    model.result().export("img_geometry_verified")
         .set("pngfilename", "D:\\Bristol course\\dissertation\\program work\\outputs\\simulation\\COMSOL_SCHEME_3A\\P02_P05_BASELINE\\geometry_surface_inspection_verified.png");
    model.result().export("img_geometry_verified").run();
    model.result().create("pg_pressure_verified", "PlotGroup3D");
    model.result("pg_pressure_verified").feature().create("surf_pressure_verified", "Surface");
    model.result("pg_pressure_verified").feature("surf_pressure_verified").set("expr", "abs(acpr.p_t)");
    model.result("pg_pressure_verified").run();
    model.result().export().create("img_pressure_verified", "pg_pressure_verified", "Image");
    model.result().export("img_pressure_verified").set("target", "file");
    model.result().export("img_pressure_verified").set("imagetype", "png");
    model.result().export("img_pressure_verified")
         .set("pngfilename", "D:\\Bristol course\\dissertation\\program work\\outputs\\simulation\\COMSOL_SCHEME_3A\\P02_P05_BASELINE\\pressure_field_7000hz_verified.png");
    model.result().export("img_pressure_verified").run();

    model.label("COMSOL_3A_P02_P05_BASELINE.mph");

    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "aveop_mic(acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "at3(0,0,z_mic,acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "aveop_port_rebuildcheck(acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");

    model.component("comp1").physics("acpr").prop("MeshControl").set("SizeControlParameter", "Frequency");
    model.component("comp1").physics("acpr").prop("MeshControl")
         .set("PhysicsControlledMeshMaximumFrequency", "25000[Hz]");

    model.component("comp1").mesh("mesh1").automatic(true);
    model.component("comp1").mesh("mesh1").autoMeshSize(6);
    model.component("comp1").mesh("mesh1").run();

    model.component("comp1").physics("acpr").prop("MeshControl").set("SizeControlParameter", "Frequency");
    model.component("comp1").physics("acpr").prop("MeshControl")
         .set("PhysicsControlledMeshMaximumFrequency", "37500[Hz]");

    model.component("comp1").mesh("mesh1").automatic(true);
    model.component("comp1").mesh("mesh1").autoMeshSize(5);
    model.component("comp1").mesh("mesh1").run();

    model.study("std_freq").run();

    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "aveop_mic(acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "at3(0,0,z_mic,acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "aveop_port_rebuildcheck(acpr.p_t)");
    model.result().numerical("gev1").set("unit", "Pa");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");
    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set("expr", "real(freq)");
    model.result().numerical("gev1").set("unit", "Hz");
    model.result().numerical("gev1").set("data", "dset1");
    model.result().numerical("gev1").computeResult();
    model.result().numerical().remove("gev1");

    model.label("COMSOL_3A_P02_P05_BASELINE.mph");

    return model;
  }

  public static void main(String[] args) {
    Model model = run();
    run2(model);
  }

}
