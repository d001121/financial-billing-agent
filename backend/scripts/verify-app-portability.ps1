param(
    [string]$Archive,
    [string]$Destination,
    [int]$Port = 2025,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$backendRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$projectRoot = Split-Path -Parent $backendRoot
if (-not $Archive) { $Archive = Join-Path $projectRoot 'delivery/harbor-bishi1-windows-x64.zip' }
$archivePath = (Get-Item -LiteralPath $Archive).FullName
$artifactRoot = Join-Path $backendRoot ('.build/app-portability-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $artifactRoot -Force
if (-not $Destination) {
    # Keep the complete path short enough for a Windows host with long paths
    # disabled, including the original EML's long filename.
    $relocatedName = [string][char]0x8fc1 + [char]0x79fb + ' ' + [char]0x7a7a + [char]0x683c + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $Destination = Join-Path (Join-Path $backendRoot '.build') $relocatedName
}
$relocatedRoot = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $relocatedRoot) { throw 'Destination must be a new directory.' }
& (Join-Path $backendRoot 'python.cmd') -m zipfile -e $archivePath $relocatedRoot
if ($LASTEXITCODE -ne 0) { throw 'ZIP extraction with the bundled interpreter failed.' }
$outside = Join-Path $artifactRoot 'outside cwd'
$null = New-Item -ItemType Directory -Path $outside
$relocatedBackend = Join-Path $relocatedRoot 'backend'
$python = Join-Path $relocatedBackend 'bishi1/python.exe'
$checks = [Collections.Generic.List[object]]::new()
$server = $null
$reportPath = Join-Path $artifactRoot 'portability-report.json'
$report = [ordered]@{
    Archive = $archivePath
    ArchiveBytes = (Get-Item -LiteralPath $archivePath).Length
    ArchiveSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    RelocatedRoot = $relocatedRoot
    RelocatedBackend = $relocatedBackend
    ExternalWorkingDirectory = $outside
    ExpectedServerUrl = "http://127.0.0.1:$Port"
    EnvFileModified = $false
    OnlineModelRequests = 0
    HttpProbeModelEndpoint = 'http://127.0.0.1:1/v1 (offline probe only; .env unchanged)'
    Checks = $checks
    Passed = $false
}
$envDigest = (Get-FileHash -LiteralPath (Join-Path $relocatedBackend '.env')).Hash

function Invoke-PortableCheck([string]$Name, [string[]]$Arguments) {
    $log = Join-Path $artifactRoot ($Name + '.log')
    $errorLog = Join-Path $artifactRoot ($Name + '.stderr.log')
    $quoted = ($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }) -join ' '
    $child = Start-Process -FilePath $python -ArgumentList $quoted -WorkingDirectory $outside `
        -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $log -RedirectStandardError $errorLog
    $code = $child.ExitCode
    $checks.Add([ordered]@{Name=$Name; ExitCode=$code; Log=$log; ErrorLog=$errorLog; CreatedPid=$child.Id})
    if ($code -ne 0) { throw "Portable check failed: $Name. See $log" }
    Write-Output "Passed: $Name"
}

function Convert-Utf8JsonResponse($Response) {
    # Windows PowerShell 5.1 can interpret application/json without a charset
    # as Latin-1. Decode the actual bytes so saved Chinese asset paths survive.
    [Text.Encoding]::UTF8.GetString($Response.RawContentStream.ToArray()) | ConvertFrom-Json
}

function Invoke-Utf8Json([string]$Uri, [int]$TimeoutSec = 20) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec $TimeoutSec
    Convert-Utf8JsonResponse $response
}

Push-Location $outside
try {
    Invoke-PortableCheck 'runtime' @((Join-Path $relocatedBackend 'scripts/verify-runtime.py'))
    Invoke-PortableCheck 'dependencies' @('-m', 'pip', 'check')
    Invoke-PortableCheck 'mcp-stdio' @((Join-Path $relocatedBackend 'scripts/verify-mcp.py'))
    if (-not $SkipTests) {
        Invoke-PortableCheck 'tests' @('-m', 'pytest', '-q',
            (Join-Path $relocatedBackend 'tests'), (Join-Path $relocatedBackend 'skills'))
    }
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    try { $listener.Start() } finally { $listener.Stop() }

    # Invoke from outside the app, with the same explicit backend cwd that
    # start.cmd establishes. Official dev metadata is relative to this cwd.
    $oldServerUrl = [Environment]::GetEnvironmentVariable('AGENT_SERVER_URL', 'Process')
    $oldTracing = [Environment]::GetEnvironmentVariable('LANGSMITH_TRACING', 'Process')
    try {
        [Environment]::SetEnvironmentVariable('AGENT_SERVER_URL', "http://127.0.0.1:$Port", 'Process')
        [Environment]::SetEnvironmentVariable('LANGSMITH_TRACING', 'false', 'Process')
        # CLI env-file loading can override inherited variables. Use its native
        # env mapping for probe overrides; backend.settings still loads the
        # original .env with override=False for all service credentials.
        $serverConfig = Get-Content -Raw -LiteralPath (Join-Path $relocatedBackend 'langgraph.json') | ConvertFrom-Json
        $serverConfig.env = @{
            AGENT_SERVER_URL="http://127.0.0.1:$Port"
            LANGSMITH_TRACING='false'
            LLM_BASE_URL='http://127.0.0.1:1/v1'
            VLM_BASE_URL='http://127.0.0.1:1/v1'
            LLM_API_KEY='portability-offline-only'
            VLM_API_KEY='portability-offline-only'
        }
        $serverConfigName = 'langgraph.portability.json'
        [IO.File]::WriteAllText((Join-Path $relocatedBackend $serverConfigName),
            ($serverConfig | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
        $server = Start-Process -FilePath $python -ArgumentList @('-m', 'langgraph_cli', 'dev',
            '--config', $serverConfigName,
            '--no-browser', '--no-reload', '--allow-blocking', '--host', '127.0.0.1',
            '--port', "$Port", '--n-jobs-per-worker', '3') -WorkingDirectory $relocatedBackend `
            -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $artifactRoot 'server.stdout.log') `
            -RedirectStandardError (Join-Path $artifactRoot 'server.stderr.log')
        $report.CreatedServerPid = $server.Id
    } finally {
        [Environment]::SetEnvironmentVariable('AGENT_SERVER_URL', $oldServerUrl, 'Process')
        [Environment]::SetEnvironmentVariable('LANGSMITH_TRACING', $oldTracing, 'Process')
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    $ready = $false
    do {
        $server.Refresh()
        if ($server.HasExited) { throw 'Relocated server exited before becoming ready. See server.stderr.log.' }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/ok" -TimeoutSec 3
            $ready = $response.StatusCode -eq 200
        } catch { Start-Sleep -Milliseconds 500 }
    } while (-not $ready -and [DateTime]::UtcNow -lt $deadline)
    if (-not $ready) { throw 'Relocated server did not become ready within 60 seconds.' }
    foreach ($path in @('/ok', '/api/health', '/app/', '/api/samples')) {
        $response = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:$Port" + $path) -TimeoutSec 20
        if ($response.StatusCode -ne 200) { throw "Unexpected HTTP status for $path" }
        $detail = [ordered]@{Name=$path; StatusCode=$response.StatusCode; ResponseBytes=$response.RawContentLength}
        if ($path -eq '/api/health') {
            $health = Convert-Utf8JsonResponse $response
            $detail.ServiceStatus = $health.status
            if ($health.status -ne 'ok') { throw 'Relocated app external service health is degraded.' }
        }
        if ($path -eq '/app/' -and $response.Content -notmatch 'assets/.*\.js') {
            throw 'The relocated Vue entry did not reference built JavaScript.'
        }
        $checks.Add($detail)
    }
    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $relocatedRoot 'delivery-manifest.json') | ConvertFrom-Json
    if ($manifest.include_state) {
        # Official read-only endpoint, checked against Docs MCP use-threads and
        # ThreadsClient.get_state. This does not resume any interrupted tool.
        $baselineFile = Join-Path $relocatedBackend 'tests/reports/structure-before.json'
        if (Test-Path -LiteralPath $baselineFile) {
            # Direct assignment preserves the JSON array's elements on Windows
            # PowerShell 5.1; @(... | ConvertFrom-Json) nests the whole array.
            $baselines = Get-Content -Raw -Encoding UTF8 -LiteralPath $baselineFile | ConvertFrom-Json
        } else {
            $baselineFile = Join-Path $relocatedBackend 'tests/reports/restart-before.json'
            $baselines = Get-Content -Raw -Encoding UTF8 -LiteralPath $baselineFile | ConvertFrom-Json
            $obsBaselineFile = Join-Path $relocatedBackend 'tests/reports/obs-agent-task.json'
            if (Test-Path -LiteralPath $obsBaselineFile) {
                $baselines += @(Get-Content -Raw -Encoding UTF8 -LiteralPath $obsBaselineFile | ConvertFrom-Json)
            }
        }
        $report.BaselineFile = $baselineFile
        foreach ($baseline in $baselines) {
            $stateUri = "http://127.0.0.1:$Port/threads/$($baseline.thread_id)/state?subgraphs=true"
            $state = Invoke-Utf8Json -Uri $stateUri -TimeoutSec 30
            if ($state.checkpoint.checkpoint_id -ne $baseline.checkpoint.checkpoint_id) {
                throw "Checkpoint changed or missing for $($baseline.task_id)"
            }
            $expectedInterrupts = @($baseline.interrupts | ForEach-Object { $_.id } | Sort-Object -Unique)
            $actualInterrupts = @(@($state.interrupts) + @($state.tasks | ForEach-Object { $_.interrupts }) |
                Where-Object { $null -ne $_ } | ForEach-Object { $_.id } | Sort-Object -Unique)
            if (($expectedInterrupts -join ',') -ne ($actualInterrupts -join ',')) {
                throw "Interrupt IDs changed or missing for $($baseline.task_id)"
            }
            if ($state.values.messages.Count -ne $baseline.messages) {
                throw "Saved messages changed or missing for $($baseline.task_id)"
            }
            $checks.Add([ordered]@{Name='saved-checkpoint'; TaskId=$baseline.task_id;
                CheckpointId=$state.checkpoint.checkpoint_id; InterruptIds=$actualInterrupts;
                Messages=$state.values.messages.Count; Preserved=$true; Resumed=$false})
        }
        $historyTask = '29c0ae9b-f792-4b53-b1f8-2423e72d852f'
        $artifacts = Invoke-Utf8Json -Uri "http://127.0.0.1:$Port/api/tasks/$historyTask/artifacts" -TimeoutSec 20
        $legacySource = $artifacts.sources | Where-Object { $_.format -eq 'eml' } | Select-Object -First 1
        if ($null -eq $legacySource) { throw 'The saved EML source is missing.' }
        $relativeSource = $legacySource.path -replace '^.*[\\/]data[\\/]assets[\\/]', ''
        $expectedSource = Join-Path (Join-Path $relocatedBackend 'data/assets') $relativeSource
        $sourceReference = Join-Path $artifactRoot 'legacy-source.json'
        [IO.File]::WriteAllText($sourceReference, ($legacySource | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        $resolveCode = 'import json,sys; from pathlib import Path; from backend.files import asset_file; s=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig")); p=asset_file(s); assert p == Path(sys.argv[2]).resolve(); assert p != Path(s["path"]).resolve(); assert p.is_file(); print(json.dumps({"legacy_source_resolves_to_relocated_asset": True, "path": str(p)}))'
        Invoke-PortableCheck 'legacy-asset-resolver' @('-c', $resolveCode, $sourceReference, $expectedSource)
        $download = Join-Path $artifactRoot 'downloaded-original.eml'
        $sourceUri = "http://127.0.0.1:$Port/api/tasks/$historyTask/sources/$($legacySource.source_id)/content"
        $response = Invoke-WebRequest -UseBasicParsing -Uri $sourceUri -TimeoutSec 20 -OutFile $download -PassThru
        $downloadHash = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash
        if ($downloadHash -ne (Get-FileHash -LiteralPath $expectedSource -Algorithm SHA256).Hash) {
            throw 'Migrated EML content does not match the bundled original.'
        }
        $checks.Add([ordered]@{Name='legacy-source-content'; TaskId=$historyTask;
            SourceId=$legacySource.source_id; StatusCode=$response.StatusCode;
            Sha256=$downloadHash.ToLowerInvariant(); Bytes=(Get-Item -LiteralPath $download).Length;
            ResolvedInsideRelocatedAssets=$true})
        $exportTask = 'abab67c9-2fe2-44fe-a416-6dbd92058b26'
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/tasks/$exportTask/export" -TimeoutSec 30
        $records = Convert-Utf8JsonResponse $response
        $amounts = @($records | ForEach-Object { [decimal]$_.charge_details.amount } | Sort-Object)
        if ($response.StatusCode -ne 200 -or $records.Count -ne 2 -or $amounts[0] -ne 20 -or $amounts[1] -ne 50) {
            throw 'The approved Excel task did not export both expected numeric amounts.'
        }
        if (@($records | Where-Object { $_.operation -ne 'CREATE' -or $_.financial_attributes.posting_type -ne 'AP' }).Count -ne 0) {
            throw 'The approved Excel export lost its CREATE/AP decisions.'
        }
        $checks.Add([ordered]@{Name='approved-export'; TaskId=$exportTask; StatusCode=$response.StatusCode;
            Records=$records.Count; Amounts=$amounts; Operation='CREATE'; PostingType='AP'; NewAgentRun=$false})
    }
    $report.EnvFileModified = $envDigest -ne (Get-FileHash -LiteralPath (Join-Path $relocatedBackend '.env')).Hash
    if ($report.EnvFileModified) { throw 'Migration check unexpectedly changed .env.' }
    $report.Passed = $true
} catch {
    $report.Error = $_.Exception.Message
    throw
} finally {
    if ($null -ne $server) {
        $server.Refresh()
        if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
        $report.CreatedServerStopped = $true
    }
    Pop-Location
    [IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    Write-Output "Migration report: $reportPath"
}
$report | ConvertTo-Json -Depth 8
