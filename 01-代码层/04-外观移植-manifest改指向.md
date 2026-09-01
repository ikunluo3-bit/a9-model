# 外观移植：manifest 改指向

物理移植靠"改 gdb 描述符指向"，外观移植靠**同一个思路的上一层**——
改 Pegasus manifest 里的 `asset_id`。

---

## 1. manifest 是唯一的间接层

```
path_hash : project_hash : 逻辑路径 : (C:明文大小|NC:-) : (X:密钥|NX:-) : asset_id
```

引擎按**逻辑路径**查表拿 `asset_id`，再去读 `assets/main/<asset_id>`。

把受体那几行的 `asset_id` 换成供体的：路径、哈希、压缩/加密标志全不动，
引擎照旧问"科迈罗的模型"，**拿到的是女武神的字节**。

**`asset_id` 是定长 16 位十六进制 —— 替换前后行长一字节不差。**
manifest 明文 5,202,868 B 改完还是 5,202,868 B，
重新加密后密文也还是 5,202,876 B。回封时其他条目一个都不用碰。

## 2. 角色对齐

A9 的资源命名极不统一，同一台车会出现四种拼法：

```
chevrolet_camaroLT_colShape.shapedef
car_Chevrolet_Camaro_LT_2.0_Turbo_2016_anim.json
Chevrolet_Camaro_LT_20L_Turbo_2016_car.json
car_Chevrolet_Camaro_LT_2L_Turbo_2016_carpaint_mk.tga
```

所以不能按车名匹配，得先把路径归到**与车名无关的角色**上再对齐：

| 角色 | 路径特征 |
|---|---|
| `model` | `/gfx3D/cars/models/*_car.json` |
| `fx_overclocked` / `fx_respawn` | 同目录 `_fx_*_dyn.json` |
| `collision` | `/collisions/*_colShape.shapedef` |
| `anim` | `/gfx3D/cars/animations/*_anim.json` |
| `shockwave` | `/gfx3D/fx/models/fx_shockwave_lines_*` |
| `tex:<后缀>` | `/gfx3D/cars/textures/car_*_<后缀>.tga` |
| `sound` | `/sounds/Asphalt_A9.voxproj/\|/<车名>` |

科迈罗 LT 18 个角色全部在女武神侧找到对应，**换了 17 个 asset_id**
（sound 与 sound_npc 共用一个）。
女武神独有的 4 个（刹车动画、三套涂装 LOD）受体没有对应路径，不用处理。

## 3. 贴图必须一起换

`.jmodel` 里（字符串 XOR `0xAB`）只有**材质槽名**：
`carpaint`、`carpaint02`、`carpaint_custom01..03`，
**没有贴图文件路径**——贴图是按车名约定去查的。

所以只换模型不换贴图，会得到"女武神的网格 + 科迈罗的贴图"，UV 对不上必然花掉。
10 张贴图（carpaint_mk / details_ala,mk,nm,tem / emissive_mesh_dfa / glass_ala /
LOD_al,mk,tem）必须同步换。

## 4. 车库缩略图不用管

`CarThumbnails.gdb` 里是 `scripting::OffscreenScene` 和
`FindCamera("/levels/CarThumbnails/DefaultCamera")` ——
**缩略图是运行时用真实 3D 模型离屏渲染出来的，不是预烘焙图片。**
模型一换，车库卡片自动变女武神。

## 5. 换不掉的

| 项 | 出处 |
|---|---|
| 车名 "Chevrolet Camaro LT" | texts babel |
| D 级徽标、面板数字 | `A9-business.gdb` |

这些属于面板层，车主明确要求不动。

## 6. 工具

```bash
python tools/visualswap.py --plan                    # 看角色映射
python tools/visualswap.py --out manifest-swapped.txt
python tools/repack.py ... --manifest manifest-swapped.txt
```

`repack.py --manifest` 会强制校验明文长度不变，并做加解密 round-trip。
