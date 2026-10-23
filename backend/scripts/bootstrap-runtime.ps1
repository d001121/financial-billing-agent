param(
    [string]$PythonVersion = '3.13.16'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtimeRoot = Join-Path $projectRoot 'bishi1'
$pythonExe = Join-Path $runtimeRoot 'python.exe'

if (Test-Path -LiteralPath $runtimeRoot) {
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw 'bishi1 exists without python.exe. Inspect it before rebuilding.'
    }
    & $pythonExe --version
    if ($LASTEXITCODE -ne 0) { throw 'Existing Python runtime failed to start.' }
    Write-Output 'Existing bishi1 runtime retained.'
    return
}

if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'X64') {
    throw 'This runtime package targets Windows x64.'
}
if ($PythonVersion -notmatch '^3\.\d+\.\d+$') {
    throw 'Use a stable Python version in major.minor.patch format.'
}

$cacheRoot = Join-Path $projectRoot '.build'
$null = New-Item -ItemType Directory -Path $cacheRoot -Force
$packagePath = Join-Path $cacheRoot "python.$PythonVersion.nupkg"
$packageUrl = "https://api.nuget.org/v3-flatcontainer/python/$PythonVersion/python.$PythonVersion.nupkg"
if (-not (Test-Path -LiteralPath $packagePath)) {
    Invoke-WebRequest -Uri $packageUrl -OutFile $packagePath -TimeoutSec 180
}

$extractRoot = Join-Path $cacheRoot ("python-extract-" + [Guid]::NewGuid().ToString('N'))
[IO.Compression.ZipFile]::ExtractToDirectory($packagePath, $extractRoot)
$toolsRoot = [IO.Path]::GetFullPath((Join-Path $extractRoot 'tools'))
$expectedCachePrefix = [IO.Path]::GetFullPath($cacheRoot) + [IO.Path]::DirectorySeparatorChar
$expectedRuntime = [IO.Path]::GetFullPath((Join-Path $projectRoot 'bishi1'))
if (-not $toolsRoot.StartsWith($expectedCachePrefix, [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetFullPath($runtimeRoot) -ne $expectedRuntime) {
    throw 'Runtime source or destination is outside the expected project paths.'
}
if (-not (Test-Path -LiteralPath (Join-Path $toolsRoot 'python.exe'))) {
    throw 'Official package does not contain tools/python.exe.'
}
Move-Item -LiteralPath $toolsRoot -Destination $runtimeRoot

$pythonMajorMinor = (($PythonVersion -split '\.')[0..1] -join '')
$pathFile = Join-Path $runtimeRoot "python$pythonMajorMinor._pth"
@(
    '.'
    'Lib'
    'DLLs'
    'Lib\site-packages'
    '..'
    '..\..'
    'import site'
) | Set-Content -LiteralPath $pathFile -Encoding ascii

& $pythonExe --version
if ($LASTEXITCODE -ne 0) { throw 'Portable interpreter verification failed.' }
& $pythonExe -m pip --version
if ($LASTEXITCODE -ne 0) { throw 'Portable pip verification failed.' }
Write-Output 'Portable runtime ready in bishi1. Run project commands with python.cmd.'
