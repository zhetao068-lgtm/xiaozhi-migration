param([switch]$CheckFilesOnly)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:NO_COLOR = '1'
$script:BackupPath = $null

function Assert-Sha256([string]$Path, [string]$Expected) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "缺少文件 $Path。请保留烧录文件夹里的所有文件。"
    }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected) {
        throw "文件校验失败 $Path。请换回项目里的原文件。"
    }
}

function Get-TargetPort {
    $ports = @(Get-CimInstance -ClassName Win32_PnPEntity -Filter "PNPClass = 'Ports' AND Present = TRUE" |
        Where-Object {
            $_.ConfigManagerErrorCode -eq 0 -and $_.PNPDeviceID -match '^USB\\VID_303A&PID_1001(?:&|\\)' -and
                $_.Name -match '\((COM[0-9]+)\)\s*$'
        })
    if ($ports.Count -eq 0) {
        throw '没有检测到小智的乐鑫 USB 端口。拔掉 USB、拨到关机，接上能传数据的 USB 线，按住 BOOT 再拨到开机。'
    }
    if ($ports.Count -ne 1) {
        throw '发现多个乐鑫 USB 端口。请拔掉其他 ESP32 设备，只保留这一台小智。'
    }
    $port = $ports[0]
    $name = [regex]::Match($port.Name, '\((COM[0-9]+)\)\s*$', 'IgnoreCase').Groups[1].Value
    return [pscustomobject]@{ Port = $name; InstanceId = $port.PNPDeviceID }
}

function Assert-SameDevice($Original) {
    $current = Get-TargetPort
    if ($current.Port -ne $Original.Port -or $current.InstanceId -ne $Original.InstanceId) {
        throw 'USB 端口或设备发生变化，已停止。'
    }
}

function Invoke-Esptool([string]$Tool, [string[]]$Arguments) {
    $ErrorActionPreference = 'Continue'
    $lines = @(& $Tool @Arguments 2>&1)
    $code = $LASTEXITCODE
    $output = ($lines | ForEach-Object { $_.ToString() }) -join "`n"
    if ($output) { Write-Host $output }
    if ($code -ne 0) {
        throw "乐鑫工具执行失败（代码 $code）。请检查 USB 数据线、下载模式以及上面的提示。"
    }
    return $output
}

function Invoke-XminiFlash([string]$Tool, [string]$Firmware, [string]$LocalFolder) {
    $device = Get-TargetPort
    Write-Host "检测到 $($device.Port)。请对照外壳或订单，必须是原版 Xmini-C3 普通 Wi-Fi 版。V3、4G 和只知道芯片是 C3 的板请退出。"
    Write-Host '只在需要恢复或刷机时使用。官方固件会在启动时永久设置一项芯片配置，错刷可能损坏其他板型。'
    Write-Host '确认后将备份原机，再刷官方小智 v2.5.2。烧完要重新填 Wi-Fi。'
    $answer = Read-Host '已按订单和实物确认是原版，输入 XMINI-C3 后回车。其他输入取消'
    if ($answer.Trim() -ine 'XMINI-C3') {
        Write-Host '已取消。'
        return
    }

    Assert-SameDevice $device
    $connection = @('--chip', 'esp32c3', '--port', $device.Port, '--before', 'default-reset', '--after', 'no-reset')
    $security = Invoke-Esptool $Tool ($connection + @('--no-stub', 'get-security-info'))
    if ($security -notmatch '(?m)^Chip ID:\s*5\s*$' -or
        $security -notmatch '(?m)^Secure Boot:\s*Disabled\s*$' -or
        $security -notmatch '(?m)^Flash Encryption:\s*Disabled\s*$' -or
        $security -match 'Secure Download Mode') {
        throw '没有确认到可正常烧录的 ESP32-C3，或设备启用了安全启动、Flash 加密或安全下载模式。请联系卖家。'
    }

    $connection += @('--baud', '460800')
    $flash = Invoke-Esptool $Tool ($connection + @('flash-id'))
    if ($flash -notmatch '(?m)^Detected flash size:\s*16\s*MB\s*$') {
        throw 'Flash 容量不是预期的 16 MB，已停止。'
    }

    $backupFolder = Join-Path $LocalFolder 'Backups'
    [void](New-Item -ItemType Directory -Path $backupFolder -Force)
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $backupPath = Join-Path $backupFolder "Xmini-C3-$stamp-$($device.Port).bin"
    if (Test-Path -LiteralPath $backupPath) { throw '备份文件名冲突，请重新启动。' }
    Write-Host '正在备份原机，可能需要几分钟，请保持 USB 连接。'
    Assert-SameDevice $device
    [void](Invoke-Esptool $Tool ($connection + @('read-flash', '0x0', '0x1000000', $backupPath)))
    if ((Get-Item -LiteralPath $backupPath).Length -ne 0x1000000) {
        throw '原机备份不是完整的 16 MB，已停止。'
    }
    $backupHash = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$backupPath.sha256" -Value "$backupHash  $([IO.Path]::GetFileName($backupPath))" -Encoding ASCII
    $script:BackupPath = $backupPath
    Write-Host "原机备份已保存 $backupPath"

    Assert-SameDevice $device
    Write-Host '正在写入官方固件，请保持 USB 连接。'
    $keep = @('--flash-mode', 'keep', '--flash-size', 'keep', '--flash-freq', 'keep')
    [void](Invoke-Esptool $Tool ($connection + @('write-flash') + $keep + @('0x0', $Firmware)))
    Assert-SameDevice $device
    Write-Host '正在读回校验。'
    [void](Invoke-Esptool $Tool ($connection + @('verify-flash') + $keep + @('0x0', $Firmware)))
    Write-Host '烧录和读回校验通过。拔掉 USB，松开 BOOT，把电源开关拨到关再拨到开，然后配网。' -ForegroundColor Green
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        $firmware = Join-Path $PSScriptRoot '../../固件与源码/merged-binary.bin'
        $tool = Join-Path $PSScriptRoot '../../手表方案/固件/C6-直接烧录/esptool.exe'
        Assert-Sha256 $firmware '2178e8cefceac607e914d345a986600d48c49e4bca196b1cd02e4fb0d59913c7'
        Assert-Sha256 $tool '7a4fc0b651197d8034dab52db1468ebf5c009d8e754306e59c7de0aa47767914'
        if ($CheckFilesOnly) {
            Write-Host '小智官方 BIN 和乐鑫 esptool 校验通过。'
            exit 0
        }

        $localFolder = Join-Path $env:LOCALAPPDATA 'Xiaozhi-Xmini-C3'
        [void](New-Item -ItemType Directory -Path $localFolder -Force)
        $lock = [IO.File]::Open((Join-Path $localFolder 'flash.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        try {
            Invoke-XminiFlash $tool $firmware $localFolder
        } finally {
            $lock.Dispose()
        }
        exit 0
    } catch {
        Write-Host ("烧录未完成。{0}" -f $_.Exception.Message) -ForegroundColor Red
        if ($script:BackupPath) { Write-Host "可用的原机备份 $script:BackupPath" }
        exit 1
    }
}
