param([string]$DocumentPath = 'HoangCongHoan_10123137_12423TN.docx')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$sourcePath = (Resolve-Path -LiteralPath $DocumentPath).Path
$qaDir = Join-Path (Get-Location) 'reports/template-qa/bigdata-render'
New-Item -ItemType Directory -Force -Path $qaDir | Out-Null
Add-Type -AssemblyName System.Drawing
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $word.Options.UpdateLinksAtOpen = $false
    Write-Output 'Word instance ready'
    $document = $word.Documents.Open($sourcePath, $false, $false, $false)
    Write-Output 'Report opened'
    $document.Repaginate()
    for ($i=1; $i -le $document.TablesOfContents.Count; $i++) {
        $document.TablesOfContents.Item($i).Update()
    }
    $document.Repaginate()
    for ($i=1; $i -le $document.TablesOfContents.Count; $i++) {
        $document.TablesOfContents.Item($i).UpdatePageNumbers()
    }
    $document.Save()
    Write-Output 'Table of contents updated and original saved'
    # Word's native page metafiles avoid the PDF exporter and preserve actual Word pagination.
    $document.ActiveWindow.View.Type = 3
    $pages = $document.ActiveWindow.Panes.Item(1).Pages
    Write-Output "Pages: $($pages.Count)"
    for ($pageIndex=1; $pageIndex -le $pages.Count; $pageIndex++) {
        $bits = [byte[]]$pages.Item($pageIndex).EnhMetaFileBits
        $stream = [System.IO.MemoryStream]::new($bits, $false)
        $metafile = [System.Drawing.Imaging.Metafile]::new($stream)
        $width = 1240
        $height = [int]($width * $metafile.Height / $metafile.Width)
        $bitmap = [System.Drawing.Bitmap]::new($width, $height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.Clear([System.Drawing.Color]::White)
        $graphics.DrawImage($metafile, [System.Drawing.Rectangle]::new(0,0,$width,$height))
        $pngPath = Join-Path $qaDir ('page-{0:D2}.png' -f $pageIndex)
        $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
        $graphics.Dispose(); $bitmap.Dispose(); $metafile.Dispose(); $stream.Dispose()
        Write-Output "Rendered page $pageIndex"
    }
} finally {
    if ($null -ne $document) { $document.Close(0) }
    if ($null -ne $word) { $word.Quit() }
    if ($null -ne $document) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($null -ne $word) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}
