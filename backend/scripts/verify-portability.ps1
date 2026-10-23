$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtimeRoot = Join-Path $projectRoot 'bishi1'
$artifactRoot = Join-Path $projectRoot ('.build\portability-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $artifactRoot -Force
$archivePath = Join-Path $artifactRoot 'runtime.zip'
$relocatedRoot = Join-Path $artifactRoot ([string][char]0x79fb + [char]0x52a8 + ' portable test')

[IO.Compression.ZipFile]::CreateFromDirectory(
    $runtimeRoot,
    $archivePath,
    [IO.Compression.CompressionLevel]::Optimal,
    $false
)
[IO.Compression.ZipFile]::ExtractToDirectory($archivePath, (Join-Path $relocatedRoot 'bishi1'))
$relocatedScripts = Join-Path $relocatedRoot 'scripts'
$null = New-Item -ItemType Directory -Path $relocatedScripts -Force
Copy-Item -LiteralPath (Join-Path $projectRoot 'python.cmd') -Destination (Join-Path $relocatedRoot 'python.cmd')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'verify-runtime.py') -Destination (Join-Path $relocatedScripts 'verify-runtime.py')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'verify-mcp.py') -Destination (Join-Path $relocatedScripts 'verify-mcp.py')

Push-Location (Split-Path -Parent $projectRoot)
try {
    & (Join-Path $relocatedRoot 'python.cmd') (Join-Path $relocatedScripts 'verify-runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Relocated runtime verification failed.' }
    & (Join-Path $relocatedRoot 'python.cmd') -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Relocated dependency check failed.' }
    & (Join-Path $relocatedRoot 'python.cmd') (Join-Path $relocatedScripts 'verify-mcp.py')
    if ($LASTEXITCODE -ne 0) { throw 'Relocated MCP stdio verification failed.' }
} finally {
    Pop-Location
}

[pscustomobject]@{
    ZipExtractRelocationPassed = $true
    ArchiveBytes = (Get-Item -LiteralPath $archivePath).Length
    ArtifactRoot = $artifactRoot
    TestedFromProjectExternalDirectory = $true
} | ConvertTo-Json
