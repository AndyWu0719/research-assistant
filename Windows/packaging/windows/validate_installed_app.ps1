param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,

    [Parameter(Mandatory = $true)]
    [string]$ScreenshotPath,

    [Parameter(Mandatory = $true)]
    [string]$SummaryPath,

    [Parameter(Mandatory = $false)]
    [string]$ExpectedWindowTitle = "Research Assistant"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Wait-ForMainWindow {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) {
            throw "The application process exited before a main window appeared."
        }
        $Process.Refresh()
        if ($Process.MainWindowHandle -ne 0 -and $Process.MainWindowTitle) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "Timed out waiting for the application main window."
}

function Activate-Window {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,

        [Parameter(Mandatory = $true)]
        [string]$WindowTitle
    )

    $shell = New-Object -ComObject WScript.Shell
    foreach ($target in @($ProcessId, $WindowTitle)) {
        for ($attempt = 0; $attempt -lt 10; $attempt += 1) {
            if ($shell.AppActivate($target)) {
                Start-Sleep -Milliseconds 800
                return $true
            }
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

function Save-Screenshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
    if ($bounds.Width -le 0 -or $bounds.Height -le 0) {
        throw "Virtual screen bounds are invalid; screenshot capture is unavailable."
    }

    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bitmap.Size)
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$exe = Resolve-Path -LiteralPath $ExePath
$summaryDirectory = Split-Path -Parent $SummaryPath
$screenshotDirectory = Split-Path -Parent $ScreenshotPath
New-Item -ItemType Directory -Force -Path $summaryDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $screenshotDirectory | Out-Null

$process = Start-Process -FilePath $exe -PassThru
$activated = $false

try {
    Wait-ForMainWindow -Process $process -TimeoutSeconds 45
    $process.Refresh()
    $activated = Activate-Window -ProcessId $process.Id -WindowTitle $ExpectedWindowTitle
    Save-Screenshot -Path $ScreenshotPath

    $payload = [ordered]@{
        exe_path = [string]$exe
        process_id = $process.Id
        process_name = $process.ProcessName
        main_window_title = $process.MainWindowTitle
        main_window_handle = $process.MainWindowHandle
        app_activate_succeeded = $activated
        screenshot_path = $ScreenshotPath
        captured_at_utc = (Get-Date).ToUniversalTime().ToString("s") + "Z"
    }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $SummaryPath -Encoding UTF8
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
