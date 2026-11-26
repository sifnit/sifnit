; MiniDock - a small, centered taskbar replacement that lives on ONE monitor.
; Apps are grouped: one icon per app, no matter how many windows it has open.
; Requires AutoHotkey v2 (https://www.autohotkey.com).

#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent
SetWinDelay(-1)
CoordMode("Mouse", "Screen")
CoordMode("ToolTip", "Screen")

; ============================ SETTINGS ============================
ICON_SIZE            := 24        ; icon size in px at 100% scaling
CELL_PADDING         := 6         ; space around each icon
ICON_GAP             := 2         ; space between icons
BOTTOM_MARGIN        := 6         ; gap between dock and screen bottom (0 = touching)
BG_COLOR             := "202020"  ; dock background
ACTIVE_COLOR         := "60CDFF"  ; underline for the app you're using
RUNNING_COLOR        := "8A8A8A"  ; underline for apps that are open
HIDE_WINDOWS_TASKBAR := true      ; hide the real taskbar while MiniDock runs
SHOW_START_BUTTON    := true
SHOW_CLOCK           := true
SHOW_SOUND_BUTTON    := true      ; speaker button: pick device, volume, mute
AUTO_AUDIO           := true      ; keep your preferred (headset) speaker/mic as default
REFRESH_MS           := 300       ; how often to check for opened/closed windows
; ==================================================================

global INI := A_ScriptDir "\MiniDock.ini"
global Scale := A_ScreenDPI / 96
global DockMon := ReadMonitor()
global Pinned := LoadPinned()
global Groups := Map()        ; key -> {path, wins: [hwnd...]}
global RunOrder := []         ; running (unpinned) apps in the order they opened
global Dock := 0, DockHwnd := 0
global Buttons := Map()       ; control hwnd -> key
global Indicators := Map()    ; key -> {ctrl, cx, state}
global ClockCtrl := 0
global LastSig := "", LastTip := ""
global DockHidden := false
global PathCache := Map()
global OrigTaskbarState := -1

#Include Audio.ahk

SetupTray()
if HIDE_WINDOWS_TASKBAR {
    OrigTaskbarState := GetTaskbarState()
    SetTaskbarState(1)            ; auto-hide, so Windows stops reserving the bottom strip
    HideTaskbars()
}
OnExit(Cleanup)
OnMessage(0x7E, (*) => ForceRebuild())   ; WM_DISPLAYCHANGE (monitor plugged/unplugged)
OnMessage(0x208, OnMiddleClick)          ; WM_MBUTTONUP: middle-click = new window
AudioInit()
Tick()
SetTimer(Tick, REFRESH_MS)
SetTimer(UpdateClock, 1000)
return

; ------------------------------------------------------------------
; Main loop: find windows, group them by app, rebuild dock if needed
; ------------------------------------------------------------------
Tick() {
    global Groups, RunOrder, LastSig
    Groups := CollectGroups()

    newOrder := []
    for k in RunOrder
        if Groups.Has(k)
            newOrder.Push(k)
    for k in Groups
        if !HasVal(newOrder, k)
            newOrder.Push(k)
    RunOrder := newOrder

    list := []                       ; pinned apps first, then other open apps
    for p in Pinned
        list.Push(StrLower(p))
    for k in RunOrder
        if !HasVal(list, k)
            list.Push(k)

    sig := DockMon ";" Join(list)
    if sig != LastSig {
        LastSig := sig
        BuildDock(list)
    }
    UpdateIndicators()
    if HIDE_WINDOWS_TASKBAR
        HideTaskbars()
    CheckFullscreen()
    HoverTip()
}

CollectGroups() {
    g := Map()
    for hwnd in WinGetList() {
        if !IsTaskbarWindow(hwnd)
            continue
        path := RealPath(hwnd)
        key := StrLower(path)
        if !g.Has(key)
            g[key] := {path: path, wins: []}
        g[key].wins.Push(hwnd)
    }
    return g
}

; Same rules Windows uses to decide what gets a taskbar button
IsTaskbarWindow(hwnd) {
    if hwnd = DockHwnd
        return false
    try {
        style := WinGetStyle(hwnd)
        ex := WinGetExStyle(hwnd)
        appWin := ex & 0x40000                        ; WS_EX_APPWINDOW
        if !(style & 0x10000000)                      ; not WS_VISIBLE
            return false
        if (ex & 0x80) && !appWin                     ; WS_EX_TOOLWINDOW
            return false
        if (ex & 0x08000000) && !appWin               ; WS_EX_NOACTIVATE
            return false
        if DllCall("GetWindow", "ptr", hwnd, "uint", 4, "ptr") && !appWin   ; owned popup
            return false
        if WinGetTitle(hwnd) = ""
            return false
        if WinGetClass(hwnd) ~= "^(Progman|WorkerW|Shell_TrayWnd|Shell_SecondaryTrayWnd)$"
            return false
        cloaked := 0                                  ; hidden UWP apps / other virtual desktops
        DllCall("dwmapi\DwmGetWindowAttribute", "ptr", hwnd, "uint", 14, "int*", &cloaked, "uint", 4)
        if cloaked
            return false
    } catch
        return false
    return true
}

; The exe behind a window. Store apps (Settings, Calculator...) all run inside
; ApplicationFrameHost.exe, so look at the child window to find the real app.
RealPath(hwnd) {
    global PathCache
    if PathCache.Has(hwnd)
        return PathCache[hwnd]
    path := ""
    try path := WinGetProcessPath(hwnd)
    if path = ""
        try path := WinGetProcessName(hwnd)
    if path = ""
        return "unknown"
    if path ~= "i)\\ApplicationFrameHost\.exe$" {
        try {
            for c in WinGetControlsHwnd(hwnd)
                if WinGetClass(c) = "Windows.UI.Core.CoreWindow"
                    return PathCache[hwnd] := WinGetProcessPath(c)
        }
        return "uwp:" WinGetTitle(hwnd)
    }
    if PathCache.Count > 500
        PathCache.Clear()
    return PathCache[hwnd] := path
}

; ------------------------------------------------------------------
; Drawing the dock
; ------------------------------------------------------------------
BuildDock(list) {
    global Dock, DockHwnd, Buttons, Indicators, ClockCtrl, DockHidden, SoundCtrl
    sz   := Round(ICON_SIZE * Scale)
    pad  := Round(CELL_PADDING * Scale)
    gap  := Round(ICON_GAP * Scale)
    cell := sz + pad * 2
    barH := Max(2, Round(3 * Scale))

    ; -Caption: no title bar. ToolWindow: no taskbar/alt-tab entry.
    ; E0x08000000 (NOACTIVATE): clicking the dock doesn't steal focus from your app.
    g := Gui("-Caption +ToolWindow +AlwaysOnTop -DPIScale +E0x08000000")
    g.BackColor := BG_COLOR
    g.MarginX := 0, g.MarginY := 0
    g.OnEvent("ContextMenu", OnDockContext)
    btns := Map(), inds := Map()
    x := pad

    if SHOW_START_BUTTON {
        g.SetFont("s" Round(ICON_SIZE * 0.55) " cFFFFFF", "Segoe UI Symbol")
        s := g.Add("Text", "x" x " y0 w" cell " h" cell " Center +0x200 +0x100", Chr(0x229E))
        s.OnEvent("Click", (*) => Send("^{Esc}"))
        btns[s.Hwnd] := "*start"
        x += cell + gap
    }

    for key in list {
        running := Groups.Has(key)
        path := running ? Groups[key].path : PinnedPath(key)
        pic := AddIcon(g, "x" (x + pad) " y" pad " w" sz " h" sz " +0x100", path, running ? Groups[key].wins[1] : 0, sz)
        pic.OnEvent("Click", OnIconClick.Bind(key))
        btns[pic.Hwnd] := key
        ind := g.Add("Text", "x" x " y" (cell - barH - 1) " w1 h" barH " Background" RUNNING_COLOR)
        ind.Visible := false
        inds[key] := {ctrl: ind, cx: x + cell // 2, state: ""}
        x += cell + gap
    }

    snd := 0
    if SHOW_SOUND_BUTTON {
        g.SetFont("s" Round(ICON_SIZE * 0.45) " cFFFFFF", "Segoe MDL2 Assets")
        snd := g.Add("Text", "x" x " y0 w" cell " h" cell " Center +0x200 +0x100", SoundGlyph())
        snd.OnEvent("Click", (*) => ShowSoundMenu())
        btns[snd.Hwnd] := "*sound"
        x += cell
    }

    clk := 0
    if SHOW_CLOCK {
        g.SetFont("s9 cFFFFFF", "Segoe UI")
        w := Round(64 * Scale)
        clk := g.Add("Text", "x" x " y0 w" w " h" cell " Center +0x200 +0x100", ClockText())
        clk.OnEvent("Click", (*) => Send("#n"))     ; opens calendar / notifications
        btns[clk.Hwnd] := "*clock"
        x += w
    } else
        x += pad - gap

    try MonitorGetWorkArea(DockMon, &l, &t, &r, &b)
    catch
        MonitorGetWorkArea(MonitorGetPrimary(), &l, &t, &r, &b)
    dx := l + (r - l - x) // 2
    dy := b - cell - Round(BOTTOM_MARGIN * Scale)
    g.Show("NA x" dx " y" dy " w" x " h" cell)
    RoundCorners(g.Hwnd)

    old := Dock
    Dock := g, DockHwnd := g.Hwnd, Buttons := btns, Indicators := inds, ClockCtrl := clk, SoundCtrl := snd
    DockHidden := false
    if old
        old.Destroy()
}

AddIcon(g, opts, path, hwnd, sz) {
    h := 0, type := 0
    if !(path ~= "i)^(uwp:|unknown)")
        try h := LoadPicture(path, "Icon1 w" sz " h" sz, &type)
    if h
        return g.Add("Picture", opts, (type = 1 ? "HICON:" : "HBITMAP:") h)
    if hwnd && (h := WindowIcon(hwnd))
        return g.Add("Picture", opts, "HICON:*" h)
    return g.Add("Picture", opts " Icon3", "shell32.dll")
}

WindowIcon(hwnd) {
    h := 0
    try h := SendMessage(0x7F, 1, 0, , hwnd, , , , 200)     ; WM_GETICON, ICON_BIG
    if !h
        try h := SendMessage(0x7F, 2, 0, , hwnd, , , , 200) ; ICON_SMALL2
    if !h
        try h := DllCall(A_PtrSize = 8 ? "GetClassLongPtr" : "GetClassLong", "ptr", hwnd, "int", -14, "uptr")
    return h
}

RoundCorners(hwnd) {
    b := Buffer(4), NumPut("int", 2, b)          ; DWMWCP_ROUND (Windows 11)
    try DllCall("dwmapi\DwmSetWindowAttribute", "ptr", hwnd, "uint", 33, "ptr", b, "uint", 4)
}

; Underline under each icon: blue = active app, gray = open, none = pinned but closed
UpdateIndicators() {
    active := WinExist("A")
    for key, ind in Indicators {
        n := Groups.Has(key) ? Groups[key].wins.Length : 0
        isAct := false
        if n
            for h in Groups[key].wins
                if h = active
                    isAct := true
        state := !n ? "off" : isAct ? "act" : n > 1 ? "multi" : "run"
        if state = ind.state
            continue
        ind.state := state
        if state = "off" {
            ind.ctrl.Visible := false
            continue
        }
        w := Round((state = "act" ? 16 : state = "multi" ? 10 : 6) * Scale)
        ind.ctrl.Move(ind.cx - w // 2, , w)
        ind.ctrl.Opt("Background" (state = "act" ? ACTIVE_COLOR : RUNNING_COLOR))
        ind.ctrl.Visible := true
        ind.ctrl.Redraw()
    }
}

; Hide the dock when a fullscreen app (video, game) is active on its monitor
CheckFullscreen() {
    global DockHidden
    full := false
    try {
        h := WinExist("A")
        if h && h != DockHwnd && !(WinGetClass(h) ~= "^(Progman|WorkerW)$") {
            WinGetPos(&x, &y, &w, &hh, h)
            MonitorGet(DockMon, &l, &t, &r, &b)
            full := (x = l && y = t && w = r - l && hh = b - t)
        }
    }
    if full && !DockHidden {
        Dock.Hide(), DockHidden := true
    } else if !full && DockHidden {
        Dock.Show("NA"), DockHidden := false
    }
}

HoverTip() {
    global LastTip
    tip := ""
    try {
        MouseGetPos(&mx, , &win, &ctl, 2)
        if win = DockHwnd && ctl && Buttons.Has(ctl)
            tip := TipFor(Buttons[ctl])
    }
    if tip = LastTip
        return
    LastTip := tip
    if tip = ""
        return ToolTip()
    WinGetPos(, &dy, , , DockHwnd)
    ToolTip(tip, mx, dy - Round(32 * Scale))
}

TipFor(key) {
    if key = "*start"
        return "Start"
    if key = "*clock"
        return FormatTime(, "LongDate")
    if key = "*sound"
        return SoundTip()
    path := Groups.Has(key) ? Groups[key].path : PinnedPath(key)
    name := path ~= "i)^uwp:" ? SubStr(path, 5) : AppName(path)
    n := Groups.Has(key) ? Groups[key].wins.Length : 0
    return name (n > 1 ? "  (" n " windows)" : "")
}

; "Google Chrome" instead of "chrome" (read from the exe's file description)
AppName(path) {
    static cache := Map()
    if cache.Has(path)
        return cache[path]
    name := ""
    try {
        size := DllCall("version\GetFileVersionInfoSizeW", "str", path, "ptr", 0, "uint")
        if size {
            buf := Buffer(size)
            pTr := 0, pStr := 0, len := 0
            if DllCall("version\GetFileVersionInfoW", "str", path, "uint", 0, "uint", size, "ptr", buf)
            && DllCall("version\VerQueryValueW", "ptr", buf, "str", "\VarFileInfo\Translation", "ptr*", &pTr, "uint*", &len)
            && len >= 4 {
                lang := Format("{:04X}{:04X}", NumGet(pTr, 0, "ushort"), NumGet(pTr, 2, "ushort"))
                if DllCall("version\VerQueryValueW", "ptr", buf, "str", "\StringFileInfo\" lang "\FileDescription", "ptr*", &pStr, "uint*", &len) && len
                    name := StrGet(pStr)
            }
        }
    }
    if Trim(name) = ""
        SplitPath(path, , , , &name)
    return cache[path] := name
}

ClockText() => FormatTime(, "Time")
UpdateClock() {
    if ClockCtrl
        try ClockCtrl.Text := ClockText()
    UpdateSoundButton()
}

; ------------------------------------------------------------------
; Clicking
; ------------------------------------------------------------------
; Left-click: 1 window -> switch to it (or minimize if already in front)
;             several windows -> pick one from a list
;             not open (pinned) -> launch it
OnIconClick(key, *) {
    if !Groups.Has(key)
        return Launch(key)
    wins := Groups[key].wins
    if wins.Length = 1 {
        h := wins[1]
        if WinActive(h) && WinGetMinMax(h) != -1
            WinMinimize(h)
        else
            ActivateWin(h)
        return
    }
    ShowAppMenu(key, false)
}

; Right-click an icon: window list + new window / pin / close
OnDockContext(g, ctrl, *) {
    if ctrl && Buttons.Has(ctrl.Hwnd) {
        key := Buttons[ctrl.Hwnd]
        if key = "*sound"
            return ShowSoundMenu()
        if SubStr(key, 1, 1) != "*"
            return ShowAppMenu(key, true)
    }
    A_TrayMenu.Show()
}

OnMiddleClick(wParam, lParam, msg, hwnd) {
    if Buttons.Has(hwnd) && SubStr(Buttons[hwnd], 1, 1) != "*" {
        Launch(Buttons[hwnd])
        return 0
    }
}

ShowAppMenu(key, full) {
    m := Menu()
    wins := Groups.Has(key) ? Groups[key].wins.Clone() : []
    active := WinExist("A")
    for i, h in wins {
        t := ""
        try t := WinGetTitle(h)
        if StrLen(t) > 60
            t := SubStr(t, 1, 57) "..."
        label := (i < 10 ? "&" i : i) "   " StrReplace(t, "&", "&&")
        m.Add(label, ActivateWin.Bind(h))
        if h = active
            m.Check(label)
    }
    if full {
        path := Groups.Has(key) ? Groups[key].path : PinnedPath(key)
        if wins.Length
            m.Add()
        if !(path ~= "i)^(uwp:|unknown)") {
            m.Add(wins.Length ? "Open new window" : "Open", (*) => Launch(key))
            m.Add(IsPinned(key) ? "Unpin from dock" : "Pin to dock", (*) => TogglePin(key))
        }
        if wins.Length
            m.Add(wins.Length > 1 ? "Close all windows" : "Close window", (*) => CloseAll(wins))
    }
    m.Show()
}

ActivateWin(h, *) {
    try {
        if WinGetMinMax(h) = -1
            WinRestore(h)
        WinActivate(h)
    }
}

CloseAll(wins) {
    for h in wins
        try WinClose(h)
}

Launch(key) {
    path := Groups.Has(key) ? Groups[key].path : PinnedPath(key)
    if path ~= "i)^(uwp:|unknown)"
        return
    try Run('"' path '"')
    catch as e
        MsgBox("Couldn't start:`n" path "`n`n" e.Message, "MiniDock")
}

; ------------------------------------------------------------------
; Pinned apps (saved in MiniDock.ini next to this script)
; ------------------------------------------------------------------
LoadPinned() {
    arr := []
    for p in StrSplit(IniRead(INI, "Dock", "Pinned", A_WinDir "\explorer.exe"), "|")
        if p != ""
            arr.Push(p)
    return arr
}

SavePinned() {
    s := ""
    for p in Pinned
        s .= (s = "" ? "" : "|") p
    IniWrite(s, INI, "Dock", "Pinned")
}

IsPinned(key) {
    for p in Pinned
        if StrLower(p) = key
            return true
    return false
}

PinnedPath(key) {
    for p in Pinned
        if StrLower(p) = key
            return p
    return key
}

TogglePin(key) {
    global LastSig := ""
    for i, p in Pinned
        if StrLower(p) = key {
            Pinned.RemoveAt(i)
            return SavePinned()
        }
    Pinned.Push(Groups[key].path)
    SavePinned()
}

; ------------------------------------------------------------------
; Monitor choice + tray menu
; ------------------------------------------------------------------
ReadMonitor() {
    m := Integer(IniRead(INI, "Dock", "Monitor", 0))
    if m < 1 || m > MonitorGetCount()
        m := MonitorGetPrimary()
    return m
}

MoveToMonitor(n, *) {
    global DockMon := n
    IniWrite(n, INI, "Dock", "Monitor")
    ForceRebuild()
}

ForceRebuild() {
    global LastSig := "", DockMon
    if DockMon > MonitorGetCount()
        DockMon := MonitorGetPrimary()
    SetupTray()
}

SetupTray() {
    tm := A_TrayMenu
    tm.Delete()
    loop MonitorGetCount() {
        label := "Put dock on monitor " A_Index (A_Index = MonitorGetPrimary() ? " (main)" : "")
        tm.Add(label, MoveToMonitor.Bind(A_Index))
        if A_Index = DockMon
            tm.Check(label)
    }
    tm.Add()
    tm.Add("Start with Windows", ToggleStartup)
    if FileExist(StartupLink())
        tm.Check("Start with Windows")
    tm.Add()
    tm.Add("Reload", (*) => Reload())
    tm.Add("Exit (bring back Windows taskbar)", (*) => ExitApp())
    A_IconTip := "MiniDock"
}

StartupLink() => A_Startup "\MiniDock.lnk"

ToggleStartup(name, *) {
    if FileExist(StartupLink()) {
        FileDelete(StartupLink())
        A_TrayMenu.Uncheck(name)
    } else {
        FileCreateShortcut(A_ScriptFullPath, StartupLink(), A_ScriptDir)
        A_TrayMenu.Check(name)
    }
}

; ------------------------------------------------------------------
; Hiding / restoring the real Windows taskbar
; ------------------------------------------------------------------
HideTaskbars() {
    for cls in ["Shell_TrayWnd", "Shell_SecondaryTrayWnd"]
        for h in WinGetList("ahk_class " cls)    ; only visible ones
            try WinHide(h)
}

AppBarData() {
    abd := Buffer(A_PtrSize = 8 ? 48 : 36, 0)
    NumPut("uint", abd.Size, abd, 0)
    NumPut("ptr", WinExist("ahk_class Shell_TrayWnd"), abd, A_PtrSize = 8 ? 8 : 4)
    return abd
}

GetTaskbarState() => DllCall("shell32\SHAppBarMessage", "uint", 4, "ptr", AppBarData(), "uptr")   ; ABM_GETSTATE

SetTaskbarState(state) {                                       ; ABM_SETSTATE, 1 = auto-hide
    abd := AppBarData()
    NumPut("ptr", state, abd, A_PtrSize = 8 ? 40 : 32)
    DllCall("shell32\SHAppBarMessage", "uint", 10, "ptr", abd)
}

Cleanup(*) {
    ToolTip()
    if HIDE_WINDOWS_TASKBAR {
        DetectHiddenWindows(true)
        for cls in ["Shell_TrayWnd", "Shell_SecondaryTrayWnd"]
            for h in WinGetList("ahk_class " cls)
                try WinShow(h)
        if OrigTaskbarState >= 0
            SetTaskbarState(OrigTaskbarState)
    }
}

; ------------------------------------------------------------------
HasVal(arr, v) {
    for x in arr
        if x = v
            return true
    return false
}

Join(arr) {
    s := ""
    for x in arr
        s .= x "|"
    return s
}
