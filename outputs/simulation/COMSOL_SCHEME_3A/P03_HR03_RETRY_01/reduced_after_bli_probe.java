/*
 * reduced_after_bli_probe.java
 */

import com.comsol.model.*;
import com.comsol.model.util.*;

/** Model exported on Aug 25 2026, 11:25 by COMSOL 6.4.0.293. */
public class reduced_after_bli_probe {

  public static Model run() {
    Model model = ModelUtil.create("Model");

    model
         .modelPath("D:\\Bristol course\\dissertation\\program work\\outputs\\simulation\\COMSOL_SCHEME_3A\\P03_HR03_RETRY_01");

    model.label("P03_HR03_RETRY01_REDUCED");
    model.label("P03_HR03_RETRY01_REDUCED");

    model.component().create("comp1", true);

    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").geom("geom1").feature().create("hr03_neck_inner", "Block");
    model.component("comp1").geom("geom1").feature("hr03_neck_inner")
         .set("pos", new String[]{"-0.0286", "-0.0014", "0.0"});
    model.component("comp1").geom("geom1").feature("hr03_neck_inner")
         .set("size", new String[]{"0.0236", "0.0028", "0.0064"});
    model.component("comp1").geom("geom1").feature("hr03_neck_inner").set("selresult", true);
    model.component("comp1").geom("geom1").feature().create("hr03_cavity", "Block");
    model.component("comp1").geom("geom1").feature("hr03_cavity")
         .set("pos", new String[]{"-0.005", "-0.0075", "0.0"});
    model.component("comp1").geom("geom1").feature("hr03_cavity")
         .set("size", new String[]{"0.026", "0.015", "0.0064"});
    model.component("comp1").geom("geom1").feature("hr03_cavity").set("selresult", true);
    model.component("comp1").geom("geom1").feature().create("hr03_neck_outer", "Block");
    model.component("comp1").geom("geom1").feature("hr03_neck_outer")
         .set("pos", new String[]{"0.021", "-0.0022", "0.0"});
    model.component("comp1").geom("geom1").feature("hr03_neck_outer")
         .set("size", new String[]{"0.0076", "0.0044", "0.0064"});
    model.component("comp1").geom("geom1").feature("hr03_neck_outer").set("selresult", true);
    model.component("comp1").geom("geom1").run();

    model.component("comp1").selection().create("sel_fluid_all", "Box");
    model.component("comp1").selection("sel_fluid_all").geom("geom1", 3);
    model.component("comp1").selection("sel_fluid_all").set("xmin", "-0.0286001[m]");
    model.component("comp1").selection("sel_fluid_all").set("xmax", "0.0286001[m]");
    model.component("comp1").selection("sel_fluid_all").set("ymin", "-0.0075001[m]");
    model.component("comp1").selection("sel_fluid_all").set("ymax", "0.0075001[m]");
    model.component("comp1").selection("sel_fluid_all").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("sel_fluid_all").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("sel_fluid_all").set("condition", "inside");
    model.component("comp1").selection().create("sel_hr03_neck_inner", "Box");
    model.component("comp1").selection("sel_hr03_neck_inner").geom("geom1", 3);
    model.component("comp1").selection("sel_hr03_neck_inner").set("xmin", "-0.0286001[m]");
    model.component("comp1").selection("sel_hr03_neck_inner").set("xmax", "-0.0049999[m]");
    model.component("comp1").selection("sel_hr03_neck_inner").set("ymin", "-0.0014001[m]");
    model.component("comp1").selection("sel_hr03_neck_inner").set("ymax", "0.0014001[m]");
    model.component("comp1").selection("sel_hr03_neck_inner").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("sel_hr03_neck_inner").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("sel_hr03_neck_inner").set("condition", "inside");
    model.component("comp1").selection().create("sel_hr03_cavity", "Box");
    model.component("comp1").selection("sel_hr03_cavity").geom("geom1", 3);
    model.component("comp1").selection("sel_hr03_cavity").set("xmin", "-0.0050001[m]");
    model.component("comp1").selection("sel_hr03_cavity").set("xmax", "0.0210001[m]");
    model.component("comp1").selection("sel_hr03_cavity").set("ymin", "-0.0075001[m]");
    model.component("comp1").selection("sel_hr03_cavity").set("ymax", "0.0075001[m]");
    model.component("comp1").selection("sel_hr03_cavity").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("sel_hr03_cavity").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("sel_hr03_cavity").set("condition", "inside");
    model.component("comp1").selection().create("sel_hr03_neck_outer", "Box");
    model.component("comp1").selection("sel_hr03_neck_outer").geom("geom1", 3);
    model.component("comp1").selection("sel_hr03_neck_outer").set("xmin", "0.0209999[m]");
    model.component("comp1").selection("sel_hr03_neck_outer").set("xmax", "0.0286001[m]");
    model.component("comp1").selection("sel_hr03_neck_outer").set("ymin", "-0.0022001[m]");
    model.component("comp1").selection("sel_hr03_neck_outer").set("ymax", "0.0022001[m]");
    model.component("comp1").selection("sel_hr03_neck_outer").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("sel_hr03_neck_outer").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("sel_hr03_neck_outer").set("condition", "inside");
    model.component("comp1").selection().create("bnd_inlet_inner", "Box");
    model.component("comp1").selection("bnd_inlet_inner").geom("geom1", 2);
    model.component("comp1").selection("bnd_inlet_inner").set("xmin", "-0.0286001[m]");
    model.component("comp1").selection("bnd_inlet_inner").set("xmax", "-0.0285999[m]");
    model.component("comp1").selection("bnd_inlet_inner").set("ymin", "-0.0014001[m]");
    model.component("comp1").selection("bnd_inlet_inner").set("ymax", "0.0014001[m]");
    model.component("comp1").selection("bnd_inlet_inner").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("bnd_inlet_inner").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("bnd_inlet_inner").set("condition", "inside");
    model.component("comp1").selection().create("bnd_source_outer", "Box");
    model.component("comp1").selection("bnd_source_outer").geom("geom1", 2);
    model.component("comp1").selection("bnd_source_outer").set("xmin", "0.0285999[m]");
    model.component("comp1").selection("bnd_source_outer").set("xmax", "0.0286001[m]");
    model.component("comp1").selection("bnd_source_outer").set("ymin", "-0.0022001[m]");
    model.component("comp1").selection("bnd_source_outer").set("ymax", "0.0022001[m]");
    model.component("comp1").selection("bnd_source_outer").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("bnd_source_outer").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("bnd_source_outer").set("condition", "inside");
    model.component("comp1").selection().create("bnd_all", "Box");
    model.component("comp1").selection("bnd_all").geom("geom1", 2);
    model.component("comp1").selection("bnd_all").set("xmin", "-0.0286001[m]");
    model.component("comp1").selection("bnd_all").set("xmax", "0.0286001[m]");
    model.component("comp1").selection("bnd_all").set("ymin", "-0.0075001[m]");
    model.component("comp1").selection("bnd_all").set("ymax", "0.0075001[m]");
    model.component("comp1").selection("bnd_all").set("zmin", "-1e-07[m]");
    model.component("comp1").selection("bnd_all").set("zmax", "0.0064001[m]");
    model.component("comp1").selection("bnd_all").set("condition", "inside");
    model.component("comp1").selection().create("bnd_ports", "Union");
    model.component("comp1").selection("bnd_ports").geom("geom1", 2);
    model.component("comp1").selection("bnd_ports")
         .set("input", new String[]{"bnd_inlet_inner", "bnd_source_outer"});
    model.component("comp1").selection().create("bnd_wall_all", "Difference");
    model.component("comp1").selection("bnd_wall_all").geom("geom1", 2);
    model.component("comp1").selection("bnd_wall_all").set("add", new String[]{"bnd_all"});
    model.component("comp1").selection("bnd_wall_all").set("subtract", new String[]{"bnd_ports"});

    model.component("comp1").cpl().create("aveop_cavity", "Average");
    model.component("comp1").cpl("aveop_cavity").selection().named("sel_hr03_cavity");

    model.param().set("rho0", "1.2041[kg/m^3]");
    model.param().set("c0", "343[m/s]");
    model.param().set("mu0", "1.814e-5[Pa*s]");
    model.param().set("mub0", "1.09e-5[Pa*s]");
    model.param().set("k0", "0.0257[W/(m*K)]");
    model.param().set("Cp0", "1005[J/(kg*K)]");
    model.param().set("gamma0", "1.4");
    model.param().set("T0", "293.15[K]");
    model.param().set("p0eq", "101325[Pa]");
    model.param().set("p_inc", "1[Pa]");

    model.label("hr03_reduced_seed.mph");

    model.component("comp1").physics().create("acpr", "PressureAcoustics", "geom1");
    model.component("comp1").physics("acpr").feature("fpam1").set("c_mat", "userdef");
    model.component("comp1").physics("acpr").feature("fpam1").set("c", "343[m/s]");
    model.component("comp1").physics("acpr").feature("fpam1").set("rho_mat", "userdef");
    model.component("comp1").physics("acpr").feature("fpam1").set("rho", "1.2041[kg/m^3]");
    model.component("comp1").physics("acpr")
         .create("thermoviscousboundarylayerimpedance_1", "ThermoviscousBoundaryLayerImpedance", 2);
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1").selection()
         .named("bnd_wall_all");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("c_mat", "userdef");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1").set("c", "343[m/s]");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("mu_mat", "userdef");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("mu", "1.814e-5[Pa*s]");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("kcond_mat", "userdef");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("kcond", "0.0257[W/(m*K)]");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("Cp_mat", "userdef");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("Cp", "1005[J/(kg*K)]");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .set("gamma_mat", "userdef");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1").set("gamma", "1.4");
    model.component("comp1").physics("acpr").feature("thermoviscousboundarylayerimpedance_1")
         .label("ThermoviscousBoundaryLayerImpedance (Selection bnd_wall_all)");

    return model;
  }

  public static void main(String[] args) {
    run();
  }

}
