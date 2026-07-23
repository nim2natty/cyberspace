$ErrorActionPreference = "Stop"
$Repo = "nim2natty/cyberspace"
$Version = if ($env:CYBERSPACE_VERSION) { $env:CYBERSPACE_VERSION } else { "latest" }
$BinDir = if ($env:CYBERSPACE_BIN_DIR) { $env:CYBERSPACE_BIN_DIR } else { Join-Path $env:LOCALAPPDATA "Cyberspace\bin" }
$Arch = switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()) {
    "X64" { "x86_64" }
    "Arm64" { "arm64" }
    default { throw "Unsupported CPU architecture: $_" }
}
$Asset = "cyberspace-windows-$Arch.exe"
$Base = if ($Version -eq "latest") { "https://github.com/$Repo/releases/latest/download" } else { "https://github.com/$Repo/releases/download/$Version" }
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$Destination = Join-Path $BinDir "cyberspace.exe"
$Temp = Join-Path ([IO.Path]::GetTempPath()) ("cyberspace-" + [guid]::NewGuid() + ".exe")
$Checksum = "$Temp.sha256"
try {
    Write-Host "[cyberspace] downloading $Asset..."
    Invoke-WebRequest -UseBasicParsing "$Base/$Asset" -OutFile $Temp
    Invoke-WebRequest -UseBasicParsing "$Base/$Asset.sha256" -OutFile $Checksum
    $Expected = ((Get-Content $Checksum -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $Actual = (Get-FileHash -Algorithm SHA256 $Temp).Hash.ToLowerInvariant()
    if ($Expected -ne $Actual) { throw "Release checksum verification failed." }
    Move-Item -Force $Temp $Destination
} finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $Temp, $Checksum
}
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($UserPath -split ';') -notcontains $BinDir) {
    [Environment]::SetEnvironmentVariable("Path", ($UserPath.TrimEnd(';') + ";" + $BinDir), "User")
    Write-Host "[cyberspace] added $BinDir to your user PATH; open a new terminal."
}
Write-Host "[cyberspace] installed and verified: $Destination"
Write-Host "Run it now: $Destination setup; $Destination doctor; $Destination"
Write-Host "Or open a new terminal and run: cyberspace setup"
Write-Host "Later, update with: cyberspace update"