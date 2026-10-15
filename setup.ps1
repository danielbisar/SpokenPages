$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 with the Python launcher is required.' }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
    & .\.venv\Scripts\python.exe -m pip install torch==2.14.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu126
    if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
    & .\.venv\Scripts\python.exe -m pip install -c constraints-windows.txt -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & .\.venv\Scripts\python.exe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency integrity check failed. See docs/troubleshooting.md.' }
    & .\.venv\Scripts\python.exe -c "import tkinter, torch, torchaudio, soundfile, triton; from voxcpm import VoxCPM; print('Dependency imports passed; no model loaded.')"
    if ($LASTEXITCODE -ne 0) { throw 'Dependency import check failed. See docs/troubleshooting.md.' }
    & .\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 .\.venv\installed-packages.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not record installed packages.' }
    Write-Host 'Setup complete. Run .\start.ps1.'
} finally {
    Pop-Location
}
