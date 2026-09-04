import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

/** Read-only inventory of an already-solved full-wave model. */
public class InspectExistingFullWave {
  private static final String MODEL =
      "D:/Bristol course/dissertation/program work/outputs/gen_enc/"
      + "GEN_ENC_26_PRINT_CONV_B/FC_L0900_A05_size2.mph";

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    Model model = ModelUtil.load("publication_view_inventory", MODEL);
    System.out.println("MODEL=" + MODEL);
    System.out.println("RESULT_TAGS=" + Arrays.toString(model.result().tags()));
    System.out.println("DATASET_TAGS=" + Arrays.toString(model.result().dataset().tags()));
    System.out.println("EXPORT_TAGS=" + Arrays.toString(model.result().export().tags()));
    System.out.println("SOLUTION_TAGS=" + Arrays.toString(model.sol().tags()));
    for (String tag : model.result().tags()) {
      try {
        System.out.println("RESULT " + tag + " label=" + model.result(tag).label()
            + " features=" + Arrays.toString(model.result(tag).feature().tags()));
      } catch (Exception ex) {
        System.out.println("RESULT " + tag + " inspection_failed=" + ex.getMessage());
      }
    }
    for (String tag : model.result().dataset().tags()) {
      try {
        System.out.println("DATASET " + tag + " label=" + model.result().dataset(tag).label());
      } catch (Exception ex) {
        System.out.println("DATASET " + tag + " inspection_failed=" + ex.getMessage());
      }
    }
    for (String tag : model.sol().tags()) {
      try {
        double[] pvals = model.sol(tag).getPVals();
        System.out.println("SOLUTION " + tag + " pvals=" + pvals.length
            + " first=" + (pvals.length > 0 ? pvals[0] : Double.NaN)
            + " last=" + (pvals.length > 0 ? pvals[pvals.length - 1] : Double.NaN));
      } catch (Exception ex) {
        System.out.println("SOLUTION " + tag + " pvals_failed=" + ex.getMessage());
      }
    }
    ModelUtil.remove("publication_view_inventory");
  }
}
