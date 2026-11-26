; Audio part of MiniDock: sound button + "keep my headset as default" rules.
; This file is included by MiniDock.ahk - don't run it on its own.
;
; How auto-switch works:
;   Windows changes the default sound device whenever a new one shows up
;   (plugging in a monitor with speakers, a dock, etc). MiniDock watches the
;   list of connected sound devices. For a few seconds after that list changes
;   it makes sure the default is:
;       1. your Preferred device (e.g. Bluetooth headset), if it's connected
;       2. otherwise your Backup device (e.g. PC speakers)
;   If you switch devices yourself while nothing is being plugged in or out,
;   MiniDock leaves your choice alone.

global AudioCfg := Map()
global AudioSig := ""
global EnforceUntil := 0
global SoundCtrl := 0

AudioInit() {
    for k in ["PrefOut", "BackupOut", "PrefIn", "BackupIn"]
        AudioCfg[k] := IniRead(INI, "Audio", k, "")
    AudioCfg["Enabled"] := IniRead(INI, "Audio", "Enabled", 1) = 1
    if AUTO_AUDIO
        SetTimer(AudioTick, 1500)
}

AudioTick() {
    global AudioSig, EnforceUntil
    try {
        outs := Audio.Devices(0), ins := Audio.Devices(1)
        sig := ""
        for d in outs
            sig .= d.id "|"
        for d in ins
            sig .= d.id "|"
        if sig != AudioSig {               ; something was plugged in / unplugged / connected
            AudioSig := sig
            EnforceUntil := A_TickCount + 8000
            GuessDefaults(outs, ins)
        }
        if !AudioCfg["Enabled"] || A_TickCount > EnforceUntil
            return
        Enforce(0, outs, "PrefOut", "BackupOut")
        Enforce(1, ins, "PrefIn", "BackupIn")
    }
}

Enforce(flow, devs, prefKey, backKey) {
    target := ""
    for k in [prefKey, backKey] {
        id := AudioCfg[k]
        if id != "" && FindDev(devs, id) {
            target := id
            break
        }
    }
    if target != "" && Audio.DefaultId(flow) != target
        Audio.SetDefault(target)
}

; First run: pick the Bluetooth headset as Preferred and a non-monitor device as Backup
GuessDefaults(outs, ins) {
    static hdmi := "i)(NVIDIA|AMD High Definition|Display Audio|HDMI|DisplayPort)"
    if AudioCfg["PrefOut"] = "" {
        pick := 0
        for d in outs                      ; prefer stereo "Headphones" over "Hands-Free"
            if d.bt && (!pick || InStr(pick.name, "Hands-Free") && !InStr(d.name, "Hands-Free"))
                pick := d
        if pick
            SetPref("PrefOut", pick.id), TrayTip("Preferred speaker: " pick.name, "MiniDock")
    }
    if AudioCfg["PrefIn"] = ""
        for d in ins
            if d.bt {
                SetPref("PrefIn", d.id), TrayTip("Preferred microphone: " d.name, "MiniDock")
                break
            }
    for pair in [[0, outs, "BackupOut"], [1, ins, "BackupIn"]] {
        if AudioCfg[pair[3]] != ""
            continue
        def := Audio.DefaultId(pair[1])
        if (d := FindDev(pair[2], def)) && !d.bt && !(d.name ~= hdmi)
            SetPref(pair[3], def)
    }
}

FindDev(devs, id) {
    for d in devs
        if d.id = id
            return d
    return 0
}

SetPref(key, id, *) {
    global EnforceUntil
    AudioCfg[key] := id
    IniWrite(id, INI, "Audio", key)
    EnforceUntil := A_TickCount + 3000     ; apply right away
}

PickDevice(id, *) {
    global EnforceUntil := 0               ; you chose it: don't fight you
    try Audio.SetDefault(id)
}

ToggleAuto(*) {
    AudioCfg["Enabled"] := !AudioCfg["Enabled"]
    IniWrite(AudioCfg["Enabled"] ? 1 : 0, INI, "Audio", "Enabled")
}

; ------------------------------------------------------------------
; Sound button on the dock
; ------------------------------------------------------------------
SoundGlyph() {
    muted := false
    try muted := SoundGetMute()
    return Chr(muted ? 0xE74F : 0xE767)    ; Segoe MDL2 Assets: mute / volume
}

UpdateSoundButton() {
    if !SoundCtrl
        return
    try {
        gl := SoundGlyph()
        if SoundCtrl.Text != gl
            SoundCtrl.Text := gl
    }
}

SoundTip() {
    name := "No sound device", vol := ""
    try name := SoundGetName()
    try vol := "  ·  " Round(SoundGetVolume()) "%" (SoundGetMute() ? " (muted)" : "")
    return name vol "`nScroll to change volume"
}

ChangeVolume(step) {
    global LastTip := ""
    try SoundSetVolume((step > 0 ? "+" : "") step)
    try SoundSetMute(false)
    UpdateSoundButton()
    HoverTip()
}

OverSoundButton() {
    try {
        MouseGetPos(, , &win, &ctl, 2)
        return win = DockHwnd && Buttons.Has(ctl) && Buttons[ctl] = "*sound"
    }
    return false
}

#HotIf OverSoundButton()
WheelUp::ChangeVolume(4)
WheelDown::ChangeVolume(-4)
#HotIf

ShowSoundMenu() {
    outs := [], ins := [], allOuts := [], allIns := [], dOut := "", dIn := ""
    try {
        outs := Audio.Devices(0), ins := Audio.Devices(1)
        allOuts := Audio.Devices(0, 1 | 4), allIns := Audio.Devices(1, 1 | 4)   ; incl. disconnected
        dOut := Audio.DefaultId(0), dIn := Audio.DefaultId(1)
    }
    m := Menu()

    m.Add("Speakers / headphones", (*) => 0), m.Disable("Speakers / headphones")
    AddDeviceItems(m, outs, dOut, "    ", AudioCfg["PrefOut"], AudioCfg["BackupOut"])
    m.Add()
    m.Add("Microphone", (*) => 0), m.Disable("Microphone")
    AddDeviceItems(m, ins, dIn, "     ", AudioCfg["PrefIn"], AudioCfg["BackupIn"])
    m.Add()

    vm := Menu()
    for v in [100, 75, 50, 25, 10]
        vm.Add(v "%", ((v, *) => (SoundSetVolume(v), SoundSetMute(false), UpdateSoundButton())).Bind(v))
    cur := ""
    try cur := " (" Round(SoundGetVolume()) "%)"
    m.Add("Volume" cur, vm)
    m.Add("Mute sound", (*) => (SoundSetMute(-1), UpdateSoundButton()))
    try if SoundGetMute()
        m.Check("Mute sound")
    if d := FindDev(ins, dIn) {
        m.Add("Mute microphone", ((n, *) => SoundSetMute(-1, , n)).Bind(d.name))
        try if SoundGetMute(, d.name)
            m.Check("Mute microphone")
    }
    m.Add()

    am := Menu()
    am.Add("Keep my preferred devices", ToggleAuto)
    if AudioCfg["Enabled"]
        am.Check("Keep my preferred devices")
    am.Add()
    am.Add("Preferred speaker", DevPicker(allOuts, "PrefOut"))
    am.Add("Backup speaker (when preferred is off)", DevPicker(allOuts, "BackupOut"))
    am.Add("Preferred microphone", DevPicker(allIns, "PrefIn"))
    am.Add("Backup microphone (when preferred is off)", DevPicker(allIns, "BackupIn"))
    m.Add("Auto-switch", am)

    m.Add("Sound settings...", (*) => Run("ms-settings:sound"))
    m.Add("Volume mixer...", (*) => Run("ms-settings:apps-volume"))
    m.Show()
}

; indent differs between outputs and inputs so identical names stay separate items
AddDeviceItems(m, devs, def, indent, pref, backup) {
    if !devs.Length {
        m.Add(indent "(none connected)", (*) => 0), m.Disable(indent "(none connected)")
        return
    }
    for d in devs {
        label := indent StrReplace(d.name, "&", "&&")
            . (d.id = pref ? "`t★ preferred" : d.id = backup ? "`tbackup" : "")
        m.Add(label, PickDevice.Bind(d.id))
        if d.id = def
            m.Check(label)
    }
}

DevPicker(devs, key) {
    sm := Menu()
    sm.Add("(none)", SetPref.Bind(key, ""))
    if AudioCfg[key] = ""
        sm.Check("(none)")
    for d in devs {
        label := StrReplace(d.name, "&", "&&") (d.state != 1 ? "   (off)" : "")
        sm.Add(label, SetPref.Bind(key, d.id))
        if d.id = AudioCfg[key]
            sm.Check(label)
    }
    return sm
}

; ------------------------------------------------------------------
; Windows Core Audio (COM) - list devices, read / set the default one
; ------------------------------------------------------------------
class Audio {
    static Enum() => ComObject("{BCDE0395-E52F-467C-8E3D-C4579291692E}", "{A95664D2-9614-4F35-A746-DE8DB63617E6}")

    ; flow: 0 = output, 1 = input.  stateMask 1 = connected only, 1|4 = also unplugged/off
    static Devices(flow, stateMask := 1) {
        list := []
        coll := 0, count := 0
        ComCall(3, Audio.Enum(), "int", flow, "uint", stateMask, "ptr*", &coll)    ; EnumAudioEndpoints
        ComCall(3, coll, "uint*", &count)                                           ; GetCount
        loop count {
            dev := 0, pId := 0, store := 0, st := 0
            ComCall(4, coll, "uint", A_Index - 1, "ptr*", &dev)                       ; Item
            ComCall(5, dev, "ptr*", &pId)                                             ; GetId
            id := StrGet(pId)
            DllCall("ole32\CoTaskMemFree", "ptr", pId)
            ComCall(6, dev, "uint*", &st)                                             ; GetState
            ComCall(4, dev, "uint", 0, "ptr*", &store)                                ; OpenPropertyStore
            name := Audio.Prop(store, 14)                                             ; FriendlyName
            enumr := Audio.Prop(store, 24)                                            ; EnumeratorName
            ObjRelease(store), ObjRelease(dev)
            list.Push({id: id, name: name, state: st, bt: InStr(enumr, "BTH") > 0})
        }
        ObjRelease(coll)
        return list
    }

    static Prop(store, pid) {
        key := Buffer(20)
        DllCall("ole32\CLSIDFromString", "wstr", "{a45c254e-df1c-4efd-8020-67d146a850e0}", "ptr", key)
        NumPut("uint", pid, key, 16)
        pv := Buffer(24, 0), val := ""
        try {
            ComCall(5, store, "ptr", key, "ptr", pv)                                  ; GetValue
            if NumGet(pv, 0, "ushort") = 31                                            ; VT_LPWSTR
                val := StrGet(NumGet(pv, 8, "ptr"))
        }
        DllCall("ole32\PropVariantClear", "ptr", pv)
        return val
    }

    static DefaultId(flow) {
        dev := 0, pId := 0
        try ComCall(4, Audio.Enum(), "int", flow, "int", 0, "ptr*", &dev)             ; GetDefaultAudioEndpoint
        catch
            return ""
        ComCall(5, dev, "ptr*", &pId)
        id := StrGet(pId)
        DllCall("ole32\CoTaskMemFree", "ptr", pId), ObjRelease(dev)
        return id
    }

    ; IPolicyConfig::SetDefaultEndpoint for all 3 roles (console, multimedia, communications)
    static SetDefault(id) {
        pc := ComObject("{870af99c-171d-4f9e-af0d-e63df40c2bc9}", "{f8679f50-850a-41cf-9c72-430f290290c8}")
        loop 3
            ComCall(13, pc, "wstr", id, "int", A_Index - 1)
    }
}
