param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Status','Sync','Check','CheckKey','Test','Offline','SetKey','Run','Export')]
    [string]$Action,
    [string]$RunId = 'formal-v1-001'
)
$ErrorActionPreference = 'Stop'
$distro = 'Ubuntu-22.04'
$linuxUser = 'trustgate'
$linuxRepo = '/home/trustgate/TrustGate'
$python = '/home/trustgate/.local/share/trustgate-env/bin/python'
$detector = "$linuxRepo/models/prompt_injection_detector"
$privateKey = '/home/trustgate/.secrets/openrouter_group9.key'

function Invoke-Linux([string[]]$Arguments) {
    & wsl.exe -d $distro -u $linuxUser --cd $linuxRepo -- @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Linux command failed (exit $LASTEXITCODE)." }
}

$runtimeEnv = @('env','PYTHONHASHSEED=0','TOKENIZERS_PARALLELISM=false',
    'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2',"TRUSTGATE_KEY_FILE=$privateKey")

switch ($Action) {
    'Status' {
        Invoke-Linux ($runtimeEnv + @($python,'--version'))
        Invoke-Linux -Arguments @('git','status','--short','--branch')
    }
    'Sync' {
        # Copy only the explicitly named adaptation files, never frozen sources,
        # environment files, run directories or credentials.
        $hostRepo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
        $windowsDrive = $hostRepo.Substring(0,1).ToLowerInvariant()
        $mountedRepo = '/mnt/' + $windowsDrive + $hostRepo.Substring(2).Replace('\','/')
        $syncCode = @'
import pathlib,shutil,sys
source=pathlib.Path(sys.argv[1]); target=pathlib.Path.cwd()
for path in (source/'scripts/platforms/local').iterdir():
    if path.is_file() and path.suffix in ('.py','.md','.ps1'):
        out=target/'scripts/platforms/local'/path.name
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
for name in ('tests/test_local_platform.py','tests/test_runner_isolation.py','tasks/03/PROGRESS.md','experiments/deliveries/person-03/.gitattributes'):
    (target/name).write_bytes((source/name).read_bytes().replace(b'\r\n',b'\n'))
print('Adaptation files synced; frozen sources and private runs untouched.')
'@
        Invoke-Linux -Arguments @($python,'-c',$syncCode,$mountedRepo)
    }
    'SetKey' {
        $secureKey = Read-Host 'Paste the authorized Group 9 API key (hidden)' -AsSecureString
        $plainKey = [System.Net.NetworkCredential]::new('', $secureKey).Password
        if ([string]::IsNullOrWhiteSpace($plainKey)) { throw 'Empty key was not saved.' }
        $saveCode = @'
import pathlib,os,sys
os.umask(0o077)
p=pathlib.Path(sys.argv[1]);p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
p.parent.chmod(0o700)
value=sys.stdin.read().strip()
if not value or '\n' in value or '\r' in value:raise SystemExit('Expected one nonempty credential line')
temp=p.with_suffix('.tmp');temp.write_text(value+'\n');temp.chmod(0o600);temp.replace(p)
print('Credential saved privately; value was not printed.')
'@
        try {
            $plainKey | & wsl.exe -d $distro -u $linuxUser -- $python -c $saveCode $privateKey
            if ($LASTEXITCODE -ne 0) { throw 'Saving the credential failed.' }
        } finally { $plainKey = $null; $secureKey.Dispose() }
    }
    'Check' { Invoke-Linux ($runtimeEnv + @($python,'scripts/platforms/local/run.py','--check','--detector-dir',$detector)) }
    'CheckKey' { Invoke-Linux ($runtimeEnv + @($python,'scripts/platforms/local/api_check.py')) }
    'Test' { Invoke-Linux ($runtimeEnv + @($python,'-m','unittest','discover','-s','tests','-v')) }
    'Offline' { Invoke-Linux ($runtimeEnv + @($python,'scripts/platforms/local/offline.py','--detector-dir',$detector)) }
    'Run' {
        if ($RunId -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$') { throw 'Invalid run ID.' }
        if (-not ('TrustGatePower' -as [type])) {
            Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class TrustGatePower { [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags); }'
        }
        [void][TrustGatePower]::SetThreadExecutionState([uint32]2147483649)
        try {
            Invoke-Linux ($runtimeEnv + @($python,'scripts/platforms/local/run.py','--execute','--detector-dir',$detector,'--run-id',$RunId))
        } finally { [void][TrustGatePower]::SetThreadExecutionState([uint32]2147483648) }
    }
    'Export' {
        if ($RunId -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$') { throw 'Invalid run ID.' }
        Invoke-Linux ($runtimeEnv + @($python,'scripts/platforms/local/delivery.py','export',
            '--worker-dir',"runs/studies/$RunId/shard-02",'--destination','experiments/deliveries/person-03'))
        # Copy the four public files only; raw traces and credentials stay on Linux.
        $hostRepo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
        $publicDir = Join-Path $hostRepo 'experiments/deliveries/person-03'
        foreach ($name in @('results.csv','receipt.json','platform_receipt.json','ENVIRONMENT.md')) {
            $destination = Join-Path $publicDir $name
            if (Test-Path -LiteralPath $destination) { throw "Refusing to overwrite $destination" }
        }
        foreach ($name in @('results.csv','receipt.json','platform_receipt.json','ENVIRONMENT.md')) {
            $source = "\\wsl.localhost\$distro\home\$linuxUser\TrustGate\experiments\deliveries\person-03\$name"
            Copy-Item -LiteralPath $source -Destination (Join-Path $publicDir $name)
        }
        Write-Output 'Public delivery copied to the Windows checkout. Review before committing.'
    }
}
