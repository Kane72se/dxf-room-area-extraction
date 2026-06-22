---
name: dxf-room-area-extraction
description: "从CAD导出的DXF文件中提取房间面积：墙线内面法(主)+轴线验证+射线校核，自动评审工作流。适用于变电站/建筑平面图。"
version: 2.3.0
tags: [dxf, room, area, extraction, cad, substation, floor-plan, validation, overlap, audit]
---

# DXF 房间面积提取

## 适用范围

从建筑/电力工程DXF文件中自动提取房间面积，带**3方法交叉验证 + 自动校核人**工作流。

**前提条件：**
- DXF文件（AutoCAD 2010+，AC1021+均可）
- ezdxf ≥ 1.4.4, shapely ≥ 2.1.2, openpyxl
- DXF中房间名在TEXT实体中（通常在"标注"或"PUB_TEXT"层）

## 参考脚本

本skill目录下附带了220-A2-5变电站的完整实现脚本，可直接作为模板使用：

```
scripts/final_v16_reference.py
```

包含以下完整功能：墙线内面法→楼梯扣除→风井扣除→L形房间→走廊45ah→走廊2 T字形→建筑面积对比。遇到新DXF图纸时，**优先参考这个脚本**调整参数后使用。

## 参考文档

- `references/110kV-case-studies.md` — 110kV变电站三层实战案例（B1/1F/2F），含墙缺口延伸、偏差分析、工程量统计。
- `references/dxf-text-search-onedrive.md` — DXF文本关键词搜索技术 + OneDrive dataless 文件处理。

---

## 面积验证体系（多源参照，总建筑面积降级为参考值）

### 总建筑面积的地位

**总建筑面积（图框标注值）降级为参考值之一，不再是"圣旨"。** 算法算出来是多少就是多少，不允许为了凑标注值而修改算法参数。

### 三源参照体系

| 参照源 | 获取方法 | 用途 | 可信度 |
|:---|:---|:---|:---|
| **A-图框标注** | DXF中搜索"总建筑面积"/"建筑面积"附近数字 | 粗校 | ★★★（设计值，可能含墙厚/不含阳台等口径差异） |
| **B-轴线网格推算** | 最远轴线（如①-⑬）×（A-G）轴距 × 层数 | 外包面积基准 | ★★★★（纯几何，不受标注错误影响） |
| **C-房间明细表** | 图纸中若有表格或TEXT列表 | 逐室核对 | ★★★★★（有则最优） |

### 偏差分级处置

```
算得总面积S  vs  三源参照T₁/T₂/T₃

偏差 = |S - median(T₁,T₂,T₃)| / median(T₁,T₂,T₃)

├─ < 3%     → ✅ 通过，在输出中标注"与参照值吻合"
├─ 3%~10%   → ⚠️ 预警，输出偏差原因分析（不修改算法）
└─ > 10%    → ❌ 深入追查（漏房间？墙厚口径不同？比例尺错误？）
```

### 已知反例库（每次计算前自动加载校验）

| 反例 | 校验规则 | 发现于 |
|:---|:---|:---|
| L形房间几何中心落在房间外 | 射线法从房间内多点采样（中心点+四角偏移点），不依赖单一中心点 | 220-A2-5 220kV GIS室 |
| 金属格栅误识别为墙体 | 过滤特定图层（如"格栅""格构""百叶"）和线型（DASHED/HIDDEN） | 散热器室外墙 |
| 双线墙间距硬编码240mm | 墙厚设为参数 `WALL_GAP_RANGE = (140, 280)`，自动检测，不写死 | 多项目通用 |
| 标注总建筑面积含墙厚 vs 算法算净面积 | 输出同时列出"净面积"和"含墙估算面积（净面积×1.08）"，两个口径 | 220-A2-5总体对比 |
| wall_bounds找不到墙时自动fallback到建筑边界 | 任何方向返回±1e9时返回None，由调用者处理 | 走廊2 T字形区域 |
| 楼梯间用STAIR线边界而非墙线 | 楼梯间边界用wall_bounds结果，向下一道水平墙扩展 | 楼梯2/3 |
| 风井标注为"通风井x-x"但只打印不扣除 | 先算风井polygon，然后从所在房间执行difference | 卫生间通风井 |
| **色块图墙线被色块盖住** | 先填色(alpha=0.30)，再画墙线(alpha=0.9,zorder=20)在上面 | 110kV 1F |
| **房间穿越墙** | 墙缺口<2m=柱缝不扩展；>2m仅缺口处延伸，不穿越完整墙段 | 110kV 1F |
| **上空房间计建面** | "上空"房间不计入建筑面积(GB/T 50353中庭按一层计) | 110kV 2F |
| **同名不连通不合并** | 同名房间仅在连通(无墙分隔)时合并，不连通则分开列 | 110kV 2F走廊 |
| **过滤器误杀房间名** | '2','3','上','下','110kV'等用精确匹配，不用substring | 110kV 1F |

### 输出审计留痕（每个房间可追溯）

最终输出 xlsx 必须包含以下列，不满足时不交付：

```
房间编号 | 房间名称 | 面积(m²) | 围合墙线 | 验证方法 | 是否扣除风井/楼梯
R-101    | 220kV GIS室 | 265.32  | A-WALL: (12400,85000)→... | wall_bounds | 扣楼梯2、3
R-102    | 卫生间     | 17.80   | A-WALL: (12600,83500)→... | wall_bounds | 扣通风井14.7m²
...
合计     |           | 3533.0  | 参照值: 3720(图框) 偏差: -5.0% | 轴线推算: 3780
```

**墙线坐标列格式：** `图层名: (x1,y1)→(x2,y2); 图层名: ...`
每道墙只记录起点终点，不记录中间点。

### 输出前自审清单

- [ ] 三源参照已获取（图框/轴线/明细表，有则必用）
- [ ] 偏差<3%或已给出偏差原因分析
- [ ] 已知反例库已加载校验（每次都过一遍）
- [ ] 每个房间面积可追溯到围合墙线
- [ ] 风井/楼梯已从所在房间扣除
- [ ] 不含墙厚（净面积）与含墙估算值分别标注
- [ ] 不使用总建筑面积"凑"算法结果
- [ ] 色块填充图墙线画在色块上面(zorder=20, alpha=0.9)
- [ ] 上空房间不计入建筑面积
- [ ] 同名不连通不合并

---

## 核心方法

### ⚠️ polygonize不适用于双线墙DXF

**重要已知限制：** 变电站/建筑DXF的墙线是**双线墙**（两根平行线，间距140-280mm表示一道墙），不是单线中心线。**切勿使用shapely.polygonize()直接处理墙线**——双线墙之间的缝隙（墙腔）面积6-7m²，polygonize只会找到这些墙腔，找不到房间：

```python
# ❌ 不会工作：polygonize找到的是墙腔，不是房间
polys = list(polygonize(wall_lines))  # 结果是6-7m²的小区域!
```

正确方法：使用**墙线内面法**（见下文），从房间文字位置向4个方向找最近的墙内面作为边界。

### 墙线内面法 (wall_bounds) — 关键实现规则

⚠️ **当任何方向找不到墙时，必须返回None，不能fallback到建筑边界！**

```python
# ✅ 正确：找不到墙就返回None
if any(v in (-1e9, 1e9) for v in b.values()):
    return None  # 让调用者处理，而不是自动扩到建筑轮廓

# ❌ 错误：fallback到建筑边界会导致墙线不全的房间面积被大幅高估
if left_x is None: left_x = BX1  # 错误！找不到左墙应返回None
```

**为什么不能fallback：** 变电站房间之间有很多短墙段（柱子、设备基础边缘），wall_bounds可能找不到某个方向的墙。如果自动fallback到建筑边界，房间会扩展到整个建筑宽度——比如一个6m宽的房间被扩成100m。

### 0图层建筑轮廓必须加入墙线集

```python
# ✅ 正确：建筑轮廓LWPOLYLINE的每一条边都加入wall_shapes
for e in msp.query('*[layer=="0"]'):
    if e.dxftype() == "LWPOLYLINE" and e.closed:
        pts = list(e.vertices())
        coords = [(v[0], v[1]) for v in pts]
        for i in range(len(coords)-1):
            x1, y1 = coords[i]
            x2, y2 = coords[i+1]
            if math.sqrt((x2-x1)**2 + (y2-y1)**2) > 100:
                wall_shapes.append(LineString([(x1,y1), (x2,y2)]))

# ❌ 错误：只读取建筑轮廓用于裁剪，不加入墙线
# OpenCode犯了此错误，导致靠近建筑边界的房间找不到外墙边界
```

建筑轮廓的边就是实际的建筑外墙线。如果只用于裁剪而不加入墙线，6号电抗器室、散热器平台等靠外墙的房间会找不到正确的外墙边界。

```python
def wall_bounds(px, py):
    b = {"L": -1e9, "R": 1e9, "B": -1e9, "T": 1e9}
    pt = Point(px, py)
    for w in wall_shapes:
        c = list(w.coords); d = pt.distance(w)
        if d > 50000: continue
        if abs(c[0][1]-c[-1][1]) < 50:  # 水平墙
            wy = (c[0][1]+c[-1][1])/2
            x1,x2 = min(c[0][0],c[-1][0]), max(c[0][0],c[-1][0])
            if x1-800 <= px <= x2+800:  # ±800mm容差
                if wy > py and wy < b["T"]: b["T"] = wy
                if wy < py and wy > b["B"]: b["B"] = wy
        if abs(c[0][0]-c[-1][0]) < 50:  # 垂直墙
            wx = (c[0][0]+c[-1][0])/2
            y1,y2 = min(c[0][1],c[-1][1]), max(c[0][1],c[-1][1])
            if y1-800 <= py <= y2+800:
                if wx > px and wx < b["R"]: b["R"] = wx
                if wx < px and wx > b["L"]: b["L"] = wx
    if any(v in (-1e9, 1e9) for v in b.values()): return None
    return b
```

### 墙线缺口延伸（110kV实战新增）

当一面墙覆盖<80%且单段缺口>2.0m时，仅在该缺口对应的X/Y范围内延伸房间边界，不做全宽扩展：

```python
def find_gaps(wall_lines, y, x_start, x_end):
    """在y位置找[x_start,x_end]内>500mm的缺口"""
    segs = sorted([(min(w['x1'],w['x2']),max(w['x1'],w['x2']))
                   for w in wall_lines if abs(w['y2']-w['y1'])<abs(w['x2']-w['x1'])
                   and abs((w['y1']+w['y2'])/2-y)<100])
    gaps=[]; cur=x_start
    for x1,x2 in segs:
        if x1>cur+500: gaps.append((cur,min(x1,x_end)))
        cur=max(cur,x2)
    if x_end-cur>500: gaps.append((cur,x_end))
    return gaps

# >2m的缺口才扩展(区分柱缝vs门洞)
for gx1,gx2 in find_gaps(wall_lines, b["T"], b["L"], b["R"]):
    if (gx2-gx1)/1000<2.0: continue  # 柱缝
    b2 = wb((gx1+gx2)/2, b["T"]+2000)
    if b2:
        ext = box(gx1, b["T"], gx2, b2["T"]).intersection(building)
        if not any(ext.contains(Point(nx,ny)) for n,(nx,ny) in texts):  # 不吞没其他房间
            room = unary_union([room, ext])
```

## 走廊处理

### 走廊45ah：全高窄走廊，使用wall_bounds

走廊45ah是④⑤轴间(A-H全高)的2.83m宽窄走廊，两侧有连续垂直墙。直接用wall_bounds后扣房间：

```python
b = wall_bounds(-600018, -1459270)
corr = box(b["L"], b["B"], b["R"], b["T"]).intersection(building_poly)
for name in room_polys:
    for rp in room_polys[name]:
        if corr.intersects(rp) and corr.intersection(rp).area > 50000:
            corr = corr.difference(rp)
```

⚠️ **不要限制到A-B轴！** "45ah"=④⑤轴和A-H轴，Y范围应该用wall_bounds的完整结果（建筑底部到顶部~40m），不是A-B之间的7m。

### 走廊2(11-13/A-E)：T字形，用建筑-房间差集法

当走廊区域**无水平墙跨越搜索点X范围**时，wall_bounds会返回None。改用per-zone计算：

```python
zone = box(-540000, -1461240, -525512, -1434340)
blank = building_poly.intersection(zone).difference(all_room_union)
```

**横臂(3040mm高)：** 紧贴220kV二次设备小室底部(-1439660)向下3040mm。
横臂X范围应该从**左侧房间墙线到右侧房间墙线**，确保两端到墙：
```python
h_zone = box(-543432, h_bot, -525592, h_top)  # 左=220kV小室左，右=卫生间右
```

**纵臂：** 左缘=站用变室右缘(-535092)，右缘=接地变室左缘(-531932)。宽度以实际墙间距为准，可大于用户指定的值。

## 图纸面积对比

最终图表标题格式：
```
建筑面积(GB/T 50353): 3720m²  本次计算(含散热平台): 3973.8m²  扣除散热平台后: 3533.0m²
```

## 楼梯间边界扩展（AI agent常见错误）

### 楼梯2/3边界扩展的精确算法

⚠️ **楼梯间面积必须用wall_bounds结果（墙到墙全高），不能用STAIR线的范围做边界！** STAIR线只覆盖踏步区域，不覆盖楼梯间平台到四面墙的完整空间：

```python
# 楼梯2（中左，220kV GIS旁）上边界扩展：
# wall_bounds找到的上墙可能在楼梯中间（被横梁/短墙阻挡），
# 必须继续向上搜索下一道水平墙
if sname == "楼梯2":
    for wsh in wall_shapes:
        c = list(wsh.coords)
        if abs(c[0][1]-c[-1][1]) < 50:
            wy = (c[0][1]+c[-1][1])/2
            x1,x2 = min(c[0][0],c[-1][0]), max(c[0][0],c[-1][0])
            if x1-800 <= sx <= x2+800 and wy > sy2 and wy < sy2+5000:
                sy2 = wy  # 扩展到下一道水平墙
                break

# 楼梯3（中右）下边界扩展：
# 同理，向下扩展到下一道水平墙
if sname == "楼梯3":
    for wsh in wall_shapes:
        c = list(wsh.coords)
        if abs(c[0][1]-c[-1][1]) < 50:
            wy = (c[0][1]+c[-1][1])/2
            x1,x2 = min(c[0][0],c[-1][0]), max(c[0][0],c[-1][0])
            if x1-800 <= sx <= x2+800 and wy < sy1 and wy > sy1-5000:
                sy1 = wy  # 扩展到下一道水平墙
                break

# ❌ 常见AI agent错误（如OpenCode）：用STAIR线最小Y作底边
# stair_area = rect_area(lx, rx, ty, sy1)  # sy1=STAIR线最小Y=-1426290
# 正确底边应是 wall_bounds 找到的下墙 Y=-1427660
# 后果：楼梯2面积误差 14.8m² vs 正确值23.6m²
```

### 0图层建筑轮廓必须加入墙线集

```python
# ✅ 正确：建筑轮廓LWPOLYLINE的每一条边都加入wall_shapes
for e in msp.query('*[layer=="0"]'):
    if e.dxftype() == "LWPOLYLINE" and e.closed:
        pts = list(e.vertices())
        for i in range(len(pts)-1):
            x1,y1 = pts[i][0],pts[i][1]
            x2,y2 = pts[i+1][0],pts[i+1][1]
            if math.sqrt((x2-x1)**2+(y2-y1)**2) > 100:
                wall_shapes.append(LineString([(x1,y1),(x2,y2)]))

# ❌ 常见AI agent错误：只读取建筑轮廓用于裁剪，不加入墙线
# 后果：靠外墙的房间（6号电抗器室、散热器平台）找不到正确的外墙边界
```

### 风井扣除必须实际执行difference

```python
# ✅ 正确：先计算风井多边形，然后从所在房间扣减
for name in list(room_polys.keys()):
    new_polys = []
    for poly in room_polys[name]:
        for well in well_polygons:
            if poly.intersects(well):
                if well.within(poly) or poly.contains(well):
                    poly = poly.difference(well)
        if poly.area > 1e6:
            new_polys.append(poly)
    room_polys[name] = new_polys

# ❌ 常见AI agent错误：只print风井面积，不执行difference
# 后果：卫生间17.8m²未扣通风井14.7m²
```

### 文字排除用前缀匹配非精确匹配

```python
# ✅ 正确：前缀匹配
EXCLUDE_PREFIX = {'排风井', '进风井', '通风井', '冷媒管井', '空调外机基础', '钢平台'}
if any(name.startswith(p) for p in EXCLUDE_PREFIX): continue

# ❌ 常见AI agent错误：用精确匹配 t in EXCLUDE_PREFIX
# 后果：DXF中带空格/后缀变体的文字漏过滤
```

⚠️ **短字符串过滤必须用精确匹配：** '2','3','上','下','110kV'等用 `t in EXCLUDE_EXACT`，不用substring。否则'上'会误杀"上空"，'3'误杀"#3主变室"。

### CJK字体必须配置

```python
# ✅ 必加，否则图上中文全变方块
plt.rcParams['font.sans-serif'] = ['Heiti TC', 'STHeiti', 'PingFang HK']
plt.rcParams['axes.unicode_minus'] = False
```

### 色块填充图绘制顺序

墙线/轴网必须画在色块上面(zorder更高)，否则被色块盖住：

```python
# Layer 1: 色块(底层,alpha=0.30,zorder=1)
ax.fill(xs, ys, alpha=0.30, color=c, zorder=1)
# Layer 2: 轴网虚线(zorder=10), 窗户(zorder=15)
ax.axvline(x=x, color='#888', lw=0.5, alpha=0.5, zorder=10)
# Layer 3: 墙线(前景,几乎不透明,zorder=20)
ax.plot([x1,x2],[y1,y2], color='#1a1a1a', lw=2.0, alpha=0.9, zorder=20)
# Layer 4: 柱/防火门(zorder=25-30)
ax.plot(x, y, 'D', color='#e67e22', ms=8, alpha=0.9, zorder=30)
```

1. ✅ 所有房间在外墙范围内
2. ✅ 楼梯间从房间中扣除重叠面积（如220kV GIS室扣楼梯2和3）
3. ✅ 风井面积从所在房间扣除
4. ✅ 走廊45ah全高（不限制到B轴）
5. ✅ 走廊2T字形横臂两端到墙、纵臂不重叠房间
6. ✅ 总面积含建筑面积对比
7. ✅ 墙线画在色块上面（zorder=20）
8. ✅ 上空房间不计入建筑面积
9. ✅ 同名不连通不合并
