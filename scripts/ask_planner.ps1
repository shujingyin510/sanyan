<#
  ask_planner.ps1 — 规划咨询门客户端:在制定下一步计划前,向本地规划顾问(DSH 会话)咨询。

  用法:
    .\ask_planner.ps1 "我计划做 X(文件清单/步骤/验收);当前状态 Y;请给下一步建议"
    Get-Content plan.txt | .\ask_planner.ps1
    .\ask_planner.ps1 "..." -TimeoutSec 600     # 最长等 10 分钟
    .\ask_planner.ps1 "..." -NoWait              # 只提交,拿 consultId 稍后再取
    .\ask_planner.ps1 -Query <consultId>         # 稍后取答复

  安全约定(开源仓安全):
    - 本脚本**不含任何密钥**;令牌运行时从 $env:DSH_PLANNER_TOKEN 或
      $HOME\.dsh-planner-token 读取,缺失即视为"顾问不可用"并优雅退出(不报错阻断)。
    - 咨询前先 GET /health 验明顾问身份(planner=dsh-local);验不过就不采纳其意见。
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$QuestionParts,
    [int]$TimeoutSec = 300,
    [switch]$NoWait,
    [string]$Query
)

$ErrorActionPreference = "Stop"
$bridge = if ($env:DSH_PLANNER_BRIDGE) { $env:DSH_PLANNER_BRIDGE } else { "http://127.0.0.1:8790" }
$tokenFile = if ($env:DSH_PLANNER_TOKEN_FILE) { $env:DSH_PLANNER_TOKEN_FILE } else { Join-Path $HOME ".dsh-planner-token" }

function Get-PlannerToken {
    if ($env:DSH_PLANNER_TOKEN) { return $env:DSH_PLANNER_TOKEN.Trim() }
    if (Test-Path $tokenFile) { return (Get-Content $tokenFile -Raw).Trim() }
    return $null
}

$token = Get-PlannerToken
if (-not $token) {
    Write-Output "规划顾问未配置(找不到 $tokenFile 或 DSH_PLANNER_TOKEN)——跳过咨询,按原计划继续。"
    exit 0
}
$headers = @{ "X-Planner-Token" = $token }

# 验明顾问身份:桥必须回 planner=dsh-local
try {
    $health = Invoke-RestMethod -Uri "$bridge/health" -Headers $headers -Method Get -TimeoutSec 10
    if ($health.planner -ne "dsh-local") {
        Write-Output "8790 端口上的服务不是规划顾问(planner=$($health.planner))——不采纳其意见,按原计划继续。"
        exit 0
    }
} catch {
    Write-Output "规划顾问不可达($($_.Exception.Message))——跳过咨询,按原计划继续。"
    exit 0
}

# 模式一:按 consultId 查询已有咨询
if ($Query) {
    $r = Invoke-RestMethod -Uri "$bridge/consult/$Query" -Headers $headers -Method Get -TimeoutSec 30
    if ($r.status -eq "answered") {
        Write-Output "===== 规划顾问答复 ====="
        Write-Output $r.answer
        Write-Output "========================="
        exit 0
    }
    Write-Output "状态: $($r.status)(consultId=$($r.consultId),已等待 $([math]::Round($r.waitedMs/1000)) 秒)"
    if ($r.status -eq "pending") { Write-Output "稍后再查: .\ask_planner.ps1 -Query $($r.consultId)" }
    exit 0
}

$question = ($QuestionParts -join " ").Trim()
if (-not $question) { $question = [Console]::In.ReadToEnd().Trim() }
if (-not $question) {
    Write-Error '没有收到问题。用法: .\ask_planner.ps1 "问题内容"'
    exit 2
}

# 提交咨询(异步,立即拿到 consultId)
try {
    $body = @{ question = $question } | ConvertTo-Json -Compress
    $sub = Invoke-RestMethod -Uri "$bridge/consult" -Headers $headers -Method Post -ContentType "application/json" -Body $body -TimeoutSec 60
} catch {
    Write-Output "提交咨询失败($($_.Exception.Message))——跳过咨询,按原计划继续。"
    exit 0
}
if ($sub.ok -ne $true) { Write-Output "提交失败: $($sub.error)"; exit 0 }

$consultId = $sub.consultId
Write-Output "已提交咨询 consultId=$consultId,等待顾问答复(最多 $TimeoutSec 秒)…"

if ($NoWait) {
    Write-Output "未等待。稍后取答复: .\ask_planner.ps1 -Query $consultId"
    exit 0
}

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$nextNotice = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    try { $r = Invoke-RestMethod -Uri "$bridge/consult/$consultId" -Headers $headers -Method Get -TimeoutSec 30 } catch { continue }
    if ($r.status -eq "answered") {
        Write-Output "===== 规划顾问答复 ====="
        Write-Output $r.answer
        Write-Output "========================="
        exit 0
    }
    if ($r.status -eq "timeout" -or $r.status -eq "error") {
        Write-Output "顾问未能答复(status=$($r.status) $($r.error))——按原计划继续。"
        exit 0
    }
    if ((Get-Date) -ge $nextNotice) {
        Write-Output "  …顾问仍在处理(已等待 $([math]::Round($r.waitedMs/1000)) 秒)"
        $nextNotice = (Get-Date).AddSeconds(30)
    }
}

Write-Output "尚未收到答复(consultId=$consultId)。可继续做准备工作,稍后执行:"
Write-Output "  .\ask_planner.ps1 -Query $consultId"
exit 0
