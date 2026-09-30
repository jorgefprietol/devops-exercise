param([string]$BaseUrl)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $labRoot
if (-not $BaseUrl) { $BaseUrl = (Get-Content '.local\public_urls.json' -Raw | ConvertFrom-Json).production }
if ($BaseUrl -notmatch '^https://') { throw 'Se requiere una URL HTTPS.' }
Get-Content -LiteralPath '.env' | ForEach-Object {
    if ($_ -match '^[A-Z_]+=') {
        $parts = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
    }
}
dotnet build tools/TokenIssuer -c Release --nologo --verbosity quiet
if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar TokenIssuer.' }
$jwt = dotnet tools/TokenIssuer/bin/Release/net8.0/TokenIssuer.dll
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el JWT.' }
$body = @{message='This is a test';to='Juan Perez';from='Rita Asturia';timeToLifeSec=45} | ConvertTo-Json -Compress
$reply = Invoke-RestMethod -Method Post -Uri ($BaseUrl.TrimEnd('/') + '/DevOps') -Headers @{'X-Parse-REST-API-Key'=$env:API_KEY;'X-JWT-KWY'=$jwt.Trim()} -ContentType 'application/json' -Body $body
$reply | ConvertTo-Json -Compress
