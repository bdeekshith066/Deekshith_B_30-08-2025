$response   = Invoke-RestMethod -Uri http://127.0.0.1:8000/trigger_report -Method Post
$REPORT_ID  = $response.report_id
"REPORT_ID=$REPORT_ID"

while ($true) {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/get_report?report_id=$REPORT_ID" -Method Get -PassThru
  if ($r.ContentType -like 'text/plain*') {
    $r.Content.Trim()
    Start-Sleep -Seconds 1
  } else {
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/get_report?report_id=$REPORT_ID" -OutFile "report_$REPORT_ID.csv"
    "Saved report_$REPORT_ID.csv"
    break
  }
}
