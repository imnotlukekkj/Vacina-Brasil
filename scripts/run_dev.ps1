<#
run_dev.ps1 — inicia backend (uvicorn) e frontend (vite) para desenvolvimento local no Windows PowerShell
Uso: .\run_dev.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# garante que o script rode a partir da pasta do repositório
Set-Location $PSScriptRoot

Write-Host '[run_dev.ps1] garantindo venv (preferência por py -3.11)...'

# checa se o lançador py suporta -3.11
$py311Available = $false
try {
    & py -3.11 -V > $null 2>&1
    $py311Available = $true
} catch {
    $py311Available = $false
}

if (-not (Test-Path ".venv")) {
    if ($py311Available) {
        Write-Host '[run_dev.ps1] criando .venv com py -3.11'
        & py -3.11 -m venv .venv
    } else {
        Write-Host '[run_dev.ps1] criando .venv com python do PATH'
        & python -m venv .venv
    }
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host '[run_dev.ps1] Aviso: não encontrei .venv\Scripts\python.exe — usando python/py diretamente'
    if ($py311Available) { $venvPython = 'py -3.11' } else { $venvPython = 'python' }
}

Write-Host '[run_dev.ps1] instalando dependências Python...'
try {
    if (Test-Path $venvPython) {
        & $venvPython -m pip install --upgrade pip
        & $venvPython -m pip install -r backend/requirements.txt
    } else {
        # se $venvPython for string com launcher (ex: 'py -3.11')
        if ($venvPython -match 'py') {
            & py -3.11 -m pip install --upgrade pip
            & py -3.11 -m pip install -r backend/requirements.txt
        } else {
            & python -m pip install --upgrade pip
            & python -m pip install -r backend/requirements.txt
        }
    }
} catch {
    Write-Host 'Erro ao instalar dependências Python:' $_ -ForegroundColor Yellow
}

Write-Host '[run_dev.ps1] iniciando backend (uvicorn) em nova janela para logs...'
$rootPath = (Get-Location).Path

# monta comando que será executado na nova janela PowerShell
if (Test-Path (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')) {
    $pythonExe = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -replace "\\","\\\\"
    $uvicornCmd = "& '$pythonExe' -m uvicorn backend.app:app --reload --reload-dir backend --port 8000"
} else {
    if ($py311Available) {
        $uvicornCmd = "& py -3.11 -m uvicorn backend.app:app --reload --reload-dir backend --port 8000"
    } else {
        $uvicornCmd = "& python -m uvicorn backend.app:app --reload --reload-dir backend --port 8000"
    }
}

# abre nova janela PowerShell com -NoExit para manter visível
$uvicornProc = Start-Process powershell -ArgumentList ('-NoExit','-Command',$uvicornCmd) -PassThru
Write-Host "[run_dev.ps1] backend ProcessId=$($uvicornProc.Id)"

Write-Host '[run_dev.ps1] escrevendo .env.local para o frontend...'
"VITE_API_BASE_URL=http://localhost:8000" | Out-File -Encoding UTF8 .env.local

try {
    Write-Host '[run_dev.ps1] iniciando frontend (npm install)...'
    cmd /c "npm install"

    Write-Host '[run_dev.ps1] iniciando frontend (npm run dev)...'
    cmd /c "npm run dev"
} finally {
    Write-Host ("[run_dev.ps1] frontend saiu - encerrando backend (process id {0})..." -f $uvicornProc.Id)
    try {
        if ($uvicornProc -and ($uvicornProc.HasExited -eq $false)) {
            Stop-Process -Id $uvicornProc.Id -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host 'Erro ao encerrar backend:' $_ -ForegroundColor Yellow
    }
}
