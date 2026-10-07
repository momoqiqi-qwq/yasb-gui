param(
    [ValidateSet('Full', 'Region')][string]$Mode = 'Region',
    [string]$OutputDirectory = (Join-Path ([Environment]::GetFolderPath('MyPictures')) 'YASB_Screenshots')
)
$ErrorActionPreference = 'Stop'
if ($Mode -eq 'Region') {
    Start-Process 'ms-screenclip:'
    exit
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class YasbCaptureDpi {
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr context);
}
'@
[void][YasbCaptureDpi]::SetProcessDpiAwarenessContext([IntPtr](-4))
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bounds.Size)
    $filename = 'Screenshot_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_' + [Guid]::NewGuid().ToString('N') + '.png'
    $bitmap.Save((Join-Path $OutputDirectory $filename), [System.Drawing.Imaging.ImageFormat]::Png)
    # Saving succeeds even if another program currently owns the clipboard.
    try { [System.Windows.Forms.Clipboard]::SetImage($bitmap) } catch { Write-Warning $_ }
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
