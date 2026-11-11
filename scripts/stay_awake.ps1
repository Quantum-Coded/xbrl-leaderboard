# Ask Windows not to idle-sleep while the batch runs (SetThreadExecutionState; no settings changed).
param([string]$Log = "results/logs/batch_s0.log")
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
$ES = [uint32]"0x80000001"   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
while (-not (Select-String -Path $Log -Pattern "BATCH DONE" -Quiet)) { [W.P]::SetThreadExecutionState($ES) | Out-Null; Start-Sleep 60 }
[W.P]::SetThreadExecutionState([uint32]"0x80000000") | Out-Null
