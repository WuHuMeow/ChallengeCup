$repoRoot = Split-Path -Parent $PSScriptRoot
$candidates = @(
  (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$python = $candidates |
  Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
  Select-Object -First 1
if (-not $python) {
  Write-Error "Project Python not found. Create .venv and install requirements-dev.txt."
  exit 2
}

$previous = Get-Location
$exitCode = 2
try {
  Set-Location -LiteralPath $repoRoot
  $launcherArgs = @($args)
  $guiModeSpecified = $launcherArgs | Where-Object {
    "$_" -eq "--gui-mode" -or "$_" -like "--gui-mode=*"
  }
  if (($env:OS -eq "Windows_NT") -and (-not $guiModeSpecified)) {
    $launcherArgs = @("--gui-mode", "native") + $launcherArgs
  }
  & $python (Join-Path $PSScriptRoot "run_judge.py") @launcherArgs
  $exitCode = $LASTEXITCODE
} finally {
  Set-Location -LiteralPath $previous
}
exit $exitCode
