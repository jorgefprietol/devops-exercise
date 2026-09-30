param([string]$BaseUrl,
    [ValidateSet('production','staging','development')][string]$Environment = 'production')
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $labRoot
$arguments = @('scripts/test_environment.py', $Environment)
if ($BaseUrl) { $arguments += @('--url', $BaseUrl) }
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 @arguments }
else { & python @arguments }
if ($LASTEXITCODE -ne 0) { throw 'La comprobacion publica no fue satisfactoria.' }
