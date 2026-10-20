param([string]$Bound = 'runs/plans/formal-v1-001-resume-02.json')
$ErrorActionPreference = 'Stop'
$hostRepo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = '/home/trustgate/.local/share/trustgate-env/bin/python'
$linuxRepo = '/home/trustgate/TrustGate'
$runtimeEnv = @('env', 'PYTHONHASHSEED=0', 'TOKENIZERS_PARALLELISM=false',
    'OMP_NUM_THREADS=2', 'MKL_NUM_THREADS=2',
    'TRUSTGATE_KEY_FILE=/home/trustgate/.secrets/openrouter_group9.key')
$publicNames = @('results.csv', 'receipt.json', 'platform_receipt.json', 'recovery_receipt.json',
    'ENVIRONMENT.md', 'analysis.json', 'ANALYSIS.md')
$destination = Join-Path $hostRepo 'experiments/deliveries/person-03'
$statusPath = Join-Path $hostRepo 'runs/person03-live-status.json'
$statusDirectory = Split-Path -Parent $statusPath
New-Item -ItemType Directory -Path $statusDirectory -Force | Out-Null
$statusDrive = $statusPath.Substring(0,1).ToLowerInvariant()
$linuxStatusPath = '/mnt/' + $statusDrive + $statusPath.Substring(2).Replace('\','/')
foreach ($name in $publicNames) {
    if (Test-Path -LiteralPath (Join-Path $destination $name)) {
        throw "Public file already exists; review before another launch: $name"
    }
}
if (-not ('TrustGateRecoveryPower' -as [type])) {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class TrustGateRecoveryPower { [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags); }'
}
$powerResult = [TrustGateRecoveryPower]::SetThreadExecutionState([uint32]2147483649)
if ($powerResult -eq 0) { throw 'Could not request system awake state.' }
try {
    @{state='starting'; observed_at_utc=[DateTime]::UtcNow.ToString('o'); bound=$Bound} | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
    & wsl.exe -d Ubuntu-22.04 -u trustgate --cd $linuxRepo -- @runtimeEnv $python tasks/03/resume.py execute --bound $Bound --status-file $linuxStatusPath
    if ($LASTEXITCODE -ne 0) { throw "Recovery stopped (exit $LASTEXITCODE); inspect the private summary. No automatic retry." }
    $linuxPublic = '\\wsl.localhost\Ubuntu-22.04\home\trustgate\TrustGate\experiments\deliveries\person-03'
    if (-not (Test-Path -LiteralPath (Join-Path $linuxPublic 'recovery_receipt.json'))) {
        Write-Output 'No final delivery exported; inspect live status for pause or unresolved-cost review.'
        return
    }
    foreach ($name in $publicNames) {
        if (-not (Test-Path -LiteralPath (Join-Path $linuxPublic $name))) {
            throw "Export/analysis incomplete: $name"
        }
    }
    foreach ($name in $publicNames) {
        Copy-Item -LiteralPath (Join-Path $linuxPublic $name) -Destination (Join-Path $destination $name)
    }
    Write-Output 'Complete: seven public delivery/analysis files copied to Windows. No commit or merge performed.'
} finally {
    [void][TrustGateRecoveryPower]::SetThreadExecutionState([uint32]2147483648)
    $lastStatus = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    if ($lastStatus.state -in @('starting','running')) {
        $lastStatus.state = 'launcher_stopped'
        $lastStatus.observed_at_utc = [DateTime]::UtcNow.ToString('o')
        $lastStatus | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
    }
}
