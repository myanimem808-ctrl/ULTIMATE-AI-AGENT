$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run install.bat first.' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
& '.venv\Scripts\python.exe' 'main.py'
