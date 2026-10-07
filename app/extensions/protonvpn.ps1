param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [ValidateSet('Open', 'ToggleTray')][string]$Mode = 'Open'
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Executable -PathType Leaf)) { throw 'Proton VPN executable not found' }
if ($Mode -eq 'ToggleTray') {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class YasbProtonWindow {
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string title);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr window, int command);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
}
'@
    $window = [YasbProtonWindow]::FindWindowW('WinUIDesktopWin32WindowClass', 'Proton VPN (tray)')
    if ($window -ne [IntPtr]::Zero) {
        if ([YasbProtonWindow]::IsWindowVisible($window)) {
            [void][YasbProtonWindow]::ShowWindow($window, 0)
        } else {
            [void][YasbProtonWindow]::ShowWindow($window, 5)
            [void][YasbProtonWindow]::SetForegroundWindow($window)
        }
        exit
    }
}
Start-Process -FilePath $Executable
