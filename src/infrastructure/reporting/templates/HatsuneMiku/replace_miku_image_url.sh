#!/usr/bin/env bash
# ============================================
#  装饰图链接一键替换（img.heliar.top 换成 jsDelivr）
#  用法：把本脚本放到模板 HTML 目录，运行：
#    bash replace_miku_image_url.sh
#  会自动替换该目录（含子目录）下所有 .html 里的旧链接
# ============================================

cd "$(dirname "$0")" || exit   # 先切到脚本所在目录

python3 <<'EOF'
import glob

OLD = "https://img.heliar.top/file/"     # 旧图床地址（已失效）
NEW = "https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/HatsuneMiku/"  # 新图床地址

# ↓↓↓ 新旧文件名对照表，以后要换图就改这里 ↓↓↓
# 格式："旧文件名": "新文件名"
MAP = {
    "1776606860022_retouch_2026032802083201.png": "retouch_2026032802083201.png",   # 峰值区装饰图
    "1778303907562_retouch_2026032810150449.png": "retouch_2026032810150449.png",   # 质量区小人
    "1778265932033_retouch_2026032810150449.jpeg": "retouch_2026032810150449.png",  # 话题图1（和小人同一张）
    "1778265932542_retouch_2026032810143720.jpeg": "retouch_2026032810143720.png",  # 话题图2
    "1778265934386_retouch_2026032810151717.jpeg": "retouch_2026032810151717.png",  # 话题图3
    "1778265931177_retouch_2026032810153327__1_.jpeg": "retouch_2026032810153327.png",  # 话题图4
    "1778265933286_retouch_2026032810145078.jpeg": "retouch_2026032810145078.png",  # 话题图5
}

n = 0
for f in glob.glob("**/*.html", recursive=True):   # 遍历所有 html 文件
    s = open(f, encoding="utf-8").read()
    t = s
    for old, new in MAP.items():                   # 逐个替换旧链接
        t = t.replace(OLD + old, NEW + new)
    if t != s:                                      # 有变化才写回，避免无意义改动
        open(f, "w", encoding="utf-8").write(t)
        print("已替换:", f)
        n += 1

print("完成！共替换", n, "个文件" if n else "（没找到要替换的链接，可能已经换过了）")
EOF
