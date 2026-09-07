# 摄像头修复脚本（需管理员）：诊断 + 重启设备（只读诊断，不改注册表）
$ErrorActionPreference = 'Continue'
Set-Content -Path 'C:\Users\Mingya\fix_marker.txt' -Value ('started ' + (Get-Date))
try {
$log = 'C:\Users\Mingya\fix_camera_log.txt'
Remove-Item $log -ErrorAction SilentlyContinue
Start-Transcript -Path $log -Force
$id = 'USB\VID_5986&PID_1176&MI_00\6&5EF2E5A&1&0000'
$cls = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}'

Write-Output '=== 1. Camera class filters ==='
try {
    $root = Get-ItemProperty $cls -ErrorAction Stop
    Write-Output ("class-root UpperFilters: " + ($root.UpperFilters -join ','))
    Write-Output ("class-root LowerFilters: " + ($root.LowerFilters -join ','))
    Get-ChildItem $cls | ForEach-Object {
        $p = Get-ItemProperty $_.PSPath
        if ($p.UpperFilters -or $p.LowerFilters) {
            Write-Output ("  subkey " + $_.PSChildName + ": Upper=[" + ($p.UpperFilters -join ',') + "] Lower=[" + ($p.LowerFilters -join ',') + "]")
        }
    }
} catch { Write-Output ("read class failed: " + $_.Exception.Message) }

Write-Output '=== 2. Device enum config ==='
try {
    $devkey = "HKLM:\SYSTEM\CurrentControlSet\Enum\$id"
    $dev = Get-ItemProperty $devkey -ErrorAction Stop
    Write-Output ("Driver: " + $dev.Driver)
    if ($dev.Driver) {
        $drvkey = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\" + $dev.Driver
        $drv = Get-ItemProperty $drvkey -ErrorAction SilentlyContinue
        if ($drv) {
            Write-Output ("  MatchingDeviceId: " + $drv.MatchingDeviceId)
            Write-Output ("  Service: " + $drv.Service)
            Write-Output ("  UpperFilters: " + ($drv.UpperFilters -join ','))
            Write-Output ("  LowerFilters: " + ($drv.LowerFilters -join ','))
        }
    }
} catch { Write-Output ("read enum failed: " + $_.Exception.Message) }

Write-Output '=== 3. Restart device ==='
pnputil /restart-device "$id"
Start-Sleep -Seconds 3
$d = Get-PnpDevice -InstanceId $id -ErrorAction SilentlyContinue
Write-Output ("status after restart: " + $d.Status + " (problem " + $d.Problem + ")")

if ($d.Status -ne 'OK') {
    Write-Output '=== 4. Try disable/enable cycle ==='
    Disable-PnpDevice -InstanceId $id -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Enable-PnpDevice -InstanceId $id -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    $d = Get-PnpDevice -InstanceId $id -ErrorAction SilentlyContinue
    Write-Output ("status after disable/enable: " + $d.Status + " (problem " + $d.Problem + ")")
}
Write-Output '=== DONE ==='
Stop-Transcript
} catch {
    $_ | Out-File -FilePath 'C:\Users\Mingya\fix_camera_log.txt' -Append -Encoding utf8
}
Add-Content -Path 'C:\Users\Mingya\fix_marker.txt' -Value ('finished ' + (Get-Date))
