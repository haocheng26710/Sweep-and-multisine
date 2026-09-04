import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc27A03S2PhaseMesh {
  static final String ROOT="D:/Bristol course/dissertation/program work/";
  static final String BASE=ROOT+"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A/FC_L0900_A03_size3.mph";
  static final String OUT=ROOT+"scripts/gen_enc_27_a03_s2_phase_mesh/run_output/";

  static void probe()throws Exception{
    Model model=ModelUtil.load("probe",BASE);MeshSequence mesh=model.component("comp1").mesh("mesh1");mesh.feature("size").set("hauto","1");
    String[] keys={"custom","hmax","hmin","hgrad","hcurve","hnarrow"};
    for(String key:keys){try{System.out.println("PROBE "+key+"="+mesh.feature("size").getString(key));}catch(Exception e){System.out.println("PROBE "+key+"=UNAVAILABLE");}}
    mesh.run();System.out.println("PROBE elements="+mesh.getNumElem());ModelUtil.remove("probe");
  }

  static void configureMesh(MeshSequence mesh,String mode){
    if(mode.equals("G2")||mode.equals("G1")){mesh.feature("size").set("custom","off");mesh.feature("size").set("hauto",mode.equals("G2")?"2":"1");return;}
    double hmax=mode.equals("F32")?.0032:.0026;
    mesh.feature("size").set("custom","on");mesh.feature("size").set("hmax",hmax);mesh.feature("size").set("hmin",4.16e-5);
    mesh.feature("size").set("hgrad",1.3);mesh.feature("size").set("hcurve",.2);mesh.feature("size").set("hnarrow",1.0);
  }

  static void runCase(String mode)throws Exception{
    Model model=ModelUtil.load("m_"+mode,BASE);MeshSequence mesh=model.component("comp1").mesh("mesh1");configureMesh(mesh,mode);mesh.run();
    try{model.result().dataset().remove("pm_ref");}catch(Exception ignored){}try{model.result().export().remove("pm_ref_data");}catch(Exception ignored){}
    model.result().dataset().create("pm_ref","CutPoint3D");model.result().dataset("pm_ref").set("pointx",new double[]{-.015});
    model.result().dataset("pm_ref").set("pointy",new double[]{0});model.result().dataset("pm_ref").set("pointz",new double[]{.0046});
    model.result().export().create("pm_ref_data","Data");model.result().export("pm_ref_data").set("data","pm_ref");model.result().export("pm_ref_data").set("expr",new String[]{"p"});
    model.param().set("src_state","2");model.study("std1").feature("step1").set("plist","range(1020,2,1280)");
    System.out.printf(Locale.US,"AUDIT CASE %s elements=%d hmax=%s%n",mode,mesh.getNumElem(),mesh.feature("size").getString("hmax"));
    model.study("std1").run();
    model.result().export("fc_data").set("filename",OUT+mode+"_center_src2.txt");model.result().export("fc_data").run();
    model.result().export("pm_ref_data").set("filename",OUT+mode+"_westref_src2.txt");model.result().export("pm_ref_data").run();
    model.save(OUT+mode+"_src2.mph");ModelUtil.remove("m_"+mode);
  }

  public static void main(String[] args)throws Exception{
    ModelUtil.initStandalone(true);
    if(args==null||args.length==0||args[0].equals("probe")){probe();return;}
    runCase("G2");runCase("G1");runCase("F32");runCase("F26");
  }
}
