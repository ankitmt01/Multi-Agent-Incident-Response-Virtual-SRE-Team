# validate.ps1  — PowerShell-native validation

$ErrorActionPreference = "Stop"
$Base = "http://localhost:8000"

# (Optional) Make sure synthetic metrics exist inside the API container
Push-Location .\infra
docker compose exec api bash -lc "python -m app.scripts.generate_fixtures payments"
Pop-Location

# Build request body as JSON
$Body = @{
  service = "payments"
  signals = @(
    @{ source="metrics"; label="http_5xx_rate"; value=12 },
    @{ source="metrics"; label="latency_p95"; value=1200; unit="ms" }
  )
  suspected_cause = "bad deploy"
} | ConvertTo-Json -Depth 6

# 1) Detect
$det = Invoke-RestMethod -Uri "$Base/incidents/detect" -Method POST -ContentType "application/json" -Body $Body
Write-Host "Detected incident $($det.id) | severity=$($det.severity)"

# 2) Run full pipeline (investigator + remediator + policy guard + validator + report)
$run = Invoke-RestMethod -Uri "$Base/incidents/$($det.id)/run" -Method POST
$reportPath = "report_$($det.id).md"
$run.report_md | Out-File -FilePath $reportPath -Encoding utf8
Write-Host "Report saved to $reportPath"

# 3) Inspect structured results
$inc = Invoke-RestMethod -Uri "$Base/incidents/$($det.id)" -Method GET

Write-Host "`nCandidates (policy):"
$inc.remediation_candidates | ForEach-Object {
  $reasons = ($_.policy_reasons -join '; ')
  Write-Host ("- {0} | {1} | {2}" -f $_.name, $_.policy_status, $reasons)
}

Write-Host "`nValidation results:"
$inc.validation_results | ForEach-Object {
  $status = if ($_.passed) { "PASSED" } else { "FAILED" }
  Write-Host ("* {0}: {1} | err {2}→{3}, p95 {4}→{5}" -f $_.candidate, $status, `
    $_.kpi_before.error_rate, $_.kpi_after.error_rate, `
    $_.kpi_before.latency_p95, $_.kpi_after.latency_p95)
}
