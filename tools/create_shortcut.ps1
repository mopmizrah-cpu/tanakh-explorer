# Creates a desktop shortcut "Tanakh Explorer" that starts the program.
# Run: powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$name = [string]::Concat([char]0x05D7, [char]0x05D5, [char]0x05E7, [char]0x05E8, ' ', [char]0x05D4, [char]0x05EA,
    [char]0x05E0, [char]0x05F4, [char]0x05DA)  # "חוקר התנ״ך" (written as code points so the script's encoding does not matter)
$path = Join-Path $desktop ($name + '.lnk')
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($path)
$lnk.TargetPath = Join-Path $root 'start.bat'
$lnk.WorkingDirectory = $root
$lnk.IconLocation = (Join-Path $root 'tanakh_explorer\frontend\icon.ico') + ',0'
$lnk.WindowStyle = 7  # start minimized: the console window only keeps the server running
$lnk.Description = 'Tanakh Explorer'
$lnk.Save()
Write-Output "created: $path"
