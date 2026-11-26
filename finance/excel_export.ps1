# Excel desktop automation: creates a NEW workbook from the local pilot's verified report.
# Does not attach to a user's existing Excel session or modify existing workbooks.
param([string]$Workspace = (Join-Path $HOME "Neuravale-finance-desktop-demo"), [string]$FinanceExecutable = "")
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if ($FinanceExecutable) {
    $json = & $FinanceExecutable --office --workspace $Workspace status
    if ($LASTEXITCODE -ne 0) { throw "Cannot read packaged office report." }
} else {
    if (-not (Test-Path -LiteralPath $python)) { throw "Python environment missing." }
    Push-Location -LiteralPath $repo
    try {
        $json = & $python -m finance.office --workspace $Workspace status
        if ($LASTEXITCODE -ne 0) { throw "Cannot read office report." }
    } finally { Pop-Location }
}
$snapshot = ($json -join [Environment]::NewLine) | ConvertFrom-Json
if ($null -eq $snapshot -or $snapshot.state -ne "complete") { throw "No successful office report. Generate fictional data and let the worker process it first." }
$r = $snapshot.report
$folder = Join-Path $Workspace "reports"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$path = Join-Path $folder ("Neuravale-office-" + [Guid]::NewGuid().ToString("N") + ".xlsx")
$excel = $null
$book = $null
$sheet = $null
function Put-Text($row,$col,$value) {
    $cell = $sheet.Cells.Item($row,$col)
    try { $cell.NumberFormat = "@"; $cell.Value2 = "'" + [string]$value } finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($cell) }
}
function Put-Money($row,$col,$cents) {
    $cell = $sheet.Cells.Item($row,$col)
    try { $cell.NumberFormat = '#,##0.00;[Red](#,##0.00)'; $cell.Value2 = [double]$cents / 100 } finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($cell) }
}
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $true
    $excel.DisplayAlerts = $false
    $excel.AutomationSecurity = 3
    $book = $excel.Workbooks.Add()
    $sheet = $book.Worksheets.Item(1)
    $sheet.Name = "Office report"
    Put-Text 1 1 "NEURAVALE FINANCE - FICTIONAL PILOT"
    Put-Text 2 1 $r.company
    Put-Text 3 1 ("Snapshot " + $r.snapshot_date + " | Report " + $r.report_date)
    Put-Text 4 1 "CAD; not financial statements or tax advice"
    Put-Text 6 1 "Account"
    Put-Text 6 2 "Debit CAD"
    Put-Text 6 3 "Credit CAD"
    $i=7
    foreach ($a in $r.accountant.trial_balance) {
        Put-Text $i 1 $a.account
        Put-Money $i 2 $a.debit_cents
        Put-Money $i 3 $a.credit_cents
        $i++
    }
    Put-Text $i 1 "Trial balance total"
    Put-Money $i 2 $r.accountant.total_debit_cents
    Put-Money $i 3 $r.accountant.total_credit_cents
    $i+=2
    foreach ($entry in @(
        @("Open receivables",$r.receivables.total_cents),
        @("Open payables",$r.payables.total_cents),
        @("Snapshot cash",$r.treasury.snapshot_cash_cents),
        @("Illustrative 30-day ending cash",$r.treasury.illustrative_ending_cash_cents)
    )) {
        Put-Text $i 1 $entry[0]; Put-Money $i 2 $entry[1]; $i++
    }
    Put-Text ($i+1) 1 $r.treasury.note
    $sheet.Columns.Item(1).ColumnWidth=50
    $sheet.Columns.Item(2).ColumnWidth=19
    $sheet.Columns.Item(3).ColumnWidth=19
    $book.SaveAs($path,51)
    if (-not (Test-Path -LiteralPath $path)) { throw "Excel did not save the workbook." }
    Write-Host "Excel saved: $path"
} finally {
    if ($null -ne $book) { $book.Close($false) }
    if ($null -ne $excel) { $excel.Quit() }
    foreach ($obj in @($sheet,$book,$excel)) {
        if ($null -ne $obj) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($obj) }
    }
}
