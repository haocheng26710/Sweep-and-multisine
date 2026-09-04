import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc25MeshSource0 {
  static final String ROOT="D:/Bristol course/dissertation/program work/";
  static final String BASE=ROOT+"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A/FC_L0900_A05_size3.mph";
  static final String OUT=ROOT+"scripts/gen_enc_25_mesh_source0/run_output/";

  static void addLocalSize(Model model,String tag,String namedSelection,int level,int position){
    MeshSequence mesh=model.component("comp1").mesh("mesh1");
    mesh.feature().create(tag,"Size");
    mesh.feature(tag).selection().named(namedSelection);
    mesh.feature(tag).set("hauto",Integer.toString(level));
    mesh.feature().move(tag,position);
    int count=model.component("comp1").selection(namedSelection).entities(3).length;
    if(count<1)throw new RuntimeException("EMPTY_LOCAL_SELECTION_"+namedSelection);
    System.out.printf(Locale.US,"AUDIT LOCAL tag=%s selection=%s domains=%d hauto=%d%n",tag,namedSelection,count,level);
  }

  static void runCase(String label,int globalSize,String mode)throws Exception{
    Model model=ModelUtil.load("m_"+label,BASE);
    MeshSequence mesh=model.component("comp1").mesh("mesh1");
    mesh.feature("size").set("hauto",Integer.toString(globalSize));
    if(mode.equals("LN2"))addLocalSize(model,"ms_neck","geom1_fc_neck_dom",2,1);
    if(mode.equals("LN1"))addLocalSize(model,"ms_neck","geom1_fc_neck_dom",1,1);
    if(mode.equals("LR2")){
      addLocalSize(model,"ms_neck","geom1_fc_neck_dom",2,1);
      addLocalSize(model,"ms_cavity","geom1_fc_cavity_dom",2,2);
    }
    mesh.run();
    model.param().set("src_state","0");
    model.study("std1").feature("step1").set("plist","range(820,2,1080)");
    System.out.printf(Locale.US,"AUDIT CASE %s global=%d mode=%s elements=%d%n",label,globalSize,mode,mesh.getNumElem());
    model.study("std1").run();
    model.result().export("fc_data").set("filename",OUT+label+"_src0.txt");
    model.result().export("fc_data").run();
    model.save(OUT+label+".mph");
    ModelUtil.remove("m_"+label);
  }

  public static void main(String[] args)throws Exception{
    ModelUtil.initStandalone(true);
    if(args==null||args.length==0||args[0].equals("global")){runCase("G1_SOURCE0",1,"GLOBAL");return;}
    if(!args[0].equals("local"))throw new RuntimeException("UNKNOWN_PHASE");
    runCase("LN2_SOURCE0",3,"LN2");
    runCase("LN1_SOURCE0",3,"LN1");
    runCase("LR2_SOURCE0",3,"LR2");
  }
}
