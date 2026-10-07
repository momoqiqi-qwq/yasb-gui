param(
    [Parameter(Mandatory=$true)][string]$Text,
    [Parameter(Mandatory=$true)][string]$FontFamily,
    [Parameter(Mandatory=$true)][string]$OutputFile
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$family = New-Object System.Drawing.FontFamily($FontFamily)
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$format = [System.Drawing.StringFormat]::GenericTypographic.Clone()
$format.FormatFlags = $format.FormatFlags -bor [System.Drawing.StringFormatFlags]::NoClip
$path.AddString($Text, $family, [int][System.Drawing.FontStyle]::Regular, 48, [System.Drawing.PointF]::Empty, $format)
$bounds = $path.GetBounds()
if ($bounds.Width -le 0 -or $bounds.Height -le 0) { throw 'Icon glyph has no drawable outline' }
$scale = [Math]::Min(36.0 / $bounds.Width, 36.0 / $bounds.Height)
$matrix = New-Object System.Drawing.Drawing2D.Matrix($scale, 0, 0, $scale, (24 - $scale * ($bounds.X + $bounds.Width / 2)), (24 - $scale * ($bounds.Y + $bounds.Height / 2)))
$path.Transform($matrix)
$bitmap = New-Object System.Drawing.Bitmap(48, 48, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb))
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::Transparent)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.FillPath([System.Drawing.Brushes]::White, $path)
$bitmap.Save($OutputFile, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
$matrix.Dispose()
$path.Dispose()
$format.Dispose()
$family.Dispose()
