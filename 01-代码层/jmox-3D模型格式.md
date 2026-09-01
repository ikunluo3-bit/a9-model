# jmox · A9 车辆 3D 模型格式（已破）

> **2026-08-27 重大更新：二进制布局已由 NevadaSprint 工程破解（读取方向 1:1 验收），
> 本文档 M1 探针补全帧前缀/摘要结论。写入器规格见文末「M1 探针结论」。**
> 交叉引用：`C:\NevadaSprint\docs\reports\A-车辆资产.md`（帧表/索引流/尺度裁判）、
> `tools/extract/`（解码器全家）、`a9模型/tools/jmox_probe.py` / `jmox_probe2.py`（本轮探针）。

## 0. 容器与帧结构（实测钉死）

```
9B 魔数 \x89jmox\r\n\x01\n
未压缩记录表（0..5231）：[u32 名长][xor(0xAB) 名字][变长负载] × 80 条
    前 55 条 = 节点（字母序，含位置 f32、镜像缩放 ±1）
    后 25 条 = 材质/批次名（carpaint、glass、tires、details、LOD_*...）
之后 73 个 zstd 帧，每帧前缀 24B：
    数据帧  [14B 载荷][1B 类型][0x02][cs u32][ds u32]
    绘制帧  [X u32][05][Y u32][07][Z u32][块数k][02][cs u32][ds u32] + k×90B 块
            X=Y=Z=顶点段基址（X/4 = 索引锚点），90B 块 = AABB×2 + 4×4 矩阵 + u16 节点号
大帧类型字节：00 位置 / 01,02,03,0b,0c,0d,13,14（未知流）/ 15 索引
```

## 1. 大帧内容（女武神样本，127,553 顶点）

| 帧 | 类型 | ds | 内容 |
|---|---:|---:|---|
| [0] | 00 | 1,020,424 | 位置 snorm16 x,y,z + w=0x7FFF，÷8192，**载荷 14B 全零（无摘要）** |
| [4] | 0b | 510,212 | UV 2×u16 ÷8192，[0,1] |
| [7] | 13 | 510,212 | 每顶点 u32 骨骼号（LOD0 全 0） |
| [8] | 14 | 510,212 | 每顶点 4×u8 权重 (255,0,0,0) |
| [9] | 15 | 896,478 | 索引 u16 ×448,239，**段内相对索引 + 连续基址铺贴**（171 段，DP 闭合）；前缀 14B 结构化计数 |
| [10..72] | — | 90×k | 63 个绘制帧 |

## 2. M1 探针结论（2026-08-27，jmox_probe2.py）

1. ~~摘要~~ **已破案（M2 装机实测）**：所谓"14B 摘要"是**前缀宽度读错**——
   数据帧真实前缀只有 **10B**（`[type][02][cs][ds]`），多出的 14B 是
   上一帧 zstd 流的尾巴，被误读成摘要、还曾被拼进重打包文件 → 闪退。
   帧间 gap 实测 −14B 钉死宽度。绘制帧前缀确为 24B（`[X][05][Y][07][Z][k][02][cs][ds]`）。
   cs/ds 相对 magic 的偏移（−8/−4）与宽度无关——这就是当初双校验测不出宽度的原因。
2. **[1]（31,692×8B）[2]（18,478×8B）[5][6]**：语义仍未定；不阻塞位置级写入。
3. **绘制帧之间的节间裸数据**：AABB 浮点数组（center/half 各 3×f32），每帧
   gap 160~174B，与块数 k 无关——绘制段结构另有一层，未解。
4. 帧扫描注意：压缩流内存在伪 zstd 魔数，必须用「尾部 ds u32 == 解压长度」过滤
   （`jmox_writer3.py` 的 locate_data_frames 可复用）。

## 3. 写入器（M2 定稿：外科手术式，jmox_writer3.py）

**头部位移帧流替换**：
- 定位 10 个数据帧（类型 00/01/02/03/0b/0c/0d/13/14/15）
- 只替换目标帧的 zstd 流 + 前缀 cs，**其余字节原样**（含全部绘制帧）
- 引擎按 cs 链顺序解析（头部记录表无流偏移）——**但实测新流尺寸必须与
  原流分毫不差**，否则加载该模型时卡死闪退（尺寸漂移疑似破坏后续帧定位）
- **精确尺寸技术**：内容语义不变（位置 ±0.12mm 抖动）+ 压缩等级固定 L19
  （帧头与原流逐字节同参数），二分抖动数量 k、边界种子轰炸命中精确 cs。
  实战：AMG 帧[0] 目标 483,393B，k=7,207 抖动 + seed=20 命中
  （`hit_content.bin`）。zstd 可跳过帧垫片**不可用**（引擎拒收，启动即崩）。

**M2 上机记录**：
| 版本 | 结果 |
|---|---|
| 手搓 zip（无 manifest 同步）| 开屏闪退 ×2 —— 是 manifest 尺寸没同步，与模型无关（见 README 陷阱 10）|
| T2v3 外科压扁（尺寸 −20KB）| 进游戏正常，**加载 AMG 即卡死** → 尺寸漂移实锤 |
| 垫片等长版 | **启动即崩** → 可跳过帧被引擎拒收 |
| 精确等长版（squash-exact）| 待实测 |

## 4. SU7 投影路线（M3 预定）

AMG 拓扑（索引/绘制块/节点/材质）整体保留，只重写 [0] 位置 + [4] UV：
SU7 表面（926k 顶点，减面后）投影到 AMG 的 165,760 顶点上。
材质槽名必须对齐 AMG 记录表（powderFactor 断言教训）。
轮子网格按位置映射到 `bone_wheel_*` 节点。

---

# M3 实战记录（2026-08-27 深夜）

## 5. 投影版已上机渲染成功

`su7_parse_glb.py` + `su7_project.py`：
- SU7 glb（Sketchfab，463,119 顶点/36 材质）解析 → 点云 ×100 还原真实尺寸
- 轴映射 A9X=glbX, A9Y=glbZ, A9Z=glbY，**包围盒非均匀贴合** AMG 空间
  （AMG: X ±0.913 / Y ±2.0 / Z ±0.659，Z=上、Y=车长、Z=0 在车身中平面）
- cKDTree 最近点投影 165,760 AMG 顶点（中位距离 4.5cm）
- **投影版已在车主手机渲染成功**（无崩溃，车形变为 SU7）——
  位置帧管线正式闭环。遗留观感问题：
  1. 贴图未改（AMG 的 UV+材质+贴图，即"AMG 涂装 SU7 车身"）
  2. 形状细节受限——AMG 拓扑长不出 SU7 独有几何（投影吸附的本质限制），
     车主观察"像被删减"，正确
- 压扁演示的两个坑已修：缩放要**以 zmin（轮胎接地面）为锚点**（以 Z=0 为中心
  压会悬空 26cm）；精确尺寸技术（抖动二分+种子轰炸）对 k 非单调
  （混合熵中段鼓包），轰炸网要撒宽（k±50 × 12 种子）

## 6. 工具链（本目录 a9模型/tools/）

| 工具 | 用途 |
|---|---|
| `jmox_extract_apk.py` | 从 base APK 按 manifest 抽车模（NC/NX 直读） |
| `jmox_probe.py` / `jmox_probe2.py` | 帧表/前缀/宽度探针 |
| `jmox_writer3.py` | 外科写入器（locate_data_frames + splice，**最终版**） |
| `jmox_writer.py` / `jmox_writer2.py` | 中间版，留作考古 |
| `su7_parse_glb.py` | glb → 世界空间点云（npz） |
| `su7_project.py` | 投影 + 精确尺寸 + 拼接（一站式） |
| `jmox_xref.py` | .so 字符串 xref 扫描（ADRP+ADD 对） |

注意：**车模文件名 ≠ 车名**。AMG One 的模型在
`/gfx3D/cars/UPD44/models/Mercedes_AMG_One_car.json`（UPD44 版本目录，
asset 397F9F1DEA08911B），manifest 里按 AMG_One 搜才能找到。

## 7. 加载器逆向（进行中，下一步的关键路径）

**目标**：完整模型写入需要自建索引流+绘制块，必须逆出引擎绘制段语义
（每个绘制块画哪些索引、范围从哪来）。

已定位（6.0.0k 的 `libAsphalt9.so`，从 base APK 抽取，**别用 5.9.0l 的**）：
- `powderFactor` 字符串 0x66ed8dc，引用代码 0x36e2078 —— 与 06 文档吻合，
  **xref 扫描器已用该校验点验证正确**（jmox_xref.py，ADRP+ADD 对，窗口 8 条）
- **JModelParser**：`"Unsupported jmodel version {} [min: {}, max: {}]"` @0x675ea2b，
  引用 4 处：**0x4cb578c / 0x4cb58f4 / 0x4cb5aa4 / 0x4cb7fb0**，
  版本常量 **min=0xb(11) max=0xd(13)**（0x4cb5788/0x4cb5790 的 mov w8/w9）
  —— 解析器函数区在 0x4cb5400 起，helper 调用密集（bl 洪泛，需按函数边界切）
- "JModelParser failed to load jmodel {}" 引用 0x5c2984c / 0x5dd3720
- JTEX：`"Invalid jtex header size"` 引用 0x60e8bdc / 0x60e9d18

**下一步**：从 0x4cb5400 起按函数边界完整反汇编，找：
1. 帧循环的 type 分发（数据帧 10 种类型各自的消费方式）
2. 绘制帧的 X/Y/Z 基址如何变成索引范围（k 个 90B 块的切分依据）
3. cs/ds 之外是否有其他校验（对应"尺寸漂移卡死"的根因）
4. 头部记录表的节点/材质负载布局（写自定义节点需要）

工具：capstone 5.0.6 可用；xref 扫描器现成；样本 amg_one.jmodel +
NevadaSprint 全套解码器（可当 oracle 对拍）。

### RE 第二轮战果（工具 jmox_re1_plt.py，全部 600k）

- **zstd 为静态链入 + 已导出符号**：decompress=0x66658c0、
  decompressDCtx=0x66658b4、isError=0x6652248、getFrameContentSize=0x6664234
- 引擎不直呼 zstd——经 PLT 桩（decompress 桩 0x34c0c78、
  decompressDCtx 桩 0x34c0c68、isError 桩 0x34c0c88），
  **全文件仅 1~2 个调用者**，集中在 **0x606a5e8~0x606a604 的封装函数**
  （即"解包一个 section"的通用 helper：flags 0=zstd/1=lz4/0? raw 的分发
  与 NevadaSprint jtex_mips 的 flag 语义一致）
- 封装函数入口定位中：0x606a4a0 处有一个 `stp x19,x30` 前导函数但
  BL 调用者 0——**真入口在 0x606a4a0 与 0x606a5e8 之间**，
  下一步：capstone 全量反汇编 0x606a400~0x606a680 找准入口，
  再扫 BL 到入口（含 B 尾调用与间接调用两种可能）
- JModel 区（0x4c80000~0x4d40000）无直接 zstd 调用 → 解析器必经
  该封装（可能再隔一层 helper），沿 BL 链上溯即可

### RE 第三轮战果（帧循环已现形）

- **0x606a6d8 = ReadXorBuffer(stream, key)**：读 u32 count → 读 count 字节 →
  逐字节 XOR key 低字节 → 返回。就是**头部记录名 XOR 0xAB 的读取器**
  （解析器 0x4cb5928/0x4cb5ad8/0x4cb5b74 三次调用它）
- **帧/贴图数据走 Stream 抽象**：对象 vtable+0x28 = Read 方法；
  解包分发器 0x606a5c8 读对象 **[+0xc] = 压缩 flag**，
  0 → 裸拷贝路径 0x606a6d0，非 0 → zstd（decompressDCtx/decompress）+ isError
  —— 与 JTEX mip 的 flag 语义（0=raw/1=lz4/3=zstd）同族
- zstd 调用者唯一封装：0x606a5c8（含 0x606a5e8/0x606a600 两个分支）
- 数据帧前缀的 [type][02][cs][ds] 中 **02 = 压缩 flag 字节**（非分隔符），
  type 为流类型；引擎的 section header 语义与民间逆向一致

**下一步（更精确）**：
1. 反汇编 0x4cb5900~0x4cb7fb0 的三次 ReadXorBuffer 调用块之间的代码——
   即"记录表之后、帧循环"的主体；找 Stream 对象的构造（open 流）与
   帧循环的 type 分发表
2. 0x606a6d0 一带的 unpacker 家族全为**间接调用**（vtable），
   别再扫 BL——要找 vtable 构造点（adrp+add 到 0x606a4a0~0x606a6d0 各入口
   的地址常量，扫 ADRP+ADD 引用函数入口本身）
3. JModelParser 首参 [x0+8]/[x0+0xc] 字段含义待定（version? flags?）

工具：jmox_re1_plt.py（PLT/GOT 解析可复用）

### RE 第四轮：两个解析函数定型（0x4cb5400 / 0x4cb5a4c）

**函数 1（0x4cb5400~0x4cb59d0）= 头部记录表循环**：
- 版本检查（min 11 / max 13，报错参数在 0x4cb5788/0x4cb5790）
- 每轮循环：**三次 Stream.Read**（0x28 虚调用）：**12B → 16B → 12B**
  （0x4cb59e8/0x4cb59fc/0x4cb5a14，缓冲在 x20+0x30/0x3c/0x4c）
- 然后 `bl 0x4cb67c4`（x19 入参）→ 回 0x4cb59b4 栈检查 → 循环
- 12+16+12 = 40B 固定头 + 名字 = NevadaSprint 观察的"48±4 步长"完全吻合
- 记录名从 [x20+0x20] 交换出来（0x4cb592c-0x4cb5940 与 std::string 交换）

**函数 2（0x4cb5a4c 起）= 单条记录的名字/类型处理**：
- 记录起点 x2，**类型字节 = [x2+0x1b]（第 27 字节）**
- 合法类型 11~14（`sub w10,w9,#0xb; cmp #3; b.hs → 版本报错`）
- type 11/12 → `bl 0x4cb696c`（明文名字路径）
- type 13/14 → `bl 0x606a6d8`（ReadXorBuffer，key=0xAB）
- 读出的名字与 [x20+0x20] 交换 → 存入记录表

**含义**：头部记录表每条 = 40B 定长头（3 段 Read）+ 类型字节@27 + 名字
（按类型明文/XOR）+ 变长负载。**帧循环不在这两个函数里**——
继续向下找（帧是 zstd 大流，函数 1 的三次小 Read 不是帧读取）。

**下一步**：
1. 拆 0x4cb67c4（函数 1 循环体的处理调用，x19 入参）
2. 找函数 1 的调用者 → 主加载流程 → 帧循环所在函数
3. 拆 0x4cb696c / 0x4cb65e8（辅助）

## 8. 加载器逆向续（第二次会话的战果与断点）

**重要版本教训**：`.so` 有两个版本——`A9 sifugc\project\work\apk-590301\lib\`
是 **5.9.0l**（01/02 号文档的地址），6.0.0k 的在 base APK 里
（`build\jmox_work\libAsphalt9_600k.so`，173,235,352B，已抽出）。
jmox 相关地址全部以 600k 为准：powderFactor 0x66ed8dc → 引用 0x36e2078 ✓
（xref 扫描器 jmox_xref.py 用它校验通过）。

**zstd 调用形态**：zstd 全套静态链入 600k .so 且**已导出**（dynsym 有
ZSTD_decompress=0x66658c0 / decompressDCtx=0x66658b4 / getFrameContentSize=
0x6664234 / decompressStream=0x6666324 等，全部带 size）。直接 BL 零命中
（BL 扫描器已用 0x4cb5000→bl 0x4cba990 校验通过，5 个调用者）——
说明引擎经 **PLT 间接调用**这些导出函数。断点：
- 需解析 DYNAMIC 段（DT_SYMTAB/DT_STRTAB/DT_JMPREL/DT_PLTRELSZ）拿
  ZSTD_* 的 JUMP_SLOT GOT 槽，再反汇编 .plt 找引用该槽的桩地址，
  再全文件扫 BL 到桩地址 → 即得全部 zstd 调用点
- 上一轮用 section 头遍历 RELA 时把 54MB 的 .rela.dyn 用 size<3MB 过滤掉了，
  且 sym_name 的 strtab 选择有 bug（多 strtab 时取错）——**这两个坑别再踩**
- 拿到调用点后过滤 JModelParser 区（0x4cb5000~0x4cb8000 及 0x5c29xxx /
  0x5dd3720 的失败路径调用者），即帧解压循环

**JModelParser 已知锚点**（600k）：
- 版本检查：min=11(0xb) max=13(0xd)，mov 于 0x4cb5788/0x4cb5790，
  报错串 "Unsupported jmodel version {} [min: {}, max: {}]" @0x675ea2b
- 失败串 "JModelParser failed to load jmodel {}" 引用 0x5c2984c / 0x5dd3720
- 首参对象 [x0+8] 在 0x4cb54ac 被读（疑似 version 或 record-count 字段）

## 9. 贴图线（独立可推进，不依赖加载器逆向）

- JTEX 容器已在 NevadaSprint `dump_jtex.py` 解读（ASTC 10×10 直灌、
  mip 链、sRGB/UNORM 规则见 handoff A §2）——写 JTEX = 按原容器字段
  重组 ASTC 载荷（SU7 PNG → astcenc → 10×10 块），mip 链逐级减半
- 贴图 asset 同为 NC/NX（AMG 槽位清单见 handoff A 的 19 张表 + UPD44
  目录下 car_Mercedes_AMG_One_*.tga），zip 级替换安全（README 陷阱 10）
- UV 帧重写走帧 [4] 同款精确尺寸管线（投影时顺带取最近点的 UV）


> 第三阶段（3D 模型提取 / 网站）的基础。第一、二阶段用不到，先存档。

## 提取链路（全部已验证可跑）

```
assets/main/397F9F0653ADA306          ← Pegasus manifest（加密）
  ↓ decrypt_pegasus_manifest.py，密钥是字符串 "Error 3452: file not found"
manifest 明文，32496 行，格式：
  path_hash : project_hash : 逻辑路径 : C:大小|NC:- : X:密钥|NX:- : asset_id(16 hex)
  ↓ 逻辑路径 → asset_id
assets/main/<asset_id>                ← 实际文件
```

**车模条目全部是 `NC:- NX:-`（未压缩、未加密），直接读文件即可。**

## 规模

| 类别 | 数量 |
|---|---:|
| manifest 总条目 | 32,496 |
| `/gfx3D/cars/models/` 车模 | **959** |
| CarDef 中 gfx3D 路径引用 | 31,477 |

## 文件格式

魔数：`89 6A 6D 6F 78 0D 0A 01 0A` = `\x89jmox\r\n\x01\n`
（PNG 式设计；`jmox` 应为 Gameloft Jade 引擎的模型容器）

**字符串层用 XOR 0xAB 混淆**，整文件按 0xAB 异或后即可提取名字表。

```python
x = bytes(b ^ 0xAB for b in open(path,'rb').read())
```

## 塞纳车模实例

```
逻辑路径 /gfx3D/cars/models/McLaren_Senna_car.json  →  .jmodel
asset_id 397F9F1C11A0A48C
大小     1,853,567 B
字符串   9,325 个（去重后）
```

解出的结构（节选）：

**骨骼**
`root` / `bone_anim01` / `bone_steering_wheel`
`bone_wheel_{BL,BR,FL,FR}_steer`、`bone_wheel_{BL,BR,FL,FR}_rotation`

**网格**
`chassis` / `glass` / `glass_window_{F,B,L,R}` / `glass_detachable`
`lights_{FL,FR,BL,BR}` / `lights_thirdlight` / `emissive_mesh`
`wheel{BL,BR,FL,FR}_caliper` / `wheel*_emissive_mesh_brakedisk` / `steering_wheel`

**可拆卸改装件**（两套外观方案）
`custom_3d_0{1,2}_{hood,roof,bumper_F,bumper_B,detachable_skirt_L,detachable_skirt_R}`

**碰撞脱落**
`detach_bumper_{F,B}_4` / `detach_door_{L,R}_90` / `detach_skirt_{L,R}_4`

**特效锚点**
`nitro_dummy_{1,2}` / `nitro_front` / `trail_left` / `trail_right`
`engine_dummy_{1,2}` / `underside_dummy`

## 配套贴图

同一 manifest 里，路径形如
`/gfx3D/cars/textures/car_McLaren_Senna_<slot>.tga/|/texture`

槽位命名：`carpaint` / `details` / `glass` / `LOD` / `emissive_mesh` / `livery`
后缀：`_al`(albedo) `_nm`(normal) `_mk`(mask) `_ala` `_dfa` `_tem`

## 还没做的

- jmox 的**二进制结构**（顶点/索引/UV/骨骼权重的实际布局）——只解了字符串层
- 贴图容器格式（`.tga` 是逻辑名，实际编码待验）
- 导出到通用格式（glTF / OBJ）

**结论：模型能提取，链路和格式都通了，剩下的是解二进制网格布局的工程量。**


### RE 第四轮追加（frida 动态分析打通）

- frida 17.15.4 客户端已在 PC（pip 包已有），设备端 frida-server 同版本
  在 `/data/local/tmp/`（root 启动 `su -c '... -D &'`）
- **两个 frida 17 的坑**：①`script.on_message = fn` 被静默忽略，
  必须 `script.on('message', fn)`；②`Module.findBaseAddress` 已删除，
  用 `Process.enumerateModules()` 遍历找 libAsphalt9.so
- spawn 模式被游戏防作弊超时拒绝；用**竞速 attach**（monkey 启动后 4s
  pidof 拿 pid 立即 attach）成功，loading 屏内挂钩
- 追踪脚本 `tools/jmox_trace2.py`（改 attach 逻辑），日志
  `build/jmox_work/frida_trace3.log`（7,600+ 事件）
- **帧/section 消费循环定位：lr=0x4cce624 恒定**（unpack 0x606a5c8 的
  唯一高频调用者），x1 值呈 0xb5/0x82/0x86 离散分布（疑似 section 类型或长度）
- 下一步：反汇编 0x4cce624 所在函数（0x4ccxxxx 区），绘制段语义即出


### RE 第五轮：section 读取现场（0x4cce590-0x4cce640 反汇编实录）

```
0x4cce5b4: blr x8        ← stream->Read(&u32_a, 4)
0x4cce5d0: blr x8        ← stream->Read(&u32_b, 4)
0x4cce5e8: blr x8        ← vtable+0x60 调用(x1=u32_a) → 分配输出 (x0,obj)
0x4cce620: bl 0x606a6ac  ← SectionReader(out, ?, u32_a, stream, type=2|3, ?)
   type 由 csel 选 2 或 3（对应 zstd 变体选择）
0x4cce624 之后: 返回 bool，成功则内容进 [sp+0x140] 对象
```
**引擎是顺序流读取**（vtable Read 逐段），理论上尺寸无关——
但实测尺寸漂移必崩（T2v3），等长必活（m2squash）→ 说明存在
**未定位的尺寸/偏移敏感点**（候选：头部记录表负载内嵌 section 偏移、
绘制帧 X/Y/Z 字段、或 EOF 校验）。

### 完整网格写入的约束推导（下一轮的设计前提）

每帧 cs 必须逐字节等于原值（已证），ds/内容可变（已证）：
- [0] 位置: cs=483,393 固定，内容任意（抖动法已验证 13s 命中）
- [4] UV:  cs=663,040 固定
- [7] 骨骼: cs=663,040    [8] 权重: cs=663,040
- [9] 索引: cs=503,366 —— 退化三角（a,a,a）可无损调索引数 → 可精确命中
- 绘制帧 ×73: 内容 = k×90B 块（AABB+矩阵+节点号），k 不可变（等长），
  但**节点号/矩阵/AABB 可自由改**（明文/可精确命中的 zstd）
- 顶点数 n 理论可变（ds 独立于 cs），但需与 [4][7][8][9] 的 ds 联动一致

**结论：自建拓扑受"逐帧 cs 不得变"约束——SU7 网格必须重排进 AMG 的
帧/块/字节预算里。可行路径：顶点数不变（165,760），索引数不变
（528,444），只改 [0] 位置 + [9] 索引连接关系 + [4] UV。**
即"AMG 的纸，画 SU7 的画"——拓扑形状（连接关系）全自由，
顶点分布可大改（顶点在 SU7 表面重新均匀采样 165,760 个点）。

### SU7 完整形状的施工方案（下一轮主体）

1. SU7 点云重建拓扑：泊松/球面采样或直接用 SU7 自带索引（glb 有索引！
   146 个 mesh 的 triangles），重采样到恰好 165,760 顶点 + 528,444 索引
   （多余索引填退化三角，不足则细分边）
2. 每顶点 UV 取 SU7 原 UV → 写 [4]
3. [0] 位置写 SU7 坐标（轴映射同投影），[9] 索引按 AMG 帧段结构重排
   （顶点按所属部件分组对齐 AMG 的块/节点分布）
4. 每帧精确 cs 命中（抖动法，位置/UV/索引都可微调）
5. 贴图：SU7 PNG → ASTC → JTEX（管线已通，闪电黄已验证渲染）
6. 材质对应：AMG 25 材质槽 × SU7 36 材质 → 按语义映射（CarPaint→carpaint01,
   Windows→glass, tire→tires, Rim→?）
