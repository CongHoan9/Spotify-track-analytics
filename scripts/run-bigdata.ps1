param([switch]$SkipBuild, [switch]$DemoOnly)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker chưa chạy. Mở Docker Desktop và đợi Linux Engine sẵn sàng.' }
if (-not $SkipBuild -and -not $DemoOnly) {
    $builder = (docker context show).Trim()
    docker build --builder $builder -t spotify-bigdata:local -f docker/bigdata.Dockerfile .
    if ($LASTEXITCODE -ne 0) { throw 'Build thất bại' }
}
docker compose -f compose.bigdata.yaml up -d master worker-1 worker-2 dashboard history
if ($LASTEXITCODE -ne 0) { throw 'Không khởi động được cluster' }
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $state = Invoke-RestMethod 'http://localhost:8080/json/'
        if (@($state.workers | Where-Object state -eq 'ALIVE').Count -ge 2) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'Chưa đủ hai worker đăng ký. Kiểm tra docker compose logs.' }
New-Item -ItemType Directory -Force reports/bigdata | Out-Null
if ($DemoOnly -and -not (Test-Path reports/bigdata/summary.json)) {
    throw 'Chưa có kết quả. Chạy script không có -DemoOnly trước buổi bảo vệ.'
}
if (-not $DemoOnly) {
docker compose -f compose.bigdata.yaml run --rm --no-deps analysis python tests/test_bigdata_quality.py
if ($LASTEXITCODE -ne 0) { throw 'Kiểm thử hợp đồng dữ liệu thất bại' }
$ErrorActionPreference = 'Continue'
docker compose -f compose.bigdata.yaml run --rm --use-aliases analysis 2>&1 | Tee-Object reports/bigdata/pipeline.log
$jobExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($jobExit -ne 0) { throw 'Pipeline lỗi; xem reports/bigdata/pipeline.log' }
}
docker compose -f compose.bigdata.yaml run --rm --no-deps analysis python scripts/verify_bigdata.py
if ($LASTEXITCODE -ne 0) { throw 'Kết quả chưa vượt qua bước kiểm tra nghiệm thu' }
Write-Host 'Hoàn tất. Dashboard: http://localhost:8050 | Spark: http://localhost:8080 | History: http://localhost:18080'
