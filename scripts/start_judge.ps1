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
  & $python (Join-Path $PSScriptRoot "run_judge.py") @args
  $exitCode = $LASTEXITCODE
} finally {
  Set-Location -LiteralPath $previous
}
exit $exitCode
