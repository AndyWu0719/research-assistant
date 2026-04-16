param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,

    [Parameter(Mandatory = $true)]
    [string]$CertificatePath,

    [Parameter(Mandatory = $true)]
    [string]$CertificatePassword,

    [Parameter(Mandatory = $false)]
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

$installer = Resolve-Path -LiteralPath $InstallerPath
$certificate = Resolve-Path -LiteralPath $CertificatePath

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin\x64\signtool.exe",
        "${env:ProgramFiles(x86)}\Windows Kits\10\App Certification Kit\signtool.exe"
    ) | Where-Object { $_ -and (Test-Path $_) }
    if ($candidates.Count -gt 0) {
        $signtool = @{ Source = $candidates[0] }
    }
}

if (-not $signtool) {
    throw "signtool.exe was not found."
}

& $signtool.Source sign `
  /fd SHA256 `
  /f $certificate `
  /p $CertificatePassword `
  /tr $TimestampUrl `
  /td SHA256 `
  $installer

$signature = Get-AuthenticodeSignature -FilePath $installer
if ($signature.Status -ne "Valid") {
    throw "Installer signature is not valid: $($signature.Status)"
}

Write-Output "Signed installer: $installer"
