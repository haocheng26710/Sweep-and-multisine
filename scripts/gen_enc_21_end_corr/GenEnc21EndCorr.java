import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc21EndCorr {
  static final String BASE="D:/Bristol course/dissertation/program work/outputs/gen_enc/GEN_ENC_13_C2_ACOUSTIC_PREFLIGHT/C0_NEAR_01_lossy2d_size3.mph";
  static final String OUT="D:/Bristol course/dissertation/program work/scripts/gen_enc_21_end_corr/run_output/";
  static final double THICKNESS=0.023, AREA=8e-6, EFFECTIVE_LENGTH=0.012, CAVITY_WIDTH=0.010;
  static final double PLENUM_HALF=0.0362053299278368/2.0, X_CENTER=0.012;

  static double cavityVolume(double targetHz) {
    return AREA*343.0*343.0/(EFFECTIVE_LENGTH*Math.pow(2*Math.PI*targetHz,2));
  }

  static void addResonator(Model model,double targetHz,double physicalLength) {
    GeomSequence geom=model.component("comp1").geom("geom1");
    double width=AREA/THICKNESS, area2d=cavityVolume(targetHz)/THICKNESS;
    geom.feature().create("hr_neck","Rectangle");
    geom.feature("hr_neck").set("size",new double[]{width,physicalLength});
    geom.feature("hr_neck").set("pos",new double[]{X_CENTER-width/2,PLENUM_HALF});
    geom.feature().create("hr_cavity","Rectangle");
    geom.feature("hr_cavity").set("size",new double[]{CAVITY_WIDTH,area2d/CAVITY_WIDTH});
    geom.feature("hr_cavity").set("pos",new double[]{X_CENTER-CAVITY_WIDTH/2,PLENUM_HALF+physicalLength});
    geom.feature().create("comp_void","Rectangle");
    geom.feature("comp_void").set("size",new double[]{0.010,area2d/0.010});
    geom.feature("comp_void").set("pos",new double[]{0.004,-PLENUM_HALF});
    geom.feature().create("plenum_comp","Difference");
    geom.feature("plenum_comp").selection("input").set(new String[]{"plenum"});
    geom.feature("plenum_comp").selection("input2").set(new String[]{"comp_void"});
    geom.run();
  }

  static void runCase(String label,double targetHz,double physicalLength,int meshSize) throws Exception {
    String tag="m_"+label;
    Model model=ModelUtil.load(tag,BASE);
    addResonator(model,targetHz,physicalLength);
    ModelNode comp=model.component("comp1");
    int[] counts=new int[]{comp.selection("port0_face").entities(1).length,comp.selection("port90_face").entities(1).length,comp.selection("port180_face").entities(1).length,comp.selection("port270_face").entities(1).length};
    for(int count:counts) if(count!=1) throw new RuntimeException("PORT_IDENTITY_FAILURE_"+label);
    System.out.printf(Locale.US,"AUDIT %s %.1f %.5f %d %s %.12g%n",label,targetHz,physicalLength*1000,meshSize,Arrays.toString(counts),cavityVolume(targetHz)*1e6);
    comp.mesh("mesh1").feature("size").set("hauto",Integer.toString(meshSize));
    comp.mesh("mesh1").run();
    model.study("std1").feature("step1").set("plist","range(650,2,1250)");
    model.result().dataset().create("cpt","CutPoint2D");
    model.result().dataset("cpt").set("pointx",0.0);
    model.result().dataset("cpt").set("pointy",0.0);
    model.result().export().create("micdata","Data");
    model.result().export("micdata").set("data","cpt");
    model.result().export("micdata").set("expr",new String[]{"p"});
    for(int source=0;source<4;source++) {
      model.param().set("src_state",Integer.toString(source));
      model.study("std1").run();
      model.result().export("micdata").set("filename",OUT+label+"_size"+meshSize+"_src"+source+".txt");
      model.result().export("micdata").run();
    }
    model.save(OUT+label+"_size"+meshSize+".mph");
    ModelUtil.remove(tag);
  }

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    if(args.length==0 || args[0].equals("anchor")) {
      runCase("R2_L0975_A05",950.0,0.00975,3);
      runCase("R2_L1000_A05",950.0,0.01000,3);
      runCase("R2_L1025_A05",950.0,0.01025,3);
      runCase("R2_L1050_A05",950.0,0.01050,3);
      runCase("R2_L1075_A05",950.0,0.01075,3);
      return;
    }
    if(args[0].equals("confirm")) {
      runCase("R2_L1025_A03",1150.0,0.01025,3);
      runCase("R2_L1025_A07",750.0,0.01025,3);
      runCase("R2_L1025_A05_FINE",950.0,0.01025,2);
      return;
    }
    if(args[0].equals("blind")) {
      runCase("R2_L1025_A04",1050.0,0.01025,3);
      runCase("R2_L1025_A06",850.0,0.01025,3);
      return;
    }
    throw new RuntimeException("UNKNOWN_PHASE");
  }
}
