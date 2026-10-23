param(
    [string]$Output = 'delivery/harbor-bishi1-windows-x64.zip',
    [switch]$IncludeState,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$arguments = @((Join-Path $PSScriptRoot 'package-app.py'), '--output', $Output)
if ($IncludeState) { $arguments += '--include-state' }
if ($DryRun) { $arguments += '--dry-run' }
& (Join-Path $projectRoot 'python.cmd') @arguments
exit $LASTEXITCODE
