# SETUP —— 从零恢复指南

本仓库只含**知识与工具**（文档 + 脚本），不含任何游戏资源本体。
母包 / 提取库 / 调产物全部可由本工具链重建，所以仓库很轻，能力一点不少。

## 0. 路径占位符（克隆后第一件事）

仓库内所有 Windows 路径的用户名统一写作占位符 `player`。
克隆后跑一次：

```bash
python tools/fix_paths.py                # 还原为当前用户 Desktop\a9模型
python tools/fix_paths.py "D:\某处\a9模型"   # 或指定项目根
```

> 还原后本地文件与仓库会出现路径 diff，属预期——**仓库以占位符为准，别把还原后的路径 commit 回去**。

## 1. 环境要求

| 件 | 用途 |
|---|---|
| Windows + Git Bash | 全部 shell 脚本 |
| Python 3.11+ | 工具链 |
| Android SDK：build-tools 37.0.0 + platform-tools | repack / apksigner / adb（35/36 签 3.5GB 会溢出，必须 37） |
| Java | apksigner 依赖 |
| frida 17.x（可选） | 动态分析 |
| astcenc（可选） | 贴图实验 |

## 2. 母包与基础库

1. 把 A9 安卓母包（如 `A9-600300-6.0.0k-base.apk`）放到
   `../A9 sifugc/output/`（或自行调整脚本里的路径）。
2. 提取基础库（生成 `gdb-6.0.0k/`，gitignore，不入库）：

```bash
python tools/extract_gdb.py --help   # 按提示从母包提取
```

## 3. 签名配置（不入库）

`tools/keystore.local` 放一行签名口令（本地已配置，克隆后需自建），
keystore 文件本体在 `../A9 sifugc/project/tools/a9-repack.keystore`。

## 4. 日常操作

```bash
# 查车
python tools/car.py <名字片段>
# 车队改车（唯一入口，禁止直接 carswap --apply，见 README 陷阱12）
python tools/fleet.py list / add / set / donor / remove
python tools/fleet.py build          # 全量重算 tuned-carswap/
python tools/fleet.py install 标签    # 回封+签名+装机
# iOS 版
python tools/ios_build.py            # gdb-ios 基础库上跑点名 swap -> tuned-ios/
python tools/ios_pack.py             # 加密回封 main.pack + 重封 IPA（未签名）
```

## 5. iOS 线要点

- 基础库 `gdb-ios-6.0.0/` 由 `main.pack` 内三个 gdb（AID 与安卓相同）解密生成；
  解密密钥与安卓 manifest 通用（`tools/ios_pack.py` 里有完整流程）。
- 产物 IPA 未签名，用 Sideloadly / 爱思助手以 Apple ID 自签安装。
- iOS 数据快照与安卓同代不同序（字节不同），**必须基于 iOS 库重跑 swap**，
  不能直接搬安卓 tuned 产物。
