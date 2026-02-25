$ErrorActionPreference = 'Continue'
$cn = Get-NetTCPConnection -LocalPort 8500 -ErrorAction SilentlyContinue
if ($cn) {
    $pid = $cn.OwningProcess
    Write-Output ('Found pid {0}' -f $pid)
    Get-Process -Id $pid -ErrorAction SilentlyContinue | Format-List Id,ProcessName,Path
    try {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-Output ('killed {0}' -f $pid)
    } catch {
        Write-Output ('failed to kill {0}' -f $pid)
    }
} else {
    Write-Output 'no connection on port 8500'
}
