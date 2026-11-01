"""Windows: the Claude app may start these scripts with a bare environment, without USERPROFILE or APPDATA.
Python then cannot find the home folder ("~" stays "~") and os.environ["APPDATA"] fails, so every script
stops before it starts and /qosmopol seemed to work while nothing ran (owner's Windows PC, 2026-11-01).
Importing this fills both in, from Windows' own record of the folders. Nothing happens on macOS."""
import os
import sys

# KNOWNFOLDERID of the profile folder and of the roaming application data folder
FOLDERS = {"USERPROFILE": "5E6C858F-0E22-4760-9AFE-EA3317B67173", "APPDATA": "3EB685DB-65F9-4CF6-A03A-E3EF65729F3D"}


def known_folder(guid):
    """The folder Windows records under this KNOWNFOLDERID, or None."""
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        u = uuid.UUID(guid)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
        path = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(path)):
            return None
        try:
            return path.value
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path)
    except Exception:
        return None


if sys.platform == "win32":
    for name, guid in FOLDERS.items():
        if os.environ.get(name):
            continue
        found = known_folder(guid)
        if not found and name == "USERPROFILE" and os.environ.get("HOMEPATH"):
            found = os.environ.get("HOMEDRIVE", "") + os.environ["HOMEPATH"]
        if not found and name == "APPDATA" and os.environ.get("USERPROFILE"):
            found = os.path.join(os.environ["USERPROFILE"], "AppData", "Roaming")
        if found:
            os.environ[name] = found  # the server's own children inherit it too
