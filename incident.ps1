$body = @{
  service = "payments"
  signals = @(
    @{ source="metrics"; label="http_5xx_rate"; value=12 },
    @{ source="metrics"; label="latency_p95"; value=1200; unit="ms" }
  )
  suspected_cause = "bad deploy"
} | ConvertTo-Json -Depth 5

$det = Invoke-RestMethod -Uri "http://localhost:8000/incidents/detect" -Method POST -ContentType "application/json" -Body $body
$id = $det.id
$run = Invoke-RestMethod -Uri "http://localhost:8000/incidents/$id/run" -Method POST
$run.report_md | Out-Host
