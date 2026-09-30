param([string]$PythonExe, [int]$AgentHours = 8,
    [ValidateSet('production','staging','development')][string]$Environment = 'production')
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
$port = @{production=9443;staging=9444;development=9445}[$Environment]
if ($Environment -ne 'production') {
    $forwardPid = ".local/forward-$Environment.pid"
    if (-not (Get-LabProcess $forwardPid $PythonExe)) {
        $forward = Start-Process -FilePath $PythonExe -ArgumentList @('-X','utf8','-u','scripts/local_port_forward.py',$Environment) -WorkingDirectory $labRoot -WindowStyle Hidden -RedirectStandardOutput ".local/forward-$Environment.log" -RedirectStandardError ".local/forward-$Environment-error.log" -PassThru
        $forward.Id | Set-Content $forwardPid
    }
}
& $PythonExe scripts/public_tunnel.py $Environment
if ($LASTEXITCODE -ne 0) { throw 'No se pudo publicar y verificar el entorno. Revisa los pods public-tunnel y Kong.' }
$publicUrl = (Get-Content '.local/public_urls.json' -Raw | ConvertFrom-Json).$Environment
$agentProcess = Get-LabProcess '.local\agent.pid' $PythonExe
if (-not $agentProcess) {
    $agentProcess = Start-Process -FilePath $PythonExe -ArgumentList @('-X','utf8','-u','scripts/local_deploy_agent.py','--hours',"$AgentHours") -WorkingDirectory $labRoot -WindowStyle Hidden -RedirectStandardOutput '.local/agent.log' -RedirectStandardError '.local/agent-error.log' -PassThru
    $agentProcess.Id | Set-Content '.local\agent.pid'
}
Write-Host "API publica ($Environment): $publicUrl/DevOps"
Write-Host 'Túnel Pinggy gratuito: hasta 60 minutos por URL. Repite este script para actualizarla.'
Write-Host 'Pipeline: https://github.com/jorgefprietol/devops-exercise/actions'
Write-Host 'El agente atiende despliegues durante la sesion configurada; el servicio depende del PC y Docker.'
