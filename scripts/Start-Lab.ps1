param([string]$PythonExe, [int]$AgentHours = 8)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $labRoot
if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}
$env:KUBECONFIG = Join-Path $labRoot '.local\kubeconfig'
if (-not (Test-Path -LiteralPath $env:KUBECONFIG)) { throw 'Primero crea el cluster siguiendo PUBLICACION.txt.' }
docker start devops-lab-control-plane devops-lab-worker devops-lab-worker2 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop debe estar iniciado.' }
function Get-LabProcess([string]$PidFile, [string]$ExpectedPath) {
    if (Test-Path -LiteralPath $PidFile) {
        $processId = [int](Get-Content -LiteralPath $PidFile -Raw)
        $foundProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($foundProcess -and $foundProcess.Path -eq $ExpectedPath) { return $foundProcess }
    }
    return $null
}
$tunnelExe = Join-Path $labRoot '.local\bin\cloudflared.exe'
$tunnelProcess = Get-LabProcess '.local\tunnel.pid' $tunnelExe
if (-not $tunnelProcess) {
    # Each restart has a new public URL; keep only this process's log for parsing.
    if (Test-Path '.local\tunnel.log') { Move-Item -LiteralPath '.local\tunnel.log' -Destination ('.local\tunnel-' + (Get-Date -Format 'yyyyMMddHHmmss') + '.log') }
    $tunnelProcess = Start-Process -FilePath $tunnelExe -ArgumentList @('tunnel','--url','https://127.0.0.1:9443','--origin-ca-pool','.local/tls.crt','--protocol','http2','--no-autoupdate','--logfile','.local/tunnel.log') -WorkingDirectory $labRoot -WindowStyle Hidden -PassThru
    $tunnelProcess.Id | Set-Content '.local\tunnel.pid'
}
$publicUrl = $null
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (Test-Path '.local\tunnel.log') {
        $foundUrls = [regex]::Matches((Get-Content '.local\tunnel.log' -Raw), 'https://[a-z0-9-]+\.trycloudflare\.com')
        if ($foundUrls.Count -gt 0) { $publicUrl = $foundUrls[$foundUrls.Count - 1].Value; break }
    }
    Start-Sleep -Seconds 1
}
if (-not $publicUrl) { throw 'El tunel no entrego una URL. Revisa .local\tunnel.log.' }
$urls = @{production = $publicUrl}
if (Test-Path '.local\public_urls.json') {
    $previous = Get-Content '.local\public_urls.json' -Raw | ConvertFrom-Json
    foreach ($property in $previous.PSObject.Properties) { if ($property.Name -ne 'production') { $urls[$property.Name] = $property.Value } }
}
[IO.File]::WriteAllText((Join-Path $labRoot '.local\public_urls.json'), ($urls | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$agentProcess = Get-LabProcess '.local\agent.pid' $PythonExe
if (-not $agentProcess) {
    $agentProcess = Start-Process -FilePath $PythonExe -ArgumentList @('-X','utf8','-u','scripts/local_deploy_agent.py','--hours',"$AgentHours") -WorkingDirectory $labRoot -WindowStyle Hidden -RedirectStandardOutput '.local/agent.log' -RedirectStandardError '.local/agent-error.log' -PassThru
    $agentProcess.Id | Set-Content '.local\agent.pid'
}
Write-Host "API publica: $publicUrl/DevOps"
Write-Host 'Pipeline: https://github.com/jorgefprietol/devops-exercise/actions'
Write-Host 'El agente atiende despliegues durante la sesion configurada; el servicio depende del PC y Docker.'
