@echo off
chcp 65001 >nul
REM ============================================
REM  装饰图链接一键替换（img.heliar.top 换成 jsDelivr）
REM  用法：把本脚本放到模板 HTML 目录，双击运行
REM  会自动替换该目录（含子目录）下所有 .html 里的旧链接
REM ============================================

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d='%~dp0';" ^
  "$OLD='https://img.heliar.top/file/';" ^
  "$NEW='https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/HatsuneMiku/';" ^
  "$MAP=@{'1776606860022_retouch_2026032802083201.png'='retouch_2026032802083201.png';'1778303907562_retouch_2026032810150449.png'='retouch_2026032810150449.png';'1778265932033_retouch_2026032810150449.jpeg'='retouch_2026032810150449.png';'1778265932542_retouch_2026032810143720.jpeg'='retouch_2026032810143720.png';'1778265934386_retouch_2026032810151717.jpeg'='retouch_2026032810151717.png';'1778265931177_retouch_2026032810153327__1_.jpeg'='retouch_2026032810153327.png';'1778265933286_retouch_2026032810145078.jpeg'='retouch_2026032810145078.png'};" ^
  "$n=0;" ^
  "Get-ChildItem $d -Recurse -Filter *.html | ForEach-Object {" ^
  "$c=Get-Content $_.FullName -Raw -Encoding UTF8; $ch=$false;" ^
  "foreach($k in $MAP.Keys){ if($c.Contains($OLD+$k)){ $c=$c.Replace($OLD+$k,$NEW+$MAP[$k]); $ch=$true } };" ^
  "if($ch){ Set-Content $_.FullName -Value $c -Encoding UTF8 -NoNewline; Write-Host ('已替换: '+$_.FullName); $n++ }" ^
  "};" ^
  "if($n -eq 0){ Write-Host '没找到要替换的链接（可能已经换过了）' } else { Write-Host ('完成！共替换 '+$n+' 个文件') }"

echo.
pause
