param([int]$AgentHours = 8)
$ErrorActionPreference = 'Stop'
foreach ($target in @('production','staging','development')) {
    & (Join-Path $PSScriptRoot 'Start-Lab.ps1') -Environment $target -AgentHours $AgentHours
}
