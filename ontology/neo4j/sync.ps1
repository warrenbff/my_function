$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& (Join-Path $root '.cache/neo4j-venv/Scripts/python.exe') (Join-Path $root 'scripts/sync_neo4j.py') @args
if ($LASTEXITCODE -ne 0) { throw 'Neo4j sync failed. Check that the server is running.' }
