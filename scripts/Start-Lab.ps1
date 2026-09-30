param([string]$PythonExe, [int]$AgentHours = 8)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $labRoot
if (-not $PythonExe) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = (& py -3 -c 'import sys; print(sys.executable)').Trim()
    } else {
        $PythonExe = (Get-Command python -ErrorAction Stop).Source
    }
    & $PythonExe -c 'import sys; assert sys.version_info >= (3, 10)'
    if ($LASTEXITCODE -ne 0) { throw 'Se requiere Python 3.10 o posterior. Indica su ruta con -PythonExe.' }
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
$tunnelCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
$tunnelCandidates = @(
    $(if ($tunnelCommand) { $tunnelCommand.Source }),
    (Join-Path ${env:ProgramFiles(x86)} 'cloudflared\cloudflared.exe'),
    (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe'),
    (Join-Path $labRoot '.local\bin\cloudflared.exe')
)
$tunnelExe = $tunnelCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $tunnelExe) { throw 'Instala cloudflared con winget install --id Cloudflare.cloudflared -e --source winget.' }
# Se conserva el tunel activo para no cambiar una URL ya compartida.
$tunnelProcess = $null
foreach ($candidate in $tunnelCandidates) {
    if ($candidate) { $tunnelProcess = Get-LabProcess '.local\tunnel.pid' $candidate }
    if ($tunnelProcess) { break }
}
if (-not $tunnelProcess) {
    # Cada reinicio obtiene otra URL; se conserva un registro por proceso.
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
Write-Host "Cloudflared disponible: $tunnelExe"
Write-Host 'Pipeline: https://github.com/jorgefprietol/devops-exercise/actions'
Write-Host 'El agente atiende despliegues durante la sesion configurada; el servicio depende del PC y Docker.'
