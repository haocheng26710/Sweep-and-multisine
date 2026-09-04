import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc22PrintBridge {
  static final String ROOT="D:/Bristol course/dissertation/program work/";
  static final String TRUE_BASE=ROOT+"outputs/gen_enc/GEN_ENC_9_LOSS_3D_BRIDGE/NEAR_01_lossy3d_eta0p02_size1.mph";
  static final String EQ_BASE=ROOT+"outputs/gen_enc/GEN_ENC_9_LOSS_3D_BRIDGE/NEAR_01_extruded_area3d_control.mph";
  static final String OUT=ROOT+"scripts/gen_enc_22_print_bridge/run_output/";
  static final double AREA=8e-6, EFFECTIVE_LENGTH=0.012, PHYSICAL_LENGTH=0.01025;
  static final double PLENUM_HALF=0.0362053299278368/2.0, TRUE_THICKNESS=0.0092;

  static double cavityVolume(double targetHz) {
    return AREA*343.0*343.0/(EFFECTIVE_LENGTH*Math.pow(2*Math.PI*targetHz,2));
  }

  static void selectPorts(Model model) {
    ModelNode comp=model.component("comp1");
    String[] phys={"nv0","nv90","nv180","nv270"};
    String[] sels={"port0_face","port90_face","port180_face","port270_face"};
    for(int i=0;i<4;i++) {
      comp.physics("acpr").feature(phys[i]).selection().named(sels[i]);
      int count=comp.selection(sels[i]).entities(2).length;
      if(count!=1) throw new RuntimeException("PORT_IDENTITY_FAILURE_"+sels[i]+"_"+count);
    }
  }

  static void addFiller(GeomSequence geom,double volume,String prefix) {
    double height=0.0082, side=Math.sqrt(volume/height);
    geom.feature().create(prefix+"_filler","Block");
    geom.feature(prefix+"_filler").set("size",new double[]{side,side,height});
    geom.feature(prefix+"_filler").set("pos",new double[]{PLENUM_HALF-side,-PLENUM_HALF,0});
    geom.feature().create(prefix+"_plenum","Difference");
    geom.feature(prefix+"_plenum").selection("input").set(new String[]{"plenum"});
    geom.feature(prefix+"_plenum").selection("input2").set(new String[]{prefix+"_filler"});
    geom.feature(prefix+"_plenum").set("selresult","on");
  }

  static String addEquivalent(Model model,double targetHz) {
    double volume=cavityVolume(targetHz), width=AREA/TRUE_THICKNESS;
    GeomSequence geom=model.component("comp1").geom("geom1");
    addFiller(geom,volume,"eq");
    geom.feature().create("eq_neck","Block");
    geom.feature("eq_neck").set("size",new double[]{width,PHYSICAL_LENGTH,TRUE_THICKNESS});
    geom.feature("eq_neck").set("pos",new double[]{0.012-width/2,PLENUM_HALF,0});
    geom.feature("eq_neck").set("selresult","on");
    double cavityWidth=0.025, cavityLength=volume/(cavityWidth*TRUE_THICKNESS);
    geom.feature().create("eq_cavity","Block");
    geom.feature("eq_cavity").set("size",new double[]{cavityWidth,cavityLength,TRUE_THICKNESS});
    geom.feature("eq_cavity").set("pos",new double[]{0.012-cavityWidth/2,PLENUM_HALF+PHYSICAL_LENGTH,0});
    geom.feature("eq_cavity").set("selresult","on");
    geom.run();
    return "geom1_eq_neck_dom";
  }

  static String addPrintable(Model model,double targetHz) {
    double volume=cavityVolume(targetHz), cavitySide=0.017;
    GeomSequence geom=model.component("comp1").geom("geom1");
    addFiller(geom,volume,"pb");
    geom.feature().create("pb_neck","Block");
    geom.feature("pb_neck").set("size",new double[]{0.002,0.004,PHYSICAL_LENGTH});
    geom.feature("pb_neck").set("pos",new double[]{0.011,-0.002,TRUE_THICKNESS});
    geom.feature("pb_neck").set("selresult","on");
    geom.feature().create("pb_cavity","Block");
    geom.feature("pb_cavity").set("size",new double[]{cavitySide,cavitySide,volume/(cavitySide*cavitySide)});
    geom.feature("pb_cavity").set("pos",new double[]{0.0035,-0.0085,TRUE_THICKNESS+PHYSICAL_LENGTH});
    geom.feature("pb_cavity").set("selresult","on");
    geom.run();
    return "geom1_pb_neck_dom";
  }

  static void addNarrowRegion(Model model,String neckSelection) {
    model.component("comp1").physics("acpr").feature().create("pb_nra","NarrowRegionAcousticsModel",3);
    model.component("comp1").physics("acpr").feature("pb_nra").selection().named(neckSelection);
    model.component("comp1").physics("acpr").feature("pb_nra").set("DuctType","RectangularDuct");
    model.component("comp1").physics("acpr").feature("pb_nra").set("a_rect","2[mm]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("b_rect","4[mm]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("rho_mat","userdef");
    model.component("comp1").physics("acpr").feature("pb_nra").set("rho","1.204[kg/m^3]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("c_mat","userdef");
    model.component("comp1").physics("acpr").feature("pb_nra").set("c","343[m/s]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("mu_mat","userdef");
    model.component("comp1").physics("acpr").feature("pb_nra").set("mu","1.814e-5[Pa*s]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("kcond_mat","userdef");
    model.component("comp1").physics("acpr").feature("pb_nra").set("kcond","0.0257[W/(m*K)]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("Cp_mat","userdef");
    model.component("comp1").physics("acpr").feature("pb_nra").set("Cp","1005[J/(kg*K)]");
    model.component("comp1").physics("acpr").feature("pb_nra").set("gamma_mat","userdef");
    model.component("comp1").physics("acpr").feature("pb_nra").set("gamma","1.4");
  }

  static void runCase(String label,String base,String geometry,boolean narrow,int meshSize) throws Exception {
    Model model=ModelUtil.load("m_"+label,base);
    String neck="";
    if(geometry.equals("eq")) neck=addEquivalent(model,950.0);
    if(geometry.equals("print")) neck=addPrintable(model,950.0);
    if(narrow) addNarrowRegion(model,neck);
    selectPorts(model);
    if(!geometry.equals("control") && model.component("comp1").selection(neck).entities(3).length!=1)
      throw new RuntimeException("NECK_DOMAIN_FAILURE_"+label);
    model.component("comp1").mesh("mesh1").feature("size").set("hauto",Integer.toString(meshSize));
    model.component("comp1").mesh("mesh1").run();
    model.study("std1").feature("step1").set("plist","range(820,2,1080)");
    try { model.result().dataset().remove("pb_cpt"); } catch(Exception ignored) {}
    try { model.result().export().remove("pb_data"); } catch(Exception ignored) {}
    model.result().dataset().create("pb_cpt","CutPoint3D");
    model.result().dataset("pb_cpt").set("pointx",new double[]{0.0});
    model.result().dataset("pb_cpt").set("pointy",new double[]{0.0});
    model.result().dataset("pb_cpt").set("pointz",new double[]{TRUE_THICKNESS/2});
    model.result().export().create("pb_data","Data");
    model.result().export("pb_data").set("data","pb_cpt");
    model.result().export("pb_data").set("expr",new String[]{"p"});
    System.out.printf(Locale.US,"AUDIT %s geometry=%s nra=%s mesh=%d volume_cm3=%.9f%n",label,geometry,narrow,meshSize,cavityVolume(950)*1e6);
    for(int source=0;source<4;source++) {
      model.param().set("src_state",Integer.toString(source));
      model.study("std1").run();
      model.result().export("pb_data").set("filename",OUT+label+"_size"+meshSize+"_src"+source+".txt");
      model.result().export("pb_data").run();
    }
    model.save(OUT+label+"_size"+meshSize+".mph");
    ModelUtil.remove("m_"+label);
  }

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    if(args==null || args.length==0 || args[0].equals("representative")) {
      runCase("EQ3D_A05",EQ_BASE,"eq",false,4);
      runCase("TRUE3D_CONTROL",TRUE_BASE,"control",false,4);
      runCase("PRINT3D_A05_BULK",TRUE_BASE,"print",false,4);
      runCase("PRINT3D_A05_NRA",TRUE_BASE,"print",true,4);
      return;
    }
    if(args[0].equals("fine")) {
      runCase("PRINT3D_A05_NRA_FINE",TRUE_BASE,"print",true,3);
      return;
    }
    if(args[0].equals("nra_retry")) {
      runCase("PRINT3D_A05_NRA",TRUE_BASE,"print",true,4);
      return;
    }
    throw new RuntimeException("UNKNOWN_PHASE");
  }
}
