from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent
nodes=[65,150,235,320]
segments=[59,73,73,73,74]
fig,ax=plt.subplots(figsize=(13,5),dpi=180)
# base modules
for x0 in [0,100,200,300]:
    ax.add_patch(plt.Rectangle((x0,-25),100,50,facecolor='0.96',edgecolor='0.75',lw=1))
    ax.text(x0+50,22,f'Base {chr(65+x0//100)}',ha='center',va='center',fontsize=8)
# rails
ax.plot([0,400],[8,8],lw=5,label='TX bus (speaker)',solid_capstyle='butt')
ax.plot([0,400],[-8,-8],lw=5,label='RX bus (microphone)',solid_capstyle='butt')
# node blocks and bridges
for i,x in enumerate(nodes,1):
    ax.add_patch(plt.Rectangle((x-6,2),12,12,facecolor='white',edgecolor='black',lw=1.0))
    ax.add_patch(plt.Rectangle((x-6,-14),12,12,facecolor='white',edgecolor='black',lw=1.0))
    ax.plot([x,x],[-6,6],lw=2,ls='--')
    ax.text(x,17,f'N{i}\n{x} mm',ha='center',va='bottom',fontsize=8)
# Interfaces
ax.annotate('Speaker interface\nTX x=0 reference',xy=(0,8),xytext=(-35,28),arrowprops=dict(arrowstyle='->'),ha='center',fontsize=8)
ax.annotate('Microphone interface\nRX x=0 reference',xy=(0,-8),xytext=(-35,-30),arrowprops=dict(arrowstyle='->'),ha='center',fontsize=8)
ax.annotate('Universal end seat\nx=400 reference',xy=(400,0),xytext=(445,0),arrowprops=dict(arrowstyle='->'),ha='center',fontsize=8)
# Center spacing
ax.annotate('',xy=(40,8),xytext=(40,-8),arrowprops=dict(arrowstyle='<->'))
ax.text(44,0,'16 mm\ncentre spacing',va='center',fontsize=8)
# module boundaries and segment lengths
for x in [100,200,300]:
    ax.axvline(x,color='0.6',ls=':',lw=1)
# Acoustic segment labels between T central blocks
bounds=[0,59,71,144,156,229,241,314,326,400]
labels=['59','12','73','12','73','12','73','12','74']
for a,b,l in zip(bounds[:-1],bounds[1:],labels):
    ax.annotate('',xy=(b,-20),xytext=(a,-20),arrowprops=dict(arrowstyle='<->',lw=0.7))
    ax.text((a+b)/2,-23,l+' mm',ha='center',va='top',fontsize=7)
ax.text(200,-34,'Acoustic axis total = 400 mm; T-node central acoustic length = 12 mm',ha='center',fontsize=9)
# bridge detail inset text
ax.text(200,31,'Standard bridge: 2 mm ID / assumed 4 mm OD soft tube, cut length 12.0 mm; wall-to-wall air path = 12.0 mm',ha='center',fontsize=9)
ax.set_xlim(-55,470); ax.set_ylim(-42,40); ax.set_aspect('equal',adjustable='box'); ax.axis('off')
ax.legend(loc='lower center',bbox_to_anchor=(0.5,-0.02),ncol=2,frameon=False,fontsize=8)
fig.tight_layout()
fig.savefig(root/'assembly_layout.png',bbox_inches='tight')
fig.savefig(root/'assembly_layout.svg',bbox_inches='tight')
