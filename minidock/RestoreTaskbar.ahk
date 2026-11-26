; Emergency restore: run this if MiniDock was force-closed (e.g. from Task Manager)
; and the normal Windows taskbar didn't come back.
#Requires AutoHotkey v2.0

DetectHiddenWindows(true)
for cls in ["Shell_TrayWnd", "Shell_SecondaryTrayWnd"]
    for h in WinGetList("ahk_class " cls)
        try WinShow(h)

; Turn taskbar auto-hide back off
abd := Buffer(A_PtrSize = 8 ? 48 : 36, 0)
NumPut("uint", abd.Size, abd, 0)
NumPut("ptr", WinExist("ahk_class Shell_TrayWnd"), abd, A_PtrSize = 8 ? 8 : 4)
NumPut("ptr", 0, abd, A_PtrSize = 8 ? 40 : 32)
DllCall("shell32\SHAppBarMessage", "uint", 10, "ptr", abd)

MsgBox("Windows taskbar restored.", "MiniDock")
