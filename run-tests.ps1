$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path .\.venv\Scripts\python.exe)) { throw 'Run .\setup.ps1 first. Python 3.12 is required.' }
    & .\.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Run .\setup.ps1.' }
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
