#!/usr/bin/env python3
"""把仓库里的路径占位符还原为本机真实路径（tools/ 下所有 .py/.sh）。

仓库内统一用占位用户名 player（如 C:\\Users\\player\\Desktop\\a9模型），
克隆后跑一次本脚本即可在本机直接使用：

    python tools/fix_paths.py                 # 还原为当前用户 Desktop\\a9模型
    python tools/fix_paths.py "D:\\某目录\\a9模型"   # 或指定项目根
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
real_user = Path.home().name
target_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "a9模型"

PAIRS = [
    ("C:\\Users\\player\\Desktop\\a9模型", str(target_root)),
    ("C:/Users/player/Desktop/a9模型", str(target_root).replace("\\", "/")),
    ("/c/Users/player/Desktop/a9模型", str(target_root).replace("\\", "/").replace("C:/", "/c/")),
    ("C:\\Users\\player\\", "C:\\Users\\" + real_user + "\\"),
    ("C:/Users/player/", "C:/Users/" + real_user + "/"),
    ("/c/Users/player/", "/c/Users/" + real_user + "/"),
]

n = 0
for f in list(BASE.glob("tools/*.py")) + list(BASE.glob("tools/*.sh")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    new = txt
    for old, newv in PAIRS:
        new = new.replace(old, newv)
    if new != txt:
        f.write_text(new, encoding="utf-8")
        n += 1
print(f"已还原 {n} 个文件 -> 本机路径（{target_root}）")
