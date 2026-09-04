import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc24PrintComp {
  static final String ROOT="D:/Bristol course/dissertation/program work/";
  static final String BASE=ROOT+"outputs/gen_enc/GEN_ENC_9_LOSS_3D_BRIDGE/NEAR_01_lossy3d_eta0p02_size1.mph";
  static final String OUT=ROOT+"scripts/gen_enc_24_print_comp/run_output/";
  static final double AREA=8e-6,EFFECTIVE_LENGTH=0.012,HALF=0.0362053299278368/2.0,THICKNESS=0.0092;

  static double cavityVolume(double targetHz){return AREA*343.0*343.0/(EFFECTIVE_LENGTH*Math.pow(2*Math.PI*targetHz,2));}

  static double addFourFillers(GeomSequence geom,double volume){
    double side=Math.sqrt(volume/(4*THICKNESS));
    String[] tags={"fc_ne","fc_nw","fc_sw","fc_se"};
    double[][] pos={{HALF-side,HALF-side,0},{-HALF,HALF-side,0},{-HALF,-HALF,0},{HALF-side,-HALF,0}};
    for(int i=0;i<4;i++){
      geom.feature().create(tags[i],"Block");geom.feature(tags[i]).set("size",new double[]{side,side,THICKNESS});geom.feature(tags[i]).set("pos",pos[i]);
    }
    geom.feature().create("fc_plenum","Difference");geom.feature("fc_plenum").selection("input").set(new String[]{"plenum"});
    geom.feature("fc_plenum").selection("input2").set(tags);geom.feature("fc_plenum").set("selresult","on");
    return side;
  }

  static String addGeometry(Model model,double targetHz,double length,boolean resonator){
    double volume=cavityVolume(targetHz),side;
    GeomSequence geom=model.component("comp1").geom("geom1");side=addFourFillers(geom,volume);
    if(resonator){
      geom.feature().create("fc_neck","Block");geom.feature("fc_neck").set("size",new double[]{0.002,0.004,length});
      geom.feature("fc_neck").set("pos",new double[]{0.011,-0.002,THICKNESS});geom.feature("fc_neck").set("selresult","on");
      double cavitySide=0.017;
      geom.feature().create("fc_cavity","Block");geom.feature("fc_cavity").set("size",new double[]{cavitySide,cavitySide,volume/(cavitySide*cavitySide)});
      geom.feature("fc_cavity").set("pos",new double[]{0.0035,-0.0085,THICKNESS+length});geom.feature("fc_cavity").set("selresult","on");
    }
    geom.run();
    double clearance=HALF-side-.001;
    if(clearance<.002)throw new RuntimeException("FOUR_CORNER_CLEARANCE_FAILURE");
    return resonator?"geom1_fc_neck_dom":"";
  }

  static void selectPorts(Model model){
    ModelNode comp=model.component("comp1");String[] phys={"nv0","nv90","nv180","nv270"},sels={"port0_face","port90_face","port180_face","port270_face"};
    for(int i=0;i<4;i++){comp.physics("acpr").feature(phys[i]).selection().named(sels[i]);if(comp.selection(sels[i]).entities(2).length!=1)throw new RuntimeException("PORT_FAILURE_"+sels[i]);}
  }

  static void addNra(Model model,String neck){
    ModelNode comp=model.component("comp1");
    if(comp.selection(neck).entities(3).length!=1)throw new RuntimeException("NECK_DOMAIN_FAILURE");
    comp.physics("acpr").feature().create("fc_nra","NarrowRegionAcousticsModel",3);comp.physics("acpr").feature("fc_nra").selection().named(neck);
    comp.physics("acpr").feature("fc_nra").set("DuctType","RectangularDuct");comp.physics("acpr").feature("fc_nra").set("a_rect","2[mm]");comp.physics("acpr").feature("fc_nra").set("b_rect","4[mm]");
    comp.physics("acpr").feature("fc_nra").set("rho_mat","userdef");comp.physics("acpr").feature("fc_nra").set("rho","1.204[kg/m^3]");
    comp.physics("acpr").feature("fc_nra").set("c_mat","userdef");comp.physics("acpr").feature("fc_nra").set("c","343[m/s]");
    comp.physics("acpr").feature("fc_nra").set("mu_mat","userdef");comp.physics("acpr").feature("fc_nra").set("mu","1.814e-5[Pa*s]");
    comp.physics("acpr").feature("fc_nra").set("kcond_mat","userdef");comp.physics("acpr").feature("fc_nra").set("kcond","0.0257[W/(m*K)]");
    comp.physics("acpr").feature("fc_nra").set("Cp_mat","userdef");comp.physics("acpr").feature("fc_nra").set("Cp","1005[J/(kg*K)]");
    comp.physics("acpr").feature("fc_nra").set("gamma_mat","userdef");comp.physics("acpr").feature("fc_nra").set("gamma","1.4");
  }

  static void staticCase(String label,double targetHz)throws Exception{
    Model model=ModelUtil.load("m_"+label,BASE);String neck=addGeometry(model,targetHz,.009,true);selectPorts(model);
    ModelNode comp=model.component("comp1");int p=comp.selection("geom1_fc_plenum_dom").entities(3).length,n=comp.selection(neck).entities(3).length,c=comp.selection("geom1_fc_cavity_dom").entities(3).length;
    if(p!=1||n!=1||c!=1)throw new RuntimeException("DOMAIN_FAILURE_"+label);
    double side=Math.sqrt(cavityVolume(targetHz)/(4*THICKNESS));
    System.out.printf(Locale.US,"AUDIT STATIC %s target=%.0f side_mm=%.9f clearance_mm=%.9f domains=%d,%d,%d ports=1,1,1,1%n",label,targetHz,side*1e3,(HALF-side-.001)*1e3,p,n,c);
    ModelUtil.remove("m_"+label);
  }

  static void runCase(String label,double targetHz,double length,boolean resonator,int meshSize)throws Exception{
    Model model=ModelUtil.load("m_"+label,BASE);String neck=addGeometry(model,targetHz,length,resonator);selectPorts(model);if(resonator)addNra(model,neck);
    model.component("comp1").mesh("mesh1").feature("size").set("hauto",Integer.toString(meshSize));model.component("comp1").mesh("mesh1").run();
    model.study("std1").feature("step1").set("plist",String.format(Locale.US,"range(%.0f,2,%.0f)",targetHz-130,targetHz+130));
    try{model.result().dataset().remove("fc_cpt");}catch(Exception ignored){}try{model.result().export().remove("fc_data");}catch(Exception ignored){}
    model.result().dataset().create("fc_cpt","CutPoint3D");model.result().dataset("fc_cpt").set("pointx",new double[]{0});model.result().dataset("fc_cpt").set("pointy",new double[]{0});model.result().dataset("fc_cpt").set("pointz",new double[]{THICKNESS/2});
    model.result().export().create("fc_data","Data");model.result().export("fc_data").set("data","fc_cpt");model.result().export("fc_data").set("expr",new String[]{"p"});
    System.out.printf(Locale.US,"AUDIT %s target=%.0f length_mm=%.3f resonator=%s mesh=%d%n",label,targetHz,length*1e3,resonator,meshSize);
    for(int source=0;source<4;source++){model.param().set("src_state",Integer.toString(source));model.study("std1").run();model.result().export("fc_data").set("filename",OUT+label+"_size"+meshSize+"_src"+source+".txt");model.result().export("fc_data").run();}
    model.save(OUT+label+"_size"+meshSize+".mph");ModelUtil.remove("m_"+label);
  }

  public static void main(String[] args)throws Exception{
    ModelUtil.initStandalone(true);
    if(args==null||args.length==0||args[0].equals("static")){
      staticCase("FC_A03",1150);staticCase("FC_A04",1050);staticCase("FC_A05",950);staticCase("FC_A06",850);staticCase("FC_A07",750);return;
    }
    if(args[0].equals("anchor")){
      runCase("FC_CONTROL_A05",950,.009,false,3);
      runCase("FC_L0850_A05",950,.00850,true,3);runCase("FC_L0875_A05",950,.00875,true,3);runCase("FC_L0900_A05",950,.00900,true,3);runCase("FC_L0925_A05",950,.00925,true,3);runCase("FC_L0950_A05",950,.00950,true,3);return;
    }
    if(args[0].equals("confirm")){
      runCase("FC_L0900_A05",950,.00900,true,2);
      runCase("FC_CONTROL_A03",1150,.00900,false,3);runCase("FC_L0900_A03",1150,.00900,true,3);
      runCase("FC_CONTROL_A07",750,.00900,false,3);runCase("FC_L0900_A07",750,.00900,true,3);return;
    }
    throw new RuntimeException("UNKNOWN_PHASE");
  }
}
