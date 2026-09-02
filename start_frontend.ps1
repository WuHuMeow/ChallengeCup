$launcher = Join-Path $PSScriptRoot "scripts\start_judge.ps1"
& $launcher @args
exit $LASTEXITCODE
