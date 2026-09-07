# 摄像头修复第二步：移除残留的 360Camera 过滤驱动（先备份）
$ErrorActionPreference = 'Continue'
Set-Content -Path 'C:\Users\Mingya\fix_marker.txt' -Value ('started ' + (Get-Date))
try {
$log = 'C:\Users\Mingya\fix_camera_log.txt'
Remove-Item $log -ErrorAction SilentlyContinue
Start-Transcript -Path $log -Force
$cls = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}'
$id = 'USB\VID_5986&PID_1176&MI_00\6&5EF2E5A&1&0000'

Write-Output '=== 0. Backup class key ==='
reg export 'HKLM\SYSTEM\CurrentControlSet\Control\Class\{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}' 'C:\Users\Mingya\camera_class_backup.reg' /y
Write-Output ("backup exit: " + $LASTEXITCODE)

Write-Output '=== 1. 360Camera service state ==='
$svc = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\360Camera' -ErrorAction SilentlyContinue
if ($svc) {
    Write-Output ("ImagePath: " + $svc.ImagePath)
    Write-Output ("Start: " + $svc.Start)
    if ($svc.ImagePath) {
        $sysfile = ($svc.ImagePath -replace '^\\\?\?\\','') -replace '"',''
        Write-Output ("sys file exists: " + (Test-Path $sysfile) + "  ($sysfile)")
    }
} else { Write-Output 'service key 360Camera not found (stale filter confirmed)' }

Write-Output '=== 2. 360 processes ==='
$p = Get-Process | Where-Object { $_.Name -match '360|ZhuDongFangYu' } | Select-Object Name, Id
if ($p) { $p | Format-Table -AutoSize | Out-String | Write-Output } else { Write-Output 'no 360 process running' }

Write-Output '=== 3. Driver key detail ==='
$drv = Get-ItemProperty ($cls + '\0000') -ErrorAction SilentlyContinue
Write-Output ("Service: [" + $drv.Service + "]  Provider: " + $drv.ProviderName + "  DriverDate: " + $drv.DriverDate)
Write-Output ("usbvideo service exists: " + [bool](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\usbvideo' -ErrorAction SilentlyContinue))

Write-Output '=== 4. Remove 360Camera from UpperFilters (keep ksthunk) ==='
$cur = (Get-ItemProperty $cls).UpperFilters
Write-Output ("before: " + ($cur -join ','))
$new = @($cur | Where-Object { $_ -ne '360Camera' })
Set-ItemProperty -Path $cls -Name UpperFilters -Value $new
Write-Output ("after: " + ((Get-ItemProperty $cls).UpperFilters -join ','))

Write-Output '=== 5. Restart device ==='
pnputil /restart-device "$id"
Start-Sleep -Seconds 3
$d = Get-PnpDevice -InstanceId $id -ErrorAction SilentlyContinue
Write-Output ("status after fix: " + $d.Status + " (problem " + $d.Problem + ")")

Write-Output '=== DONE ==='
Stop-Transcript
} catch {
    $_ | Out-File -FilePath 'C:\Users\Mingya\fix_camera_log.txt' -Append -Encoding utf8
}
Add-Content -Path 'C:\Users\Mingya\fix_marker.txt' -Value ('finished ' + (Get-Date))
