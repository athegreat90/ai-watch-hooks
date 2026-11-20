param([switch]$Uninstall)
. "$PSScriptRoot/common.ps1"
$arguments = @("$Root/bridge/install.py")
if ($Uninstall) { $arguments += '--uninstall' }
Invoke-Checked python $arguments
