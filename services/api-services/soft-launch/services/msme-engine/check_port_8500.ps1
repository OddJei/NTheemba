$c = Get-NetTCPConnection -LocalPort 8500 -ErrorAction SilentlyContinue
if ($c) {
    $c | Format-List *
} else {
    Write-Output 'no connection on port 8500'
}
