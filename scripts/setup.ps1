$ErrorActionPreference = 'Stop'

py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'

Write-Host 'Environment ready. Review the provider agreement, then run: district-context sources'
