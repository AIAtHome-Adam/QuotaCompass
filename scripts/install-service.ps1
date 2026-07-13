[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Install', 'Uninstall')]
    [string]$Action = 'Install',
    [string]$TaskName = 'QuotaCompass',
    [string]$ConfigPath,
    [string]$Command = 'quotacompass'
)

$ErrorActionPreference = 'Stop'

if ($Action -eq 'Uninstall') {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        if ($PSCmdlet.ShouldProcess($TaskName, 'Unregister scheduled task')) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
    }
    return
}

$resolvedCommand = (Get-Command $Command -ErrorAction Stop).Source
$arguments = @()
if ($ConfigPath) {
    $resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
    $arguments += @('--config', ('"{0}"' -f $resolvedConfig))
}
$arguments += 'serve'

$taskAction = New-ScheduledTaskAction `
    -Execute $resolvedCommand `
    -Argument ($arguments -join ' ')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal `
    -UserId ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME) `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

if ($PSCmdlet.ShouldProcess($TaskName, 'Register logon scheduled task')) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description 'Local-first QuotaCompass quota service' `
        -Action $taskAction `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null
}
