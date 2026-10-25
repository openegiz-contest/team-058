#!/usr/bin/env python3
"""Create a standalone competition presentation from real executed simulation results."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'presentation.pdf'
DATA=json.loads((ROOT/'team/oreflow/reports/benchmark.json').read_text())
W,H=960,540
NAVY='#0B1422'; PANEL='#132538'; LINE='#2B4359'; CYAN='#69CBDE'; GOLD='#E6B76D'; WHITE='#E9F2FC'; SOFT='#93AEC6'; GREEN='#71D6AF'; RED='#FE8B95'
pdfmetrics.registerFont(TTFont('DVS','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVSB','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
C=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
C.setTitle('OreFlow KZ — North Pit Digital Mine | Team 058')

def bg():
 C.setFillColor(NAVY);C.rect(0,0,W,H,fill=1,stroke=0)
 C.setStrokeColor('#1c3347')
 for x in range(0,960,64):C.line(x,0,x,540)
 for y in range(0,540,64):C.line(0,y,960,y)
 C.setFillColor('#08101c');C.rect(0,0,960,32,fill=1,stroke=0)
 C.setFont('DVS',9);C.setFillColor(SOFT);C.drawString(42,13,'OREFLOW KZ   /   NORTH PIT INTELLIGENCE   /   TEAM 058')
 C.drawRightString(920,13,'SOURCE-CONFIGURED MINE  •  SIMULATION DATA')

def text(x,y,string,size=12,color=WHITE,bold=False):
 C.setFillColor(color);C.setFont('DVSB' if bold else 'DVS',size);C.drawString(x,y,string)

def multiline(x,y,lines,size=13,leading=22,color=SOFT):
 for i,l in enumerate(lines):text(x,y-i*leading,l,size,color)

def start(kicker,title,sub=None):
 bg();text(43,487,kicker,11,CYAN,True);text(43,442,title,31,WHITE,True)
 if sub:text(43,408,sub,11,SOFT)

def box(x,y,w,h,title=None):
 C.setFillColor(PANEL);C.setStrokeColor(LINE);C.roundRect(x,y,w,h,13,fill=1,stroke=1)
 if title:text(x+16,y+h-27,title,13,WHITE,True)

def foot(num):
 text(899,13,f'{num:02d}',8,SOFT)
 C.showPage()

def metric(x,y,value,label,w=250):
 box(x,y,w,110);text(x+17,y+58,str(value),28,CYAN,True);text(x+17,y+28,label,11,SOFT)

# 1 Cover
bg();C.setFillColor('#16314a');C.circle(812,315,235,stroke=0,fill=1)
C.setFillColor('#1e5872');C.circle(812,315,155,stroke=0,fill=1)
C.setFillColor('#2c95ad');C.circle(812,315,72,stroke=0,fill=1)
text(54,448,'TEAM 058  /  DIGITAL MINE ON OPENEGIZ',13,CYAN,True)
text(54,360,'OREFLOW KZ',52,WHITE,True)
text(54,307,'Autonomous Mine',34,WHITE,True)
text(54,262,'Control Center',34,WHITE,True)
multiline(55,186,['71 source-configured trucks • 20 shovels • dynamic dispatch',
                  'Real operating constraints. Reversible disruption scenarios.',
                  'Measured simulation comparisons, not fabricated AI metrics.'],12,24)
foot(1)
# 2
start('THE PROBLEM','Every assignment has a cost','A dispatcher faces queues, slow loading sites, long haul routes and sudden failures.')
for i,(big,small) in enumerate([('01','Where does this truck load?'),('02','Which dump receives this ore?'),('03','What if the shovel fails?')]):
 x=43+i*300;box(x,180,280,178);text(x+19,299,big,26,CYAN,True);text(x+19,252,small,14,WHITE,True)
 text(x+19,218,'Each decision affects queues and',11,SOFT);text(x+19,196,'total mine production.',11,SOFT)
foot(2)
#3
start('SOURCE / PROVENANCE','North Pit, without inventing a fleet','Anonymized OpenMines source configuration; MIT license, copied intact.')
metric(43,255,'71','TRUCKS',260);metric(338,255,'20','SHOVELS',260);metric(632,255,'10','LOAD + DUMP SITES',260)
multiline(55,208,['9 × 77 t  •  29 × 35 t  •  33 × 55 t',
                   'Road distance matrices and shovel loading rates come from the original JSON.',
                   'All journeys, queues, outages and moving markers are calculated simulation outputs.'],13,32)
foot(3)
#4
start('MODEL / LOGIC','A mine that actually behaves','An event-driven simulator tracks individual truck and service-device availability.')
labels=['Dispatch','Travel empty','Wait + load','Haul ore','Wait + dump','Return']
for i,l in enumerate(labels):
 x=48+i*149;box(x,290,133,85);text(x+10,343,f'{i+1:02d}',12,CYAN,True);text(x+10,311,l,11,WHITE,True)
 if i<5:text(x+136,330,'→',15,CYAN)
multiline(55,245,['Truck capacity is enforced. Shovel rates depend on configured bucket size and cycle time.',
                   'All 71 trucks can operate simultaneously. Two trucks cannot occupy the same truck state at once.',
                   'Disruptions alter service availability or valid routes; recovery is then re-simulated.'],12,28)
foot(4)
#5
start('EVIDENCE / NORMAL RUN','The optimizer makes a measurable difference','Four-hour simulation, seed 42. Same source parameters and seeded travel variation.')
base=DATA['single_seed_comparison']['nearest'];opt=DATA['single_seed_comparison']['smart']
box(42,148,874,220)
for i,(label,val,clr) in enumerate([('NEAREST RULE',base['tonnes'],GOLD),('ORE FLOW OPTIMIZER',opt['tonnes'],CYAN)]):
 y=301-i*105;text(62,y,label,12,WHITE,True)
 C.setFillColor('#203849');C.roundRect(290,y-13,510,27,6,fill=1,stroke=0)
 C.setFillColor(clr);C.roundRect(290,y-13,510*val/16000,27,6,fill=1,stroke=0)
 text(812,y-1,f'{val:,} t',14,WHITE,True)
text(56,112,'+52.48% delivered tonnes • seed 42',17,GREEN,True)
text(56,79,'Queue: 25.51 → 10.81 minutes  |  Trips: 203 → 317  |  Simulated outcome only',11,SOFT)
foot(5)
#6
start('REPRODUCIBILITY','Independent seed comparison','After policy-weight selection, evaluate on held-out seeds 21–31.')
normal=DATA['heldout_seed_experiments']['normal']
metric(45,265,f"+{normal['mean_change_pct']}%",'MEAN PAIRED TONNAGE GAIN',265)
metric(349,265,'11 / 11','TRIALS BETTER THAN BASELINE',265)
metric(654,265,'240 min','EACH TRIAL',265)
multiline(54,217,['Not an ML R² or field validation result: this measures policy performance in our event simulator.',
                   'For fairness, compared methods see identical equipment constraints and seeded travel variation.',
                   'The full per-seed CSV, policy weights and scripts are included in the repository.'],12,29)
foot(6)
#7
start('WHAT-IF STUDIO','Break it. Recover. Compare.','Same dispatcher policy and baseline under each precisely defined scenario.')
rows=[('Shovel outage',DATA['heldout_seed_experiments']['shovel_outage']['mean_change_pct'],'Suspend a shovel for 65 minutes'),
 ('Road closure',DATA['heldout_seed_experiments']['road_closure']['mean_change_pct'],'Block one haul route at departure'),
 ('Reduced fleet',DATA['heldout_seed_experiments']['fleet_reduction']['mean_change_pct'],'Operate only 50 trucks')]
for i,(name,gain,detail) in enumerate(rows):
 y=328-i*93;box(50,y-29,862,79)
 text(70,y+19,name,16,WHITE,True);text(70,y-4,detail,11,SOFT)
 text(744,y+5,'+'+str(gain)+'%',17,GREEN,True)
text(54,65,'All numbers are mean paired simulated improvements vs closest-route dispatch on seeds 21–31.',10,SOFT)
foot(7)
#8
start('OPENEGIZ / DIGITAL TWINS','One stream, many views','Built against the original OpenEgiz template services.')
links=[('OreFlow Engine','Deterministic events'),('Mosquitto MQTT','Ditto commands'),('Eclipse Ditto','102 digital twins'),('Influx + Grafana','Telemetric history')]
for i,(a,b) in enumerate(links):
 x=50+i*227;box(x,252,211,111);text(x+12,317,a,13,CYAN,True);text(x+12,289,b,10,SOFT)
 if i<3:text(x+213,300,'→',14,CYAN,True)
multiline(59,204,['The UI reads the simulation API; a real Ditto readback button checks actual persisted state.',
                   'A verification tool checks live MQTT, Ditto run IDs, Influx records and Grafana health.',
                   'Full Docker integration remains UNVERIFIED in this authoring environment.'],12,27)
foot(8)
#9
start('INTERFACE / OPERATIONS','A control center built for decisions','Playback, per-truck selection, policies, disruptions, evidence and platform readback.')
img=ROOT/'team/oreflow/reports/ui_preview.png'
if img.exists():
 C.drawImage(ImageReader(str(img)),80,78,width=795,height=315,preserveAspectRatio=True,anchor='c',mask='auto')
else:box(60,88,840,300)
text(53,63,'Preview from a browser-backed interaction test; source map remains schematic.',10,SOFT)
foot(9)
#10
start('DELIVERY / VALIDATION','What is proven; what is not','We separate model tests, API/browser evidence and live-platform checks.')
box(50,186,420,192);text(69,341,'VERIFIED HERE',17,GREEN,True)
multiline(69,310,['Source equipment counts + road constraints',
                 '18 event-engine tests and deterministic benchmarks',
                 'Local HTTP checks and browser UI interactions',
                 'Real benchmark evidence in JSON/CSV'],11,31)
box(490,186,420,192);text(509,341,'REQUIRES JUDGE / DOCKER CHECK',15,GOLD,True)
multiline(509,310,['MQTT broker and 102 persisted Ditto twins',
                  'End-to-end telemetry in InfluxDB',
                  'Grafana query rendering in a live stack',
                  'Fresh Ubuntu clean-start build'],11,31)
text(55,118,'Demonstration: open live map → compare dispatch → break shovel → apply optimizer → verify Ditto.',13,CYAN,True)
text(55,87,'A working, defensible submission is more valuable than invented R² scores or unverified savings.',11,SOFT)
foot(10)
C.save();print(OUT)
