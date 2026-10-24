$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $root '.cache/neo4j'
$state = Get-Content -LiteralPath (Join-Path $runtime 'runtime.json') -Raw | ConvertFrom-Json
$env:JAVA_HOME = $state.java_home
$env:NEO4J_HOME = $state.home
$connection = Get-NetTCPConnection -LocalPort 7687 -State Listen -ErrorAction SilentlyContinue
if ($connection) {
    Write-Host 'Port 7687 already in use. Check http://127.0.0.1:7474/browser/'
    exit 0
}
$script = Join-Path $state.home 'bin/neo4j-admin.ps1'
$process = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $script + '"'), 'server', 'console') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'console.log') -RedirectStandardError (Join-Path $runtime 'console-error.log')
$process.Id | Set-Content -LiteralPath (Join-Path $runtime 'launcher.pid')
Write-Host 'Neo4j starting: http://127.0.0.1:7474/browser/'
Write-Host 'Login details: neo4j/local.json'
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    $process.Refresh()
    if ($process.HasExited) { throw 'Neo4j failed to start. Check .cache/neo4j/console-error.log.' }
    $ready = Get-NetTCPConnection -LocalPort 7687 -State Listen -ErrorAction SilentlyContinue
} until ($ready -or (Get-Date) -ge $deadline)
if (-not $ready) { throw 'Neo4j is still starting. Check logs before running sync.' }
Write-Host 'Neo4j Bolt is ready.'
