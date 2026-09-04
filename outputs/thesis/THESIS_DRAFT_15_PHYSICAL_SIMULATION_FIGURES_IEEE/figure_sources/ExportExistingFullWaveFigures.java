import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/**
 * Export publication views from an already-solved alpha=0.05 full-wave model.
 * This utility loads and plots the stored solution only; it does not mesh,
 * solve, alter, or save the source MPH file.
 */
public class ExportExistingFullWaveFigures {
  private static final String ROOT = "D:/Bristol course/dissertation/program work/";
  private static final String MODEL = ROOT
      + "outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B/FC_L0900_A05_size2.mph";
  private static final String OUT = ROOT + "tmp/thesis_draft_15/comsol_exports/";

  private static void configureImage(Model model, String tag, String plotGroup,
                                     String filename, boolean showLegend) {
    model.result().export().create(tag, plotGroup, "Image");
    model.result().export(tag).set("target", "file");
    model.result().export(tag).set("imagetype", "png");
    model.result().export(tag).set("pngfilename", OUT + filename);
    model.result().export(tag).set("width", "2400");
    model.result().export(tag).set("height", "1600");
    model.result().export(tag).set("antialias", "on");
    model.result().export(tag).set("lockratio", "off");
    model.result().export(tag).set("zoomextents", "on");
    model.result().export(tag).set("options3d", "on");
    model.result().export(tag).set("legend3d", showLegend ? "on" : "off");
    model.result().export(tag).set("title3d", "off");
    model.result().export(tag).set("logo3d", "off");
    model.result().export(tag).set("axisorientation", "off");
    model.result().export(tag).set("grid", "off");
    model.result().export(tag).set("fontsize", "9");
    model.result().export(tag).set("background", "color");
    model.result().export(tag).set("customcolor", new double[]{1, 1, 1});
  }

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    Model model = ModelUtil.load("publication_views", MODEL);
    double[] frequencies = model.sol("sol1").getPVals();
    boolean has954 = false;
    for (double frequency : frequencies) {
      if (Math.abs(frequency - 954.0) < 1e-9) {
        has954 = true;
        break;
      }
    }
    if (!has954) {
      throw new IllegalStateException("Stored solution does not contain 954 Hz");
    }

    model.result().create("pg_pub_geometry", "PlotGroup3D");
    model.result("pg_pub_geometry").set("data", "dset1");
    // Frequencies are stored as 820:2:1080 Hz; 954 Hz is solution index 68.
    model.result("pg_pub_geometry").set("looplevel", new String[]{"68"});
    model.result("pg_pub_geometry").feature().create("surf", "Surface");
    model.result("pg_pub_geometry").feature("surf").set("expr", "1");
    model.result("pg_pub_geometry").feature("surf").set("coloring", "uniform");
    model.result("pg_pub_geometry").feature("surf").set("color", "custom");
    model.result("pg_pub_geometry").feature("surf").set(
        "customcolor", new double[]{0.68, 0.80, 0.90});
    model.result("pg_pub_geometry").feature("surf").set("wireframe", "on");
    model.result("pg_pub_geometry").run();
    configureImage(model, "img_pub_geometry", "pg_pub_geometry",
        "stored_fullwave_geometry.png", false);
    model.result().export("img_pub_geometry").run();

    model.result().create("pg_pub_pressure", "PlotGroup3D");
    model.result("pg_pub_pressure").set("data", "dset1");
    model.result("pg_pub_pressure").set("looplevel", new String[]{"68"});
    model.result("pg_pub_pressure").feature().create("surf", "Surface");
    model.result("pg_pub_pressure").feature("surf").set("expr", "abs(acpr.p_t)");
    model.result("pg_pub_pressure").feature("surf").set("unit", "Pa");
    model.result("pg_pub_pressure").feature("surf").set("descr", "Pressure magnitude");
    model.result("pg_pub_pressure").feature("surf").set("coloring", "colortable");
    model.result("pg_pub_pressure").feature("surf").set("colortable", "Thermal");
    model.result("pg_pub_pressure").feature("surf").set("colorscalemode", "linear");
    // A fixed non-negative display range avoids the symmetric complex-field
    // default and is used for visualisation only, not for a numerical claim.
    double displayMaximumPa = 2000.0;
    model.result("pg_pub_pressure").feature("surf").set("rangecoloractive", "on");
    model.result("pg_pub_pressure").feature("surf").set("rangecolormin", 0.0);
    model.result("pg_pub_pressure").feature("surf").set("rangecolormax", displayMaximumPa);
    model.result("pg_pub_pressure").feature("surf").set("colorlegend", "on");
    model.result("pg_pub_pressure").set("showlegendstitle", "on");
    model.result("pg_pub_pressure").set("showlegendsunit", "on");
    model.result("pg_pub_pressure").run();
    configureImage(model, "img_pub_pressure", "pg_pub_pressure",
        "stored_pressure_field_954hz.png", true);
    model.result().export("img_pub_pressure").run();

    System.out.println("SOURCE_MODEL=" + MODEL);
    System.out.println("STORED_FREQUENCY_HZ=954");
    System.out.println("DISPLAY_RANGE_PA=0.." + displayMaximumPa);
    System.out.println("NO_MESH_OR_SOLVE_CALLED=true");
    ModelUtil.remove("publication_views");
  }
}
