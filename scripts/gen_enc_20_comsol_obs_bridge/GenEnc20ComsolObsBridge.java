import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.util.*;

public class GenEnc20ComsolObsBridge {
  static final String BASE="D:/Bristol course/dissertation/program work/outputs/gen_enc/GEN_ENC_13_C2_ACOUSTIC_PREFLIGHT/C0_NEAR_01_lossy2d_size3.mph";
  static final String OUT="D:/Bristol course/dissertation/program work/scripts/gen_enc_20_comsol_obs_bridge/run_output/";
  static final double THICKNESS=0.023, AREA=8e-6, NECK_LENGTH=0.012, CAVITY_WIDTH=0.012;
  static final double PLENUM_HALF=0.0362053299278368/2.0, X_CENTER=0.009;

  static double cavityVolume(double f0) {
    return AREA*343.0*343.0/(NECK_LENGTH*Math.pow(2*Math.PI*f0,2));
  }

  static void addResonator(Model model,double f0) {
    GeomSequence geom=model.component("comp1").geom("geom1");
    double width=AREA/THICKNESS, area2d=cavityVolume(f0)/THICKNESS;
    geom.feature().create("hr_neck","Rectangle");
    geom.feature("hr_neck").set("size",new double[]{width,NECK_LENGTH});
    geom.feature("hr_neck").set("pos",new double[]{X_CENTER-width/2,PLENUM_HALF});
    geom.feature().create("hr_cavity","Rectangle");
    geom.feature("hr_cavity").set("size",new double[]{CAVITY_WIDTH,area2d/CAVITY_WIDTH});
    geom.feature("hr_cavity").set("pos",new double[]{X_CENTER-CAVITY_WIDTH/2,PLENUM_HALF+NECK_LENGTH});
    geom.feature().create("comp_void","Rectangle");
    geom.feature("comp_void").set("size",new double[]{0.010,area2d/0.010});
    geom.feature("comp_void").set("pos",new double[]{0.004,-PLENUM_HALF});
    geom.feature().create("plenum_comp","Difference");
    geom.feature("plenum_comp").selection("input").set(new String[]{"plenum"});
    geom.feature("plenum_comp").selection("input2").set(new String[]{"comp_void"});
    geom.run();
  }

  static void runCase(String label,double f0,int meshSize) throws Exception {
    String tag="m_"+label;
    Model model=ModelUtil.load(tag,BASE);
    if(f0>0) addResonator(model,f0);
    ModelNode comp=model.component("comp1");
    int[] counts=new int[]{comp.selection("port0_face").entities(1).length,comp.selection("port90_face").entities(1).length,comp.selection("port180_face").entities(1).length,comp.selection("port270_face").entities(1).length};
    for(int count:counts) if(count!=1) throw new RuntimeException("PORT_IDENTITY_FAILURE_"+label);
    System.out.printf(Locale.US,"AUDIT %s %.1f %d %s %.12g %.12g%n",label,f0,meshSize,Arrays.toString(counts),f0>0?cavityVolume(f0)*1e6:0.0,f0>0?cavityVolume(f0)/THICKNESS*1e6:0.0);
    comp.mesh("mesh1").feature("size").set("hauto",Integer.toString(meshSize));
    comp.mesh("mesh1").run();
    model.study("std1").feature("step1").set("plist","range(650,2,1250)");
    model.result().numerical().create("micpt","Interp");
    model.result().numerical("micpt").set("expr",new String[]{"p"});
    model.result().numerical("micpt").set("coord",new double[][]{{0.0},{0.0}});
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
    if(args.length==1 && args[0].equals("fine-only")) {
      runCase("ALPHA05_FINE",950.0,2);
      return;
    }
    runCase("CONTROL",0.0,3);
    runCase("ALPHA03",1150.0,3);
    runCase("ALPHA05",950.0,3);
    runCase("ALPHA07",750.0,3);
    runCase("ALPHA05_FINE",950.0,2);
  }
}
