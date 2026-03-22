Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Claude\01_UFS\services\session-manager"
WshShell.Run "cmd /c start-headless.bat", 0, False
