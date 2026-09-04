import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc23PrintCal {
  static final String ROOT="D:/Bristol course/dissertation/program work/";
  static final String BASE=ROOT+"outputs/gen_enc/GEN_ENC_9_LOSS_3D_BRIDGE/NEAR_01_lossy3d_eta0p02_size1.mph";
  static final String OUT=ROOT+"scripts/gen_enc_23_print_cal/run_output/";
  static final double AREA=8e-6,EFFECTIVE_LENGTH=0.012,HALF=0.0362053299278368/2.0,THICKNESS=0.0092;

  static double cavityVolume(double targetHz) {
    return AREA*343.0*343.0/(EFFECTIVE_LENGTH*Math.pow(2*Math.PI*targetHz,2));
  }

  static String addPrintable(Model model,double targetHz,double length,double neckA,double neckB) {
    double volume=cavityVolume(targetHz),fillerHeight=0.0082,fillerSide=Math.sqrt(volume/fillerHeight),cavitySide=0.017;
    GeomSequence geom=model.component("comp1").geom("geom1");
    geom.feature().create("pc_filler","Block");
    geom.feature("pc_filler").set("size",new double[]{fillerSide,fillerSide,fillerHeight});
    geom.feature("pc_filler").set("pos",new double[]{HALF-fillerSide,-HALF,0});
    geom.feature().create("pc_plenum","Difference");
    geom.feature("pc_plenum").selection("input").set(new String[]{"plenum"});
    geom.feature("pc_plenum").selection("input2").set(new String[]{"pc_filler"});
    geom.feature("pc_plenum").set("selresult","on");
    geom.feature().create("pc_neck","Block");
    geom.feature("pc_neck").set("size",new double[]{neckA,neckB,length});
    geom.feature("pc_neck").set("pos",new double[]{0.012-neckA/2,-neckB/2,THICKNESS});
    geom.feature("pc_neck").set("selresult","on");
    geom.feature().create("pc_cavity","Block");
    geom.feature("pc_cavity").set("size",new double[]{cavitySide,cavitySide,volume/(cavitySide*cavitySide)});
    geom.feature("pc_cavity").set("pos",new double[]{0.0035,-0.0085,THICKNESS+length});
    geom.feature("pc_cavity").set("selresult","on");
    geom.run();
    return "geom1_pc_neck_dom";
  }

  static void selectPorts(Model model) {
    ModelNode comp=model.component("comp1");
    String[] phys={"nv0","nv90","nv180","nv270"},sels={"port0_face","port90_face","port180_face","port270_face"};
    for(int i=0;i<4;i++) {
      comp.physics("acpr").feature(phys[i]).selection().named(sels[i]);
      if(comp.selection(sels[i]).entities(2).length!=1)throw new RuntimeException("PORT_IDENTITY_FAILURE_"+sels[i]);
    }
  }

  static void configurePhysics(Model model,String neckSelection,double neckA,double neckB) {
    ModelNode comp=model.component("comp1");selectPorts(model);
    if(comp.selection(neckSelection).entities(3).length!=1)throw new RuntimeException("NECK_DOMAIN_FAILURE");
    comp.physics("acpr").feature().create("pc_nra","NarrowRegionAcousticsModel",3);
    comp.physics("acpr").feature("pc_nra").selection().named(neckSelection);
    comp.physics("acpr").feature("pc_nra").set("DuctType","RectangularDuct");
    comp.physics("acpr").feature("pc_nra").set("a_rect",Double.toString(neckA));
    comp.physics("acpr").feature("pc_nra").set("b_rect",Double.toString(neckB));
    comp.physics("acpr").feature("pc_nra").set("rho_mat","userdef");comp.physics("acpr").feature("pc_nra").set("rho","1.204[kg/m^3]");
    comp.physics("acpr").feature("pc_nra").set("c_mat","userdef");comp.physics("acpr").feature("pc_nra").set("c","343[m/s]");
    comp.physics("acpr").feature("pc_nra").set("mu_mat","userdef");comp.physics("acpr").feature("pc_nra").set("mu","1.814e-5[Pa*s]");
    comp.physics("acpr").feature("pc_nra").set("kcond_mat","userdef");comp.physics("acpr").feature("pc_nra").set("kcond","0.0257[W/(m*K)]");
    comp.physics("acpr").feature("pc_nra").set("Cp_mat","userdef");comp.physics("acpr").feature("pc_nra").set("Cp","1005[J/(kg*K)]");
    comp.physics("acpr").feature("pc_nra").set("gamma_mat","userdef");comp.physics("acpr").feature("pc_nra").set("gamma","1.4");
  }

  static void runCase(String label,double targetHz,double length,double neckA,double neckB,int meshSize) throws Exception {
    Model model=ModelUtil.load("m_"+label,BASE);
    if(length>0) {
      String neck=addPrintable(model,targetHz,length,neckA,neckB);configurePhysics(model,neck,neckA,neckB);
    } else selectPorts(model);
    model.component("comp1").mesh("mesh1").feature("size").set("hauto",Integer.toString(meshSize));
    model.component("comp1").mesh("mesh1").run();
    model.study("std1").feature("step1").set("plist",String.format(Locale.US,"range(%.0f,2,%.0f)",targetHz-130,targetHz+130));
    try{model.result().dataset().remove("pc_cpt");}catch(Exception ignored){}
    try{model.result().export().remove("pc_data");}catch(Exception ignored){}
    model.result().dataset().create("pc_cpt","CutPoint3D");
    model.result().dataset("pc_cpt").set("pointx",new double[]{0.0});model.result().dataset("pc_cpt").set("pointy",new double[]{0.0});model.result().dataset("pc_cpt").set("pointz",new double[]{THICKNESS/2});
    model.result().export().create("pc_data","Data");model.result().export("pc_data").set("data","pc_cpt");model.result().export("pc_data").set("expr",new String[]{"p"});
    System.out.printf(Locale.US,"AUDIT %s target=%.1f length_mm=%.3f neck_mm=%.3fx%.3f mesh=%d volume_cm3=%.9f control=%s%n",label,targetHz,length*1e3,neckA*1e3,neckB*1e3,meshSize,cavityVolume(targetHz)*1e6,length<=0);
    for(int source=0;source<4;source++) {
      model.param().set("src_state",Integer.toString(source));model.study("std1").run();
      model.result().export("pc_data").set("filename",OUT+label+"_size"+meshSize+"_src"+source+".txt");model.result().export("pc_data").run();
    }
    model.save(OUT+label+"_size"+meshSize+".mph");ModelUtil.remove("m_"+label);
  }

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    if(args==null||args.length==0||args[0].equals("anchor")) {
      runCase("L0800_A05",950,0.00800,0.002,0.004,4);
      runCase("L0825_A05",950,0.00825,0.002,0.004,4);
      runCase("L0850_A05",950,0.00850,0.002,0.004,4);
      runCase("L0875_A05",950,0.00875,0.002,0.004,4);
      runCase("L0900_A05",950,0.00900,0.002,0.004,4);
      return;
    }
    if(args[0].equals("confirm")) {
      runCase("TRUE3D_CONTROL_A03",1150,-1,0.002,0.004,4);
      runCase("L0900_A03",1150,0.009,0.002,0.004,4);
      runCase("TRUE3D_CONTROL_A07",750,-1,0.002,0.004,4);
      runCase("L0900_A07",750,0.009,0.002,0.004,4);
      runCase("L0900_A05_FINE",950,0.009,0.002,0.004,3);
      return;
    }
    throw new RuntimeException("UNKNOWN_PHASE");
  }
}
