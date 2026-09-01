# 全库统计（gdb-6.0.0k）

**由 `tools/fleetstats.py` 自动生成，勿手改。**
数据源 `gdb-6.0.0k/`，428B 队列 295 台，剔除开发用参考车与非玩家载具后 290 台。

> 引用任何「全库最高/最低」时都要连版本一起写。
> 跨版本沿用手写数字已经出过三次错 —— 见 README「常见陷阱」。
>
> 下表极值已被本项目改装实践使用并实测验证：
> 锐度顶格 98900（11 号文档 A/B）、抓地 1.28~1.3（多轮装机）、
> 氮气消耗下探至原厂最低之下（×0.25~×0.5 倍率改装，无越界副作用）。

## CarPhysics

| 项 | 最低 | 最低者 | 中位 | 最高 | 最高者 |
|---|---:|---|---:|---:|---|
| 物理极速 | **208** | KTM X-Bow GTX | 266 | **357** | Devel Sixteen |
| 加速 | **1.629** | Mitsubishi Lancer Evolutio | 2.429 | **2.8** | Lamborghini Diablo GT |
| 抓地 | **0.5366** | KTM X-Bow GTX | 0.7765 | **1.3** | NIO EP9 Anniversary Specia |
| 转向锐度 | **1.38e+04** | Mazda Furai | 3.95e+04 | **9.89e+04** | Devel Sixteen |
| 操控 idx77 | **0.1** | Ford GT | 0.53 | **1** | McLaren Senna |
| 操控 idx76 | **0.02** | Ford GT | 0.3 | **0.75** | Chevrolet Corvette Grand S |
| 单喷消耗 | **6** | Porsche 911 GT3 RS | 15 | **30** | W Motors Lykan HyperSport  |
| 橙喷消耗 | **13.5** | Nissan 370Z SpecialEdition | 30 | **60** | W Motors Lykan HyperSport  |
| 蓝喷消耗 | **9** | Porsche 911 GT3 RS | 22.5 | **45** | W Motors Lykan HyperSport  |
| 紫喷消耗 | **16** | Porsche 911 GT3 RS | 40 | **105** | Mercedes_Benz_Biome_2010 |
| 蓝喷加成 | **5.971** | Mitsubishi Lancer Evolutio | 8.286 | **10** | Mercedes Benz Concept Silv |
| 蓝喷维持 | **2300** | Volkswagen XL Sport Concep | 5640 | **4e+04** | Nissan GT-R Nismo Neon |

## CarChassis

| 项 | 最低 | 最低者 | 中位 | 最高 | 最高者 |
|---|---:|---|---:|---:|---|
| 质量kg | **592** | Praga R1 | 1404 | **2490** | Lotus_Emeya |
| 前轮距 | **1.22** | McMurtry Speirling | 1.66 | **2.12** | Ferrante_Design_Dose_Elytr |
| 后轮距 | **1.22** | McMurtry Speirling | 1.65 | **2.172** | Mercedes Benz Concept Silv |
| 轴距 | **2** | McMurtry Speirling | 2.7 | **3.47** | Devel Sixteen |
| 重心高 | **-0.19** | Maserati Alfieri | -0.15 | **-0.035** | Rimac Concept One |

## 抓地百分位（改装选值用）

| 值 | 百分位 |
|---:|---:|
| 0.6 | 2% |
| 0.7 | 17% |
| 0.8 | 62% |
| 0.9 | 85% |
| 0.95 | 91% |
| 1.0 | 94% |
| 1.05 | 97% |
| 1.1 | 98% |
| 1.15 | 99% |
| 1.2 | 100% |
| 1.28 | 100% |
| 1.3 | 100% |

## 转向锐度百分位

| 值 | 百分位 |
|---:|---:|
| 30000 | 17% |
| 40000 | 51% |
| 50000 | 81% |
| 56500 | 90% |
| 58000 | 91% |
| 70000 | 98% |
| 83000 | 99% |
| 98900 | 100% |

## 蓝喷消耗百分位（越小越省）

| 值 | 百分位 |
|---:|---:|
| 9 | 0% |
| 12 | 2% |
| 14 | 6% |
| 16.2 | 13% |
| 18 | 20% |
| 20.25 | 30% |
| 22.5 | 46% |
| 27 | 71% |
| 30 | 82% |

## 物理极速百分位

| 值 | 百分位 |
|---:|---:|
| 200 | 0% |
| 230 | 4% |
| 250 | 20% |
| 266 | 50% |
| 278 | 75% |
| 285 | 80% |
| 300 | 88% |
| 320 | 95% |
| 340 | 99% |
| 357 | 100% |

