import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/** Read-only inspection of the saved field state used for the manuscript. */
public class InspectStoredFieldState {
  private static final String MODEL =
      "D:/Bristol course/dissertation/program work/outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B/FC_L0900_A05_size2.mph";

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    Model model = ModelUtil.load("stored_field_audit", MODEL);
    System.out.println("SOURCE_MODEL=" + MODEL);
    System.out.println("SRC_STATE=" + model.param().get("src_state"));
    System.out.println("SOLUTION_COUNT=" + model.sol("sol1").getPVals().length);
    double[] pvals = model.sol("sol1").getPVals();
    boolean has954 = false;
    for (double p : pvals) if (Math.abs(p - 954.0) < 1e-9) has954 = true;
    System.out.println("HAS_954_HZ=" + has954);

    ModelNode comp = model.component("comp1");
    for (String tag : new String[]{"nv0", "nv90", "nv180", "nv270"}) {
      System.out.println("FEATURE=" + tag + " TYPE="
          + comp.physics("acpr").feature(tag).getType()
          + " LABEL=" + comp.physics("acpr").feature(tag).label());
      for (String key : comp.physics("acpr").feature(tag).properties()) {
        try {
          String value = comp.physics("acpr").feature(tag).getString(key);
          if (value != null && !value.isEmpty())
            System.out.println("  PROPERTY " + key + "=" + value);
        } catch (Exception ignored) {
          try {
            String[] values = comp.physics("acpr").feature(tag).getStringArray(key);
            if (values != null && values.length > 0)
              System.out.println("  PROPERTY " + key + "=" + Arrays.toString(values));
          } catch (Exception ignoredAgain) {}
        }
      }
    }
    System.out.println("NO_MESH_SOLVE_OR_SAVE_CALLED=true");
    ModelUtil.remove("stored_field_audit");
  }
}
