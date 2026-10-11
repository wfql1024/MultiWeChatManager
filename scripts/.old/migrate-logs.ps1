# 一次性日志迁移（用户 2026-10-11）
#
# 背景：日志原先由 logback 以**系统默认编码**（中文 Windows = GBK）写盘 → 在 VSCode 里全是乱码。
#      现在已把 logback 改成显式 UTF-8；历史上这些 GBK 文件需要转码迁移到新的日志目录。
#
# 做什么：
#   1. 把 %APPDATA%\JhiFengMultiChat\<ver>\{Dev?}UserFiles\logs\*.log 以 **GBK 读**、以 **UTF-8 写**到
#      目标目录（项目内 storage\<ver>\DevUserFiles\logs\）
#   2. 顺手迁移项目根 logs\ 下那批"绕过 Launcher 直接跑 MainApp"时漏下的日志（同样是 GBK）
#   3. 已存在的目标文件**不覆盖**（加 .migrated 后缀区分），避免误伤新日志
#
# 用法： pwsh -File tmp\migrate-logs.ps1
#        pwsh -File tmp\migrate-logs.ps1 -DryRun     # 只看要做什么，不动文件

param(
    [string]$Version = '4.0.0.7000',
    [switch]$DryRun,
    [string]$Only = '',        # 只迁这一个文件名（如 jfmultichat.log）
    [switch]$Force             # 覆盖已存在的目标文件（重迁用）
)

$ErrorActionPreference = 'Stop'

$srcDirs = @(
    (Join-Path $env:APPDATA "JhiFengMultiChat\$Version\DevUserFiles\logs"),
    (Join-Path $env:APPDATA "JhiFengMultiChat\$Version\UserFiles\logs"),
    'E:\SpaceDev\Projects\Mine\JhiFengMultiChat\logs'          # 项目根那处（IDE 直跑时漏下的）
)
$dstDir = "E:\SpaceDev\Projects\Mine\JhiFengMultiChat\storage\$Version\DevUserFiles\logs"

Write-Host "目标目录: $dstDir"
if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }

$gbk = [System.Text.Encoding]::GetEncoding(936)          # GBK
$utf8NoBom = New-Object System.Text.UTF8Encoding($false) # UTF-8 不带 BOM

$total = 0
foreach ($src in $srcDirs) {
    if (-not (Test-Path $src)) { Write-Host "跳过（不存在）: $src"; continue }
    $files = @(Get-ChildItem $src -Filter '*.log' -File)
    if ($Only) { $files = @($files | Where-Object { $_.Name -eq $Only }) }
    if ($files.Count -eq 0) { continue }
    Write-Host "来源: $src"
    foreach ($f in $files) {
        $target = Join-Path $dstDir $f.Name
        if ((Test-Path $target) -and -not $Force) {
            $target = "$target.migrated"                      # 不覆盖已有（除非 -Force）
        }
        # 用 FileShare.ReadWrite 打开：正在运行的软件会占着当前那个 jfmultichat.log，
        # 直接 ReadAllText 会报"being used by another process"
        $fs = [System.IO.File]::Open($f.FullName,
                [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $sr = New-Object System.IO.StreamReader($fs, $gbk)
            $text = $sr.ReadToEnd()
            $sr.Dispose()
        } finally {
            $fs.Dispose()
        }
        if ($DryRun) {
            Write-Host ("  [DryRun] {0} ({1} 字节) -> {2}" -f $f.Name, $f.Length, $target)
        } else {
            [System.IO.File]::WriteAllText($target, $text, $utf8NoBom)
            Write-Host ("  迁移 {0} ({1} 字节)" -f $f.Name, $f.Length)
        }
        $total++
    }
    # -Only 时只认**第一个**含有该文件的来源（否则会被后面那批同名旧副本覆盖）
    if ($Only) { break }
}
Write-Host "完成：共处理 $total 个文件$(if ($DryRun) { '（DryRun，未写盘）' })"
