import sys, struct, json
sys.path.insert(0, 'tools')
from index6 import resolve, build, table
from transplant import CHASSIS

idx = build()
k, v = resolve(idx, 'Nissan 370Z')
p = v['physics']
cpb = open('gdb-6.0.0k/CarPhysics.gdb', 'rb').read()
d0 = next(x for x in table(cpb)[1] if x['off'] == p['off'])
tuned = open('tuned-carswap/CarPhysics.gdb', 'rb').read()
d = next(x for x in table(tuned)[1] if x['key'] == d0['key'])
rec = tuned[d['off']:d['off'] + d['size']]

def f(i): return struct.unpack_from('<f', rec, i * 4)[0]

arch = json.load(open(r'03-车辆档案/carphysics-428B-cohort.json', encoding='utf-8'))
named = {a: b for a, b in arch.items() if b.get('name') == 'Nissan 370Z'}
biz = list(named.values())[0].get('business') if named else None

print('———— 极速与动力 ————')
print(f'物理极速      {f(22):.1f} / {f(23):.1f}   (低/满级，面板极速 {biz["ts_hi"] if biz else "?"} 对应满级档)')
print(f'加速          {f(72):.3f} / {f(73):.3f}   (引擎推力系数，越大越猛)')
print()
print('———— 转向 ————')
print(f'转向锐度(主)  {f(19):.0f} / {f(21):.0f}   (几何半径主控，62000柔/80000锐/98900顶格)')
print(f'低速转向角    {f(14):.0f} / {f(16):.0f}   (随锐度同比)')
print(f'操控 idx76    {f(76):.3f} / {f(77):.3f}   (漂移/过弯，全库最高1.00塞纳)')
print()
print('———— 抓地与抬轮 ————')
print(f'抓地 tyre     {f(78):.4f} / {f(79):.4f}')
print(f'下压力        {f(30):.0f} / {f(31):.0f}   (抬轮总开关：杰AB200/P1 550/恶魔16 1150)')
print(f'压缩/回弹阻尼 {f(99):.2f} / {f(100):.2f}   (悬挂动作快慢)')
print()
tiers = [('单喷', 32), ('橙喷', 40), ('蓝喷(完美)', 48), ('紫喷', 56)]
print('———— 氮气四档（满级端）————')
for nm, b in tiers:
    A, dr, sp, keep = f(b + 1), f(b + 3), f(b + 5), f(b + 7)
    print(f'{nm:<10} 加成 {sp:6.3f} km/h(HUD≈×2.15)   消耗 {dr:6.2f}(时长∝1/它)   维持 {keep:7.0f}(抗掉速)   A {A:.3f}')
print()
chb = open('tuned-carswap/CarChassis.gdb', 'rb').read()
ch = resolve(idx, 'Nissan 370Z')[1]['chassis']
d2 = next(x for x in table(chb)[1] if x['off'] == ch['off'])
crec = chb[d2['off']:d2['off'] + d2['size']]
g = {l: struct.unpack_from('<f', crec, i * 4)[0] for i, l in CHASSIS}
print('———— 底盘几何 ————')
print(f'质量 {g["质量kg"]:.0f} kg   轴距 {g["轴距"]:.2f} m   前轮距 {g["前轮距"]:.2f} / 后轮距 {g["后轮距"]:.2f} m')
print(f'轮径 前 {g["前轮半径"]:.3f} / 后 {g["后轮半径"]:.3f} m   重心高 {g["重心高"]:.3f} m')
s16, s17, s18, s19 = (struct.unpack_from('<f', crec, i * 4)[0] for i in (16, 17, 18, 19))
print(f'悬挂行程 前 {s16:.3f}/{s17:.3f} m   后 {s18:.3f}/{s19:.3f} m   (参照 P1贴地0.010 / 718 Cayman 0.080-0.100)')
wi = f(79) * abs(g["重心高"]) / g["前轮距"]
print(f'抬轮指数(几何) {wi:.4f}   (AMG One 原厂 0.0642)')
print()
if biz:
    print(f'———— 面板（business，未动）————')
    print(f"rank {biz['rank_lo']}/{biz['rank_hi']}   极速面板 {biz['ts_lo']}/{biz['ts_hi']}")
