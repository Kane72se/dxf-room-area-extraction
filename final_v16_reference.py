"""
v16: 走廊2用building-rooms方法 + T形过滤
220-A2-5 变电站 DXF 房间面积提取

从CAD导出的DXF文件中自动提取变电站房间净面积。
方法：墙线内面法(wall_bounds) + 轴线验证 + 射线校核
"""
import ezdxf, math, re
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Heiti TC', 'STHeiti', 'PingFang HK']
plt.rcParams['axes.unicode_minus'] = False

dxf_path = "/Users/kane72se/Library/CloudStorage/OneDrive-Personal/ai/220-A2-5 T01-3.dxf"
doc = ezdxf.readfile(dxf_path); msp = doc.modelspace()

wall_shapes = []
for layer in ["WALL","WALL1","WALL2"]:
    for l in msp.query(f'LINE[layer=="{layer}"]'):
        wall_shapes.append(LineString([(l.dxf.start.x,l.dxf.start.y),(l.dxf.end.x,l.dxf.end.y)]))
for p in msp.query('LWPOLYLINE[layer=="JZX_ViewLine"]'):
    pts=list(p.vertices())
    for i in range(len(pts)-1):
        x1,y1=pts[i][0],pts[i][1]; x2,y2=pts[i+1][0],pts[i+1][1]
        if math.sqrt((x2-x1)**2+(y2-y1)**2)>50: wall_shapes.append(LineString([(x1,y1),(x2,y2)]))
for e in msp.query('*[layer=="0"]'):
    if e.dxftype()=="LWPOLYLINE" and e.closed:
        pts=list(e.vertices()); coords=[(v[0],v[1]) for v in pts]
        for i in range(len(coords)-1):
            if math.sqrt((coords[i][0]-coords[i+1][0])**2+(coords[i][1]-coords[i+1][1])**2)>100:
                wall_shapes.append(LineString([coords[i],coords[i+1]]))

def wall_bounds(px,py):
    """从房间内一点向四方向找最近的墙内面"""
    b={"L":-1e9,"R":1e9,"B":-1e9,"T":1e9}; pt=Point(px,py)
    for w in wall_shapes:
        c=list(w.coords); d=pt.distance(w)
        if d>50000: continue
        if abs(c[0][1]-c[-1][1])<50:  # 水平墙
            wy=(c[0][1]+c[-1][1])/2; x1,x2=min(c[0][0],c[-1][0]),max(c[0][0],c[-1][0])
            if x1-800<=px<=x2+800:
                if wy>py and wy<b["T"]: b["T"]=wy
                if wy<py and wy>b["B"]: b["B"]=wy
        if abs(c[0][0]-c[-1][0])<50:  # 垂直墙
            wx=(c[0][0]+c[-1][0])/2; y1,y2=min(c[0][1],c[-1][1]),max(c[0][1],c[-1][1])
            if y1-800<=py<=y2+800:
                if wx>px and wx<b["R"]: b["R"]=wx
                if wx<px and wx>b["L"]: b["L"]=wx
    if any(v in (-1e9,1e9) for v in b.values()): return None
    return b

building_poly=None
for e in msp.query('*[layer=="0"]'):
    if e.dxftype()=="LWPOLYLINE" and e.closed:
        pts=list(e.vertices())
        if len(pts)==18: building_poly=Polygon([(v[0],v[1]) for v in pts])

EXCLUDE_EXACT={'FM','甲','乙','丙','上','下'}
EXCLUDE_PREFIX={'排风井','进风井','通风井','冷媒管井','空调外机基础','钢平台'}
text_items=[]
for t in msp.query('TEXT'):
    name=t.dxf.text.strip()
    if not name: continue
    if name in EXCLUDE_EXACT: continue
    if any(name.startswith(p) for p in EXCLUDE_PREFIX): continue
    if re.match(r'^\d+$',name): continue
    n2="卫生间" if name=="WC" else name
    if name=="楼梯": n2="楼梯间"
    if any(k in n2 for k in ['室','间','房','厅','平台']) or n2 in ["卫生间","楼梯间"]:
        text_items.append((n2,t.dxf.insert.x,t.dxf.insert.y))

seen=set(); text_rooms={}
for n,x,y in text_items:
    k=(n,round(x/100),round(y/100))
    if k not in seen: seen.add(k)
    text_rooms.setdefault(n,[]).append((x,y))

stair_b={
    "楼梯1":{"x1":-610812,"x2":-606652,"y1":-1461490,"y2":-1459520},
    "楼梯2":{"x1":-598432,"x2":-595292,"y1":-1426290,"y2":-1423200},
    "楼梯3":{"x1":-520712,"x2":-518762,"y1":-1425950,"y2":-1422830},
    "楼梯4":{"x1":-523812,"x2":-520842,"y1":-1437146,"y2":-1434318},
}
room_polys={}; stair_polys=[]

for name,positions in text_rooms.items():
    if "散热器" in name or name=="楼梯间": continue
    for px,py in positions:
        b=wall_bounds(px,py)
        if not b: continue
        if name=="110kV GIS室":
            poly=unary_union([box(b["L"],b["B"],b["R"],b["T"]), box(-605232,-1461490,b["R"],b["B"])])
        elif name=="消防泵控制室":
            poly=unary_union([box(b["L"],b["B"],b["R"],b["T"]), box(-521832,-1439990,b["R"],b["B"])])
        else:
            if name=="2号接地变室": b["L"]=-531932
            poly=box(b["L"],b["B"],b["R"],b["T"])
        if building_poly: poly=poly.intersection(building_poly)
        if poly.area>1e6: room_polys.setdefault(name,[]).append(poly)

# 楼梯处理
stair_p=[(-612087,-1460116),(-597177,-1427175),(-520311,-1427413),(-520226,-1435640)]
for idx,(sx,sy) in enumerate(stair_p):
    sb=stair_b[f"楼梯{idx+1}"]
    b=wall_bounds(sx,sy)
    if b:
        sx1=min(b["L"],sb["x1"]-200); sx2=max(b["R"],sb["x2"]+200)
        sy1=min(b["B"],sb["y1"]-200); sy2=max(b["T"],sb["y2"]+200)
    else: sx1,sx2,sy1,sy2=sb["x1"]-200,sb["x2"]+200,sb["y1"]-200,sb["y2"]+200
    if idx==1:  # 楼梯2向上扩展
        for wsh in wall_shapes:
            c=list(wsh.coords)
            if abs(c[0][1]-c[-1][1])<50:
                wy=(c[0][1]+c[-1][1])/2; x1,x2=min(c[0][0],c[-1][0]),max(c[0][0],c[-1][0])
                if x1-800<=sx<=x2+800 and wy>sy2 and wy<sy2+5000: sy2=wy; break
    if idx==2:  # 楼梯3向下扩展
        for wsh in wall_shapes:
            c=list(wsh.coords)
            if abs(c[0][1]-c[-1][1])<50:
                wy=(c[0][1]+c[-1][1])/2; x1,x2=min(c[0][0],c[-1][0]),max(c[0][0],c[-1][0])
                if x1-800<=sx<=x2+800 and wy<sy1 and wy>sy1-5000: sy1=wy; break
    poly=box(sx1,sy1,sx2,sy2)
    if building_poly and poly.intersects(building_poly): poly=poly.intersection(building_poly)
    if poly.area>1e6: stair_polys.append(poly)

# 从房间扣楼梯
for name in list(room_polys.keys()):
    new_polys=[]
    for poly in room_polys[name]:
        for sp in stair_polys:
            if poly.intersects(sp) and poly.intersection(sp).area>100000: poly=poly.difference(sp)
        if poly.area>1e6: new_polys.append(poly)
    room_polys[name]=new_polys
for sp in stair_polys: room_polys.setdefault("楼梯间",[]).append(sp)

# 散热平台
for name,positions in text_rooms.items():
    if "主变散热器" in name:
        for px,py in positions:
            b=wall_bounds(px,py)
            if b:
                lw,rw=b["L"],b["R"]; bottom=-1e9
                for wsh in wall_shapes:
                    c=list(wsh.coords)
                    if abs(c[0][1]-c[-1][1])<50:
                        wy=(c[0][1]+c[-1][1])/2; x1,x2=min(c[0][0],c[-1][0]),max(c[0][0],c[-1][0])
                        if x1-500<=px<=x2+500 and wy<py and wy>bottom: bottom=wy
                if bottom==-1e9: bottom=b["B"]
                poly=box(lw,bottom,b["R"],b["T"])
                if building_poly: poly=poly.intersection(building_poly)
                if poly.area>1e6: room_polys.setdefault(name,[]).append(poly)

rc=[-1424434,-1430934,-1437434,-1443934,-1450482,-1457684]
wy2=[round((rc[i]+rc[i+1])/2) for i in range(5)]
for name,positions in text_rooms.items():
    if "散热器平台" in name and "主变" not in name:
        for idx,(px,py) in enumerate(positions):
            if idx<6:
                y_t=-1420990 if idx==0 else wy2[idx-1]
                y_b=-1461770 if idx==5 else wy2[idx]
                b=wall_bounds(px,py)
                if b:
                    poly=box(b["L"],y_b,b["R"],y_t)
                    if building_poly: poly=poly.intersection(building_poly)
                    if poly.area>1e6: room_polys.setdefault(name,[]).append(poly)

# 走廊(45ah)
b=wall_bounds(-600018,-1459270)
if b:
    c1=box(b["L"],b["B"],b["R"],b["T"]).intersection(building_poly)
    for name in list(room_polys.keys()):
        for rp in room_polys[name]:
            if c1.intersects(rp) and c1.intersection(rp).area>50000:
                c1=c1.difference(rp)
                if hasattr(c1,'geoms'):
                    gs=list(c1.geoms); c1=max(gs,key=lambda g:g.area) if gs else c1
    if c1.area>500000: room_polys.setdefault("走廊(45ah)",[]).append(c1)

# 走廊2(11-13/A-E): T字形
h_top=-1439660; h_bot=h_top-3040; zone2=box(-543432-200,-1461770-200,-525592+200,-1434340+200)
building_in=building_poly.intersection(zone2)
all_union=None
for name in list(room_polys.keys()):
    for poly in room_polys[name]:
        if poly.intersects(zone2):
            if all_union is None: all_union=poly
            else: all_union=unary_union([all_union,poly])
if building_in and all_union:
    blank=building_in.difference(all_union)
    h_zone=box(-543432,h_bot,-525592,h_top)
    v_zone=box(-535092,-1461770,-531932,h_bot)
    for p,label in [(h_zone,"横臂"),(v_zone,"纵臂")]:
        corr=blank.intersection(p)
        if hasattr(corr,'geoms'):
            for cp in corr.geoms:
                if cp.area>500000: room_polys.setdefault("走廊(11-13/A-E)",[]).append(cp)
        elif corr.area>500000: room_polys.setdefault("走廊(11-13/A-E)",[]).append(corr)

# 输出
total=0; cnt=0
for name in sorted(room_polys.keys()):
    for poly in room_polys[name]:
        a=round(poly.area/1e6,1); total+=poly.area; cnt+=1
        print(f"  {name:30s} {a:6.1f}m²")
platform_total=95.3*3+25.4+24.7+24.7+24.8+26.1+29.2
excl=total/1e6-platform_total
print(f"\n房间:{len(room_polys)} 色块:{cnt} 总面积:{total/1e6:.1f}m² 建面3720m² 差:{total/1e6-3720:.1f}m²")
print(f"扣除散热平台: {excl:.1f}m²")

# 绘图
fig,ax=plt.subplots(figsize=(24,18))
ax.set_facecolor('#f5f5f5')
colors=['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22',
        '#34495e','#e91e63','#00bcd4','#ff5722','#795548','#607d8b','#ffc107',
        '#8bc34a','#ff9800','#673ab7','#009688','#cddc39','#03a9f4','#d32f2f','#1976d2']
idx=0
for name in sorted(room_polys.keys()):
    for poly in room_polys[name]:
        a=round(poly.area/1e6,1)
        geoms=list(poly.geoms) if hasattr(poly,'geoms') else [poly]
        for sp in geoms:
            if sp.exterior and sp.area>50000:
                c=colors[idx%len(colors)]
                xs,ys=sp.exterior.xy; ax.fill(xs,ys,alpha=0.45,color=c); ax.plot(xs,ys,color=c,lw=1.5)
                cx,cy=sp.centroid.x,sp.centroid.y
                ax.text(cx,cy,f"{name}\n{a}m²",fontsize=7,ha='center',va='center',fontweight='bold')
                idx+=1
if building_poly:
    xs,ys=building_poly.exterior.xy; ax.plot(xs,ys,'k-',lw=2,label='建筑轮廓')
ax.set_aspect('equal')
ax.set_title(f'220-A2-5 变电站\n建筑面积(GB/T 50353): 3720m²  本次计算(含散热平台): {total/1e6:.1f}m²  扣除散热平台后: {excl:.1f}m²',fontsize=13)
fig.savefig('/tmp/dxf_final_v16.png',dpi=200,bbox_inches='tight')
print("保存: /tmp/dxf_final_v16.png")
