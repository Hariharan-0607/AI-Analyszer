# Project Submission AI Analyzer - Startup Script

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Checking Gemini API key..." -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$envContent = Get-Content .env -Raw
if ($envContent -notmatch 'GEMINI_API_KEY=\s*\S+' -or $envContent -match 'GEMINI_API_KEY=\s*your_gemini') {
  Write-Host "WARNING: Set GEMINI_API_KEY in backend\.env" -ForegroundColor Yellow
  Write-Host "  Get a free key: https://aistudio.google.com/apikey" -ForegroundColor Gray
} else {
  Write-Host "Gemini API key found in .env" -ForegroundColor Green
}

Write-Host "Building website..." -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install --silent
npm run build

Write-Host "Starting server on all network interfaces..." -ForegroundColor Cyan
Set-Location "$root\backend"

# Get local network IP
$ip = "127.0.0.1"
try {
    $socket = New-Object System.Net.Sockets.Socket([System.Net.Sockets.AddressFamily]::InterNetwork, [System.Net.Sockets.SocketType]::Dgram, [System.Net.Sockets.ProtocolType]::Udp)
    $socket.Connect("8.8.8.8", 80)
    $ip = $socket.LocalEndPoint.Address.ToString()
    $socket.Close()
} catch {}

Write-Host ""
Write-Host "Website URLs:" -ForegroundColor Green
Write-Host "  This PC:     http://localhost:8000" -ForegroundColor White
Write-Host "  Other devices: http://${ip}:8000" -ForegroundColor Yellow
Write-Host "  (Use the network URL on phones/tablets on the same Wi-Fi)" -ForegroundColor Gray
Write-Host ""

py -m pip install -r requirements.txt -q
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
