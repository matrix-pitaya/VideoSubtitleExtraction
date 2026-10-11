$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '请安装 Python 3.11 或 3.12，并勾选 Python Launcher。' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络。' }
& '.\.venv\Scripts\python.exe' -m streamlit run app.py --server.address 127.0.0.1
