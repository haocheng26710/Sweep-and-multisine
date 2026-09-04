import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.*;

public class GenEnc26PrintConvB {
  static final String ROOT="D:/Bristol course/dissertation/program work/";
  static final String PREV=ROOT+"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A/";
  static final String OUT=ROOT+"scripts/gen_enc_26_print_conv_b/run_output/";

  static void runAllSources(String label,double target)throws Exception{
    Model model=ModelUtil.load("m_"+label,PREV+label+"_size3.mph");
    MeshSequence mesh=model.component("comp1").mesh("mesh1");
    mesh.feature("size").set("hauto","2");mesh.run();
    model.study("std1").feature("step1").set("plist",String.format(Locale.US,"range(%.0f,2,%.0f)",target-130,target+130));
    System.out.printf(Locale.US,"AUDIT CASE %s target=%.0f mesh=2 elements=%d%n",label,target,mesh.getNumElem());
    for(int source=0;source<4;source++){
      model.param().set("src_state",Integer.toString(source));model.study("std1").run();
      model.result().export("fc_data").set("filename",OUT+label+"_size2_src"+source+".txt");model.result().export("fc_data").run();
    }
    model.save(OUT+label+"_size2.mph");ModelUtil.remove("m_"+label);
  }

  static void runAdaptiveSize1(String label,double target,int[] sources)throws Exception{
    Model model=ModelUtil.load("m_"+label,PREV+label+"_size3.mph");
    MeshSequence mesh=model.component("comp1").mesh("mesh1");mesh.feature("size").set("hauto","1");mesh.run();
    model.study("std1").feature("step1").set("plist",String.format(Locale.US,"range(%.0f,2,%.0f)",target-130,target+130));
    System.out.printf(Locale.US,"AUDIT ADAPTIVE %s target=%.0f mesh=1 elements=%d sources=%s%n",label,target,mesh.getNumElem(),Arrays.toString(sources));
    for(int source:sources){model.param().set("src_state",Integer.toString(source));model.study("std1").run();model.result().export("fc_data").set("filename",OUT+label+"_size1_src"+source+".txt");model.result().export("fc_data").run();}
    model.save(OUT+label+"_size1.mph");ModelUtil.remove("m_"+label);
  }

  public static void main(String[] args)throws Exception{
    ModelUtil.initStandalone(true);
    if(args!=null&&args.length>0&&args[0].equals("adaptive")){
      runAdaptiveSize1("FC_L0900_A03",1150,new int[]{0,1,2});runAdaptiveSize1("FC_L0900_A07",750,new int[]{0});return;
    }
    runAllSources("FC_CONTROL_A03",1150);runAllSources("FC_L0900_A03",1150);
    runAllSources("FC_CONTROL_A05",950);
    runAllSources("FC_CONTROL_A07",750);runAllSources("FC_L0900_A07",750);
  }
}
