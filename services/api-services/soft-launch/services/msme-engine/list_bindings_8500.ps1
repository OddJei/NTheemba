$ErrorActionPreference='Continue'
$c = Get-NetTCPConnection -LocalPort 8500 -ErrorAction SilentlyContinue
if ($c) {
    foreach($conn in $c) {
        Write-Output ('LocalAddress: {0} LocalPort: {1} State: {2} OwningProcess: {3}' -f $conn.LocalAddress, $conn.LocalPort, $conn.State, $conn.OwningProcess)
        try { Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue | Format-List Id,ProcessName,Path } catch {}
    }
} else {
    Write-Output 'no connections on port 8500'
}
