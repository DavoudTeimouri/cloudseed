$ErrorActionPreference = 'Stop'

$packageName = 'cloudseed'
$url = 'https://github.com/DavoudTeimouri/cloudseed/releases/download/v2.0.4/cloudseed.exe'
$checksum = 'REPLACE_WITH_ACTUAL_SHA256'
$checksumType = 'sha256'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

$packageArgs = @{
  packageName   = $packageName
  fileFullPath  = Join-Path $toolsDir 'cloudseed.exe'
  url           = $url
  checksum      = $checksum
  checksumType  = $checksumType
}

Get-ChocolateyWebFile @packageArgs

# Create shim
Install-BinFile -Name 'cloudseed' -Path $packageArgs.fileFullPath
