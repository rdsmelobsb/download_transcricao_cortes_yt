<#
.SYNOPSIS
    Registra os agendamentos diários dos pipelines YouTube e Kwai no
    Agendador de Tarefas do Windows (Task Scheduler).

.DESCRIPTION
    Grade diária configurada:
      - PoliticaDireta_Pipeline_YouTube : 08:00 e 17:00 (todos os dias)
      - PoliticaDireta_Pipeline_Kwai    : 09:00 e 18:00 (todos os dias)

    Pode ser executado novamente a qualquer momento para recriar/atualizar as tarefas.
#>

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe  = Join-Path $ProjectDir "venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python do ambiente virtual não encontrado em: $PythonExe"
}

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# 1. Pipeline YouTube — Diariamente às 08:00 e 17:00
$ActionYouTube = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "pipeline_youtube.py" `
    -WorkingDirectory $ProjectDir

$TriggersYouTube = @(
    (New-ScheduledTaskTrigger -Daily -At "08:00"),
    (New-ScheduledTaskTrigger -Daily -At "17:00")
)

Register-ScheduledTask `
    -TaskName "PoliticaDireta_Pipeline_YouTube" `
    -Description "Pipeline diário Política Direta (YouTube Shorts): métricas, download, Whisper, Gemini, FFmpeg e agendamento sem colisões (08h e 17h)." `
    -Action $ActionYouTube `
    -Trigger $TriggersYouTube `
    -Settings $Settings `
    -Force | Out-Null

# 2. Pipeline Kwai — Diariamente às 09:00 e 18:00
$ActionKwai = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "pipeline_kwai.py" `
    -WorkingDirectory $ProjectDir

$TriggersKwai = @(
    (New-ScheduledTaskTrigger -Daily -At "09:00"),
    (New-ScheduledTaskTrigger -Daily -At "18:00")
)

Register-ScheduledTask `
    -TaskName "PoliticaDireta_Pipeline_Kwai" `
    -Description "Pipeline diário Política Direta (Kwai via ADB/BlueStacks): publicação dos TOP 3 cortes + coleta de métricas (09h e 18h)." `
    -Action $ActionKwai `
    -Trigger $TriggersKwai `
    -Settings $Settings `
    -Force | Out-Null

Write-Host "`n✅ Tarefas registradas com sucesso no Agendador de Tarefas do Windows!`n" -ForegroundColor Green

Get-ScheduledTask -TaskName "PoliticaDireta_Pipeline_*" | ForEach-Object {
    $info = Get-ScheduledTaskInfo -TaskName $_.TaskName
    $horarios = ($_.Triggers | ForEach-Object { ([datetime]$_.StartBoundary).ToString("HH:mm") }) -join ", "
    [PSCustomObject]@{
        Tarefa       = $_.TaskName
        Estado       = $_.State
        Horarios     = $horarios
        ProximaExec  = $info.NextRunTime
    }
} | Format-Table -AutoSize
