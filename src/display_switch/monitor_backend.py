"""Monitor enable/disable by attaching or detaching displays in the Windows desktop topology.

A disabled PnP device does not remove the display from the desktop, so this module
uses the CCD API (QueryDisplayConfig / SetDisplayConfig) through PowerShell.
This module has no Qt imports so it can be tested without a display.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass, field

# Full path to Windows PowerShell 5.1, which ships the PnpDevice cmdlets.
# Under WSL the Linux process must use the /mnt/c path to execute the Windows binary.
if sys.platform == "win32":
    POWERSHELL_EXE = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )
else:
    POWERSHELL_EXE = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"


# C# helper compiled by PowerShell Add-Type. It lists displays and attaches or
# detaches them by editing the active display paths.
_DISPLAY_TOPOLOGY_CS = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;

public static class DisplayTopology
{
    const uint QDC_ALL_PATHS = 0x1;
    const uint QDC_ONLY_ACTIVE_PATHS = 0x2;
    const uint SDC_APPLY = 0x80;
    const uint SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x20;
    const uint SDC_TOPOLOGY_EXTEND = 0x4;
    const uint PATH_ACTIVE = 0x1;
    const int MODE_INFO_SIZE = 64;
    const uint DEVICE_INFO_GET_TARGET_NAME = 2;

    [StructLayout(LayoutKind.Sequential)]
    public struct LUID { public uint LowPart; public int HighPart; }

    [StructLayout(LayoutKind.Sequential)]
    public struct PathSource { public LUID AdapterId; public uint Id; public uint ModeInfoIdx; public uint StatusFlags; }

    [StructLayout(LayoutKind.Sequential)]
    public struct PathTarget
    {
        public LUID AdapterId; public uint Id; public uint ModeInfoIdx;
        public int OutputTechnology; public int Rotation; public int Scaling;
        public uint RefreshNumerator; public uint RefreshDenominator;
        public int ScanLineOrdering; public int TargetAvailable; public uint StatusFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PathInfo { public PathSource Source; public PathTarget Target; public uint Flags; }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct TargetName
    {
        public uint Type; public uint Size; public LUID AdapterId; public uint Id;
        public uint Flags; public int OutputTechnology; public ushort ManufactureId; public ushort ProductCodeId; public uint ConnectorInstance;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string FriendlyName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DevicePath;
    }

    [DllImport("user32.dll")] static extern int GetDisplayConfigBufferSizes(uint flags, out uint pathCount, out uint modeCount);
    [DllImport("user32.dll")] static extern int QueryDisplayConfig(uint flags, ref uint pathCount, [Out] PathInfo[] paths, ref uint modeCount, [Out] byte[] modes, IntPtr topologyId);
    [DllImport("user32.dll")] static extern int SetDisplayConfig(uint pathCount, PathInfo[] paths, uint modeCount, byte[] modes, uint flags);
    [DllImport("user32.dll")] static extern int DisplayConfigGetDeviceInfo(ref TargetName request);

    sealed class Snapshot { public PathInfo[] Paths; public byte[] Modes; public uint ModeCount; }

    static void Check(int result, string call)
    {
        if (result != 0) throw new InvalidOperationException(call + " failed with error " + result);
    }

    static Snapshot Take(uint flags)
    {
        uint pathCount, modeCount;
        Check(GetDisplayConfigBufferSizes(flags, out pathCount, out modeCount), "GetDisplayConfigBufferSizes");
        var paths = new PathInfo[pathCount];
        var modes = new byte[(int)modeCount * MODE_INFO_SIZE];
        Check(QueryDisplayConfig(flags, ref pathCount, paths, ref modeCount, modes, IntPtr.Zero), "QueryDisplayConfig");
        Array.Resize(ref paths, (int)pathCount);
        return new Snapshot { Paths = paths, Modes = modes, ModeCount = modeCount };
    }

    static TargetName ReadTarget(PathInfo path)
    {
        var request = new TargetName();
        request.Type = DEVICE_INFO_GET_TARGET_NAME;
        request.Size = (uint)Marshal.SizeOf(typeof(TargetName));
        request.AdapterId = path.Target.AdapterId;
        request.Id = path.Target.Id;
        DisplayConfigGetDeviceInfo(ref request);
        return request;
    }

    // Converts \\?\DISPLAY#BNQ7F47#5&184851c5&1&uid45313#{guid} to DISPLAY\BNQ7F47\5&184851C5&1&UID45313,
    // the same form as the PnP instance ID.
    static string InstanceId(string devicePath)
    {
        string s = devicePath ?? "";
        if (s.StartsWith(@"\\?\", StringComparison.OrdinalIgnoreCase)) s = s.Substring(4);
        int brace = s.IndexOf("#{", StringComparison.Ordinal);
        if (brace >= 0) s = s.Substring(0, brace);
        return s.Replace('#', '\\').ToUpperInvariant();
    }

    public static string[] List()
    {
        var snapshot = Take(QDC_ALL_PATHS);
        var seen = new HashSet<string>();
        var lines = new List<string>();
        foreach (var path in snapshot.Paths)
        {
            bool active = (path.Flags & PATH_ACTIVE) != 0;
            if (path.Target.TargetAvailable == 0 && !active) continue;
            var name = ReadTarget(path);
            string id = InstanceId(name.DevicePath);
            if (id.Length == 0 || !seen.Add(id)) continue;
            string friendly = string.IsNullOrEmpty(name.FriendlyName) ? id : name.FriendlyName;
            lines.Add(id + "\t" + friendly + "\t" + (active ? "1" : "0"));
        }
        return lines.ToArray();
    }

    static T FromBytes<T>(byte[] buffer) where T : struct
    {
        int size = Marshal.SizeOf(typeof(T));
        IntPtr ptr = Marshal.AllocHGlobal(size);
        try
        {
            Marshal.Copy(buffer, 0, ptr, size);
            return (T)Marshal.PtrToStructure(ptr, typeof(T));
        }
        finally { Marshal.FreeHGlobal(ptr); }
    }

    static byte[] ToBytes<T>(T value) where T : struct
    {
        int size = Marshal.SizeOf(typeof(T));
        IntPtr ptr = Marshal.AllocHGlobal(size);
        try
        {
            Marshal.StructureToPtr(value, ptr, false);
            var buffer = new byte[size];
            Marshal.Copy(ptr, buffer, 0, size);
            return buffer;
        }
        finally { Marshal.FreeHGlobal(ptr); }
    }

    static string[] Ids(Snapshot snapshot)
    {
        var ids = new string[snapshot.Paths.Length];
        for (int i = 0; i < ids.Length; i++) ids[i] = InstanceId(ReadTarget(snapshot.Paths[i]).DevicePath);
        return ids;
    }

    static bool Known(Snapshot snapshot, string wanted)
    {
        return Array.IndexOf(Ids(snapshot), wanted) >= 0;
    }

    // Saved layouts are kept in a text file: one line per monitor, "instanceId<TAB>base64".
    static Dictionary<string, string> LoadState(string file)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!File.Exists(file)) return map;
        foreach (var line in File.ReadAllLines(file))
        {
            int tab = line.IndexOf('\t');
            if (tab > 0) map[line.Substring(0, tab)] = line.Substring(tab + 1);
        }
        return map;
    }

    static void SaveState(string file, Dictionary<string, string> map)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(file));
        var lines = new List<string>();
        foreach (var kv in map) lines.Add(kv.Key + "\t" + kv.Value);
        File.WriteAllLines(file, lines.ToArray());
    }

    static string Encode(Snapshot snapshot, string[] ids)
    {
        using (var ms = new MemoryStream())
        using (var w = new BinaryWriter(ms))
        {
            w.Write(snapshot.Paths.Length);
            for (int i = 0; i < snapshot.Paths.Length; i++)
            {
                w.Write(ids[i]);
                w.Write(ToBytes(snapshot.Paths[i]));
            }
            w.Write(snapshot.Modes.Length);
            w.Write(snapshot.Modes);
            w.Flush();
            return Convert.ToBase64String(ms.ToArray());
        }
    }

    static void Decode(string text, out string[] ids, out List<PathInfo> paths, out byte[] modes)
    {
        using (var ms = new MemoryStream(Convert.FromBase64String(text)))
        using (var r = new BinaryReader(ms))
        {
            int count = r.ReadInt32();
            int size = Marshal.SizeOf(typeof(PathInfo));
            ids = new string[count];
            paths = new List<PathInfo>();
            for (int i = 0; i < count; i++)
            {
                ids[i] = r.ReadString();
                paths.Add(FromBytes<PathInfo>(r.ReadBytes(size)));
            }
            int modeLength = r.ReadInt32();
            modes = r.ReadBytes(modeLength);
        }
    }

    // Detach: save the full active layout first so it can be restored later.
    // Attach: restore the saved layout for that monitor, or extend if nothing was saved.
    public static void Set(string instanceId, bool enable, string stateFile)
    {
        string wanted = instanceId.ToUpperInvariant();
        var active = Take(QDC_ONLY_ACTIVE_PATHS);
        var activeIds = Ids(active);
        bool isActive = Array.IndexOf(activeIds, wanted) >= 0;
        var state = LoadState(stateFile);

        if (!enable)
        {
            if (!isActive)
            {
                if (!Known(Take(QDC_ALL_PATHS), wanted))
                    throw new InvalidOperationException("Monitor not found in the display topology: " + instanceId);
                return;
            }
            state[wanted] = Encode(active, activeIds);
            SaveState(stateFile, state);

            var remaining = new List<PathInfo>(active.Paths);
            remaining.RemoveAt(Array.IndexOf(activeIds, wanted));
            var array = remaining.ToArray();
            Check(SetDisplayConfig((uint)array.Length, array, active.ModeCount, active.Modes,
                SDC_APPLY | SDC_USE_SUPPLIED_DISPLAY_CONFIG), "SetDisplayConfig");
            return;
        }

        if (isActive) return;
        string saved;
        string[] savedIds;
        List<PathInfo> savedPaths;
        byte[] savedModes;
        if (state.TryGetValue(wanted, out saved))
        {
            Decode(saved, out savedIds, out savedPaths, out savedModes);
            var savedSet = new HashSet<string>(savedIds);
            // Only restore when every monitor that is active now was part of the saved layout.
            if (activeIds.All(id => savedSet.Contains(id)))
            {
                var restore = new List<PathInfo>();
                for (int i = 0; i < savedPaths.Count; i++)
                {
                    // Skip monitors that were detached after this layout was saved.
                    if (savedIds[i] != wanted && Array.IndexOf(activeIds, savedIds[i]) < 0) continue;
                    var path = savedPaths[i];
                    path.Flags |= PATH_ACTIVE;
                    restore.Add(path);
                }
                var restoreArray = restore.ToArray();
                Check(SetDisplayConfig((uint)restoreArray.Length, restoreArray,
                    (uint)(savedModes.Length / MODE_INFO_SIZE), savedModes,
                    SDC_APPLY | SDC_USE_SUPPLIED_DISPLAY_CONFIG), "SetDisplayConfig");
                state.Remove(wanted);
                SaveState(stateFile, state);
                return;
            }
        }

        if (!Known(Take(QDC_ALL_PATHS), wanted))
            throw new InvalidOperationException("Monitor not found in the display topology: " + instanceId);
        Check(SetDisplayConfig(0, null, 0, null, SDC_APPLY | SDC_TOPOLOGY_EXTEND), "SetDisplayConfig");
    }
}
'''


class PowerShellError(RuntimeError):
    """A PowerShell command failed or PowerShell is unavailable."""


class GuardError(RuntimeError):
    """A requested change was refused for safety reasons."""


MAX_LOG_ENTRIES = 50


@dataclass(frozen=True)
class CommandRecord:
    """One PowerShell script that was run, with its outcome."""

    script: str
    ok: bool
    output: str


_log_lock = threading.Lock()
_command_log: deque[CommandRecord] = deque(maxlen=MAX_LOG_ENTRIES)


@dataclass(frozen=True)
class Monitor:
    instance_id: str
    name: str
    enabled: bool


@dataclass
class ChangeResult:
    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def _ps_quote(value: str) -> str:
    """Quote a value as a PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


def _record(script: str, ok: bool, output: str) -> None:
    """Store a finished PowerShell command in the in-memory log.

    Args:
        script: The PowerShell script that was run.
        ok: Whether the command succeeded.
        output: Stdout on success, or the error message on failure.

    Returns:
        None
    """
    with _log_lock:
        _command_log.append(CommandRecord(script=script, ok=ok, output=output))


def command_log() -> list[CommandRecord]:
    """Return a copy of the recent PowerShell commands, oldest first.

    Returns:
        The logged command records.
    """
    with _log_lock:
        return list(_command_log)


def format_command_log(records: list[CommandRecord]) -> str:
    """Format logged commands as runnable PowerShell with a result comment above each.

    Args:
        records: Commands to format.

    Returns:
        Text that can be pasted into a Windows PowerShell window.
    """
    blocks: list[str] = []
    for record in records:
        status = "OK" if record.ok else "FAILED"
        first_line = record.output.splitlines()[0] if record.output else ""
        blocks.append(f"# {status}: {first_line}\n{record.script}")
    return "\n\n".join(blocks)


def run_powershell(script: str) -> str:
    """Run a PowerShell script, log it, and return its stdout.

    Args:
        script: The PowerShell script to run.

    Returns:
        The standard output of the script.

    Raises:
        PowerShellError: PowerShell is missing or the script exited non-zero.
    """
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # -EncodedCommand avoids quoting problems with the multi-line C# helper.
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        proc = subprocess.run(
            [
                POWERSHELL_EXE,
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            creationflags=creationflags,
            check=False,
        )
    except FileNotFoundError as exc:
        message = f"PowerShell not found at {POWERSHELL_EXE}; this tool requires Windows."
        _record(script, ok=False, output=message)
        raise PowerShellError(message) from exc

    if proc.returncode != 0:
        message = proc.stderr.strip() or f"PowerShell exited with code {proc.returncode}"
        _record(script, ok=False, output=message)
        raise PowerShellError(message)
    _record(script, ok=True, output=proc.stdout.strip())
    return proc.stdout


def _ps_script(call: str) -> str:
    """Build a PowerShell script that loads the display topology helper and runs one call.

    Args:
        call: PowerShell expression to run after the helper type is compiled.

    Returns:
        The complete PowerShell script text.
    """
    return (
        "$ErrorActionPreference='Stop'\n"
        "Add-Type -TypeDefinition @'\n"
        f"{_DISPLAY_TOPOLOGY_CS}\n"
        "'@\n"
        f"{call}"
    )


def parse_monitors(payload: str) -> list[Monitor]:
    """Parse the lines printed by the display topology helper.

    Each line is ``instance_id<TAB>name<TAB>1`` (on the desktop) or ``...<TAB>0`` (detached).
    """
    monitors: list[Monitor] = []
    for line in payload.splitlines():
        parts = line.rstrip("\r").split("\t")
        if len(parts) != 3 or not parts[0]:
            continue
        instance_id, name, active = parts
        monitors.append(Monitor(instance_id=instance_id, name=name or instance_id, enabled=active == "1"))
    return monitors


def list_monitors() -> list[Monitor]:
    """Return connected monitors and whether each one is part of the desktop."""
    return parse_monitors(run_powershell(_ps_script("[DisplayTopology]::List()")))


def set_monitor_enabled(instance_id: str, enabled: bool) -> None:
    """Attach or detach one monitor from the Windows desktop.

    Args:
        instance_id: PnP-style instance ID of the monitor.
        enabled: True to attach the display to the desktop, False to detach it.

    Raises:
        PowerShellError: The display topology could not be changed.
    """
    flag = "$true" if enabled else "$false"
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    state_file = os.path.join(base, "display-switch", "topology-state.txt")
    run_powershell(
        _ps_script(f"[DisplayTopology]::Set({_ps_quote(instance_id)}, {flag}, {_ps_quote(state_file)})")
    )


def check_disable_allowed(monitors: list[Monitor], targets: list[str]) -> None:
    """Refuse a disable request that would leave no active monitor.

    The guard protects the desktop by keeping at least one monitor attached.
    """
    target_set = set(targets)
    currently_enabled_targets = any(m.enabled and m.instance_id in target_set for m in monitors)
    remaining = {m.instance_id for m in monitors if m.enabled} - target_set
    if currently_enabled_targets and not remaining:
        raise GuardError("Refusing to disable the last active monitor; the desktop would be unusable.")


def verify_change(result: ChangeResult, enabled: bool) -> ChangeResult:
    """Re-query Windows and move any change that did not take effect to failed.

    A PowerShell call can return success without changing the desktop topology,
    so the reported state is checked afterwards.

    Args:
        result: The result of the change attempts.
        enabled: The state that was requested for the succeeded devices.

    Returns:
        The same result object, updated in place.
    """
    if not result.succeeded:
        return result
    actual = {m.instance_id: m.enabled for m in list_monitors()}
    verified: list[str] = []
    for iid in result.succeeded:
        if actual.get(iid) == enabled:
            verified.append(iid)
        else:
            state = "enabled" if actual.get(iid) else "disabled"
            result.failed[iid] = f"Windows still reports the monitor as {state}"
    result.succeeded = verified
    return result


def apply_change(instance_ids: list[str], enabled: bool) -> ChangeResult:
    """Enable or disable several monitors, recording per-monitor failures."""
    monitors = list_monitors()
    if not enabled:
        check_disable_allowed(monitors, instance_ids)

    known = {m.instance_id for m in monitors}
    result = ChangeResult()
    for iid in dict.fromkeys(instance_ids):
        if iid not in known:
            result.failed[iid] = "Monitor not found"
            continue
        try:
            set_monitor_enabled(iid, enabled)
        except PowerShellError as exc:
            result.failed[iid] = str(exc)
        else:
            result.succeeded.append(iid)
    return verify_change(result, enabled)
