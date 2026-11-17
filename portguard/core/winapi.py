"""Объявления Win32 API для PortGuard.

Проект сознательно не зависит от pywin32: всё нужное объявлено через ctypes,
поэтому сборка PyInstaller не тянет лишние бинарники, а приложение работает на
«чистой» Windows с одним Python.

Здесь только объявления: константы, структуры и прототипы функций с
проверенными argtypes/restype. Логика лежит в setupapi.py, holders.py,
hotplug.py и serial_monitor.py.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

if sys.platform != "win32":
    raise RuntimeError("PortGuard поддерживает только Windows")

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

# ---------------------------------------------------------------------------
# Базовые типы
# ---------------------------------------------------------------------------
HDEVINFO = wintypes.HANDLE
HKEY = wintypes.HANDLE
HANDLE = wintypes.HANDLE
DEVINST = wintypes.DWORD
CONFIGRET = wintypes.ULONG
DEVPROPTYPE = wintypes.ULONG
DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
LRESULT = ctypes.c_ssize_t
NTSTATUS = ctypes.c_long

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_NO_MORE_ITEMS = 259
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_SUCCESS = 0

# ---------------------------------------------------------------------------
# SetupAPI: флаги и свойства
# ---------------------------------------------------------------------------
DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004

SPDRP_DEVICEDESC = 0x00000000
SPDRP_HARDWAREID = 0x00000001
SPDRP_COMPATIBLEIDS = 0x00000002
SPDRP_SERVICE = 0x00000004
SPDRP_CLASS = 0x00000007
SPDRP_CLASSGUID = 0x00000008
SPDRP_DRIVER = 0x00000009
SPDRP_MFG = 0x0000000B
SPDRP_FRIENDLYNAME = 0x0000000C
SPDRP_LOCATION_INFORMATION = 0x0000000D
SPDRP_ENUMERATOR_NAME = 0x00000016
SPDRP_INSTALL_STATE = 0x00000022
SPDRP_LOCATION_PATHS = 0x00000023

DIF_PROPERTYCHANGE = 0x00000012
DICS_ENABLE = 0x00000001
DICS_DISABLE = 0x00000002
DICS_PROPCHANGE = 0x00000003
DICS_FLAG_GLOBAL = 0x00000001
DICS_FLAG_CONFIGSPECIFIC = 0x00000002

DIREG_DEV = 0x00000001
KEY_READ = 0x00020019

# DEVPROP_TYPE_*
DEVPROP_TYPE_STRING = 0x00000012
DEVPROP_TYPE_STRING_LIST = 0x00002012
DEVPROP_TYPE_UINT32 = 0x00000007

# ---------------------------------------------------------------------------
# Диспетчер устройств: статусы и коды проблем
# ---------------------------------------------------------------------------
DN_ROOT_ENUMERATED = 0x00000001
DN_DRIVER_LOADED = 0x00000002
DN_STARTED = 0x00000008
DN_MANUAL = 0x00000010
DN_HAS_PROBLEM = 0x00000400
DN_DISABLEABLE = 0x00002000
DN_REMOVABLE = 0x00004000
DN_PRIVATE_PROBLEM = 0x00008000
DN_WILL_BE_REMOVED = 0x00040000
DN_NEED_RESTART = 0x00000100

CM_PROB_NOT_CONFIGURED = 0x01
CM_PROB_DEVLOADER_FAILED = 0x02
CM_PROB_OUT_OF_MEMORY = 0x03
CM_PROB_ENTRY_IS_WRONG_TYPE = 0x04
CM_PROB_LACKED_ARBITRATOR = 0x05
CM_PROB_BOOT_CONFIG_CONFLICT = 0x06
CM_PROB_FAILED_FILTER = 0x07
CM_PROB_DEVLOADER_NOT_FOUND = 0x08
CM_PROB_INVALID_DATA = 0x09
CM_PROB_FAILED_START = 0x0A
CM_PROB_LIAR = 0x0B
CM_PROB_NORMAL_CONFLICT = 0x0C
CM_PROB_NOT_VERIFIED = 0x0D
CM_PROB_NEED_RESTART = 0x0E
CM_PROB_REENUMERATION = 0x0F
CM_PROB_PARTIAL_LOG_CONF = 0x10
CM_PROB_UNKNOWN_RESOURCE = 0x11
CM_PROB_REINSTALL = 0x12
CM_PROB_REGISTRY = 0x13
CM_PROB_VXDLDR = 0x14
CM_PROB_WILL_BE_REMOVED = 0x15
CM_PROB_DISABLED = 0x16
CM_PROB_DEVLOADER_NOT_READY = 0x17
CM_PROB_DEVICE_NOT_THERE = 0x18
CM_PROB_MOVED = 0x19
CM_PROB_TOO_EARLY = 0x1A
CM_PROB_NO_VALID_LOG_CONF = 0x1B
CM_PROB_FAILED_INSTALL = 0x1C
CM_PROB_HARDWARE_DISABLED = 0x1D
CM_PROB_CANT_SHARE_IRQ = 0x1E
CM_PROB_FAILED_ADD = 0x1F
CM_PROB_DISABLED_SERVICE = 0x20
CM_PROB_TRANSLATION_FAILED = 0x21
CM_PROB_NO_SOFTCONFIG = 0x22
CM_PROB_BIOS_TABLE = 0x23
CM_PROB_IRQ_TRANSLATION_FAILED = 0x24
CM_PROB_FAILED_DRIVER_ENTRY = 0x25
CM_PROB_DRIVER_FAILED_PRIOR_UNLOAD = 0x26
CM_PROB_DRIVER_FAILED_LOAD = 0x27
CM_PROB_DRIVER_SERVICE_KEY_INVALID = 0x28
CM_PROB_LEGACY_SERVICE_NO_DEVICES = 0x29
CM_PROB_DUPLICATE_DEVICE = 0x2A
CM_PROB_FAILED_POST_START = 0x2B
CM_PROB_HALTED = 0x2C
CM_PROB_PHANTOM = 0x2D
CM_PROB_SYSTEM_SHUTDOWN = 0x2E
CM_PROB_HELD_FOR_EJECT = 0x2F
CM_PROB_DRIVER_BLOCKED = 0x30
CM_PROB_REGISTRY_TOO_LARGE = 0x31
CM_PROB_SETPROPERTIES_FAILED = 0x32
CM_PROB_WAITING_ON_DEPENDENCY = 0x33
CM_PROB_UNSIGNED_DRIVER = 0x34
CM_PROB_USED_BY_DEBUGGER = 0x35
CM_PROB_DEVICE_RESET = 0x36
CM_PROB_CONSOLE_LOCKED = 0x37
CM_PROB_NEED_CLASS_CONFIG = 0x38
CM_PROB_GUEST_ASSIGNMENT_FAILED = 0x39

CR_SUCCESS = 0x00000000
CR_REMOVE_VETOED = 0x00000017
CR_NO_SUCH_DEVNODE = 0x0000000D

CM_EJECT_NORMAL = 0x00000000
CM_EJECT_REMOVE = 0x00000002

# PNP_VETO_TYPE
PNP_VETO_UNKNOWN = 0
PNP_VETO_LEGACY_DEVICE = 1
PNP_VETO_PENDING_CLOSE = 2
PNP_VETO_WINDOWS_APP = 3
PNP_VETO_WINDOWS_SERVICE = 4
PNP_VETO_OUTSTANDING_OPEN = 5
PNP_VETO_DEVICE = 6
PNP_VETO_DRIVER = 7
PNP_VETO_ILLEGAL_DEVICE_REQUEST = 8
PNP_VETO_INSUFFICIENT_POWER = 9
PNP_VETO_NON_DISABLEABLE = 10
PNP_VETO_LEGACY_DRIVER = 11
PNP_VETO_INSUFFICIENT_RIGHTS = 12

# ---------------------------------------------------------------------------
# Окна и сообщения (наблюдение за hot-plug)
# ---------------------------------------------------------------------------
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVNODES_CHANGED = 0x0007

HWND_MESSAGE = wintypes.HWND(-3)
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
CW_USEDEFAULT = 0x80000000

# ---------------------------------------------------------------------------
# NT: перечисление хендлов процессов
# ---------------------------------------------------------------------------
SystemExtendedHandleInformation = 64
STATUS_SUCCESS = 0
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
STATUS_BUFFER_OVERFLOW = 0x80000005
STATUS_BUFFER_TOO_SMALL = 0xC0000023
STATUS_ACCESS_DENIED = 0xC0000022
STATUS_INVALID_HANDLE = 0xC0000008

ObjectNameInformation = 1
ObjectTypeInformation = 2

PROCESS_DUP_HANDLE = 0x0040
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DUPLICATE_SAME_ACCESS = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002
SE_DEBUG_NAME = "SeDebugPrivilege"


# ---------------------------------------------------------------------------
# Структуры
# ---------------------------------------------------------------------------
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __str__(self) -> str:
        tail = "".join(f"{b:02x}" for b in self.Data4)
        return (
            f"{self.Data1:08x}-{self.Data2:04x}-{self.Data3:04x}-"
            f"{tail[:4]}-{tail[4:]}"
        )


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_CLASSINSTALL_HEADER(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InstallFunction", wintypes.DWORD),
    ]


class SP_PROPCHANGE_PARAMS(ctypes.Structure):
    _fields_ = [
        ("ClassInstallHeader", SP_CLASSINSTALL_HEADER),
        ("StateChange", wintypes.DWORD),
        ("Scope", wintypes.DWORD),
        ("HwProfile", wintypes.DWORD),
    ]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


class SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX(ctypes.Structure):
    _fields_ = [
        ("Object", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_void_p),
        ("HandleValue", ctypes.c_void_p),
        ("GrantedAccess", wintypes.ULONG),
        ("CreatorBackTraceIndex", wintypes.USHORT),
        ("ObjectTypeIndex", wintypes.USHORT),
        ("HandleAttributes", wintypes.ULONG),
        ("Reserved", wintypes.ULONG),
    ]


class SYSTEM_HANDLE_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("NumberOfHandles", ctypes.c_void_p),
        ("Reserved", ctypes.c_void_p),
        ("Handles", SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX * 1),
    ]


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


# ---------------------------------------------------------------------------
# Прототипы: SetupAPI
# ---------------------------------------------------------------------------
setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
]
setupapi.SetupDiGetClassDevsW.restype = HDEVINFO

setupapi.SetupDiDestroyDeviceInfoList.argtypes = [HDEVINFO]
setupapi.SetupDiDestroyDeviceInfoList.restype = BOOL

setupapi.SetupDiEnumDeviceInfo.argtypes = [
    HDEVINFO,
    wintypes.DWORD,
    ctypes.POINTER(SP_DEVINFO_DATA),
]
setupapi.SetupDiEnumDeviceInfo.restype = BOOL

setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    HDEVINFO,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.LPWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
setupapi.SetupDiGetDeviceInstanceIdW.restype = BOOL

setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
    HDEVINFO,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(ctypes.c_ubyte),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
setupapi.SetupDiGetDeviceRegistryPropertyW.restype = BOOL

setupapi.SetupDiGetDevicePropertyW.argtypes = [
    HDEVINFO,
    ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(DEVPROPKEY),
    ctypes.POINTER(DEVPROPTYPE),
    ctypes.POINTER(ctypes.c_ubyte),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
]
setupapi.SetupDiGetDevicePropertyW.restype = BOOL

setupapi.SetupDiOpenDevRegKey.argtypes = [
    HDEVINFO,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
]
setupapi.SetupDiOpenDevRegKey.restype = HKEY

setupapi.SetupDiCreateDeviceInfoList.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.HWND,
]
setupapi.SetupDiCreateDeviceInfoList.restype = HDEVINFO

setupapi.SetupDiOpenDeviceInfoW.argtypes = [
    HDEVINFO,
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.POINTER(SP_DEVINFO_DATA),
]
setupapi.SetupDiOpenDeviceInfoW.restype = BOOL

setupapi.SetupDiSetClassInstallParamsW.argtypes = [
    HDEVINFO,
    ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(SP_CLASSINSTALL_HEADER),
    wintypes.DWORD,
]
setupapi.SetupDiSetClassInstallParamsW.restype = BOOL

setupapi.SetupDiCallClassInstaller.argtypes = [
    wintypes.DWORD,
    HDEVINFO,
    ctypes.POINTER(SP_DEVINFO_DATA),
]
setupapi.SetupDiCallClassInstaller.restype = BOOL

# ---------------------------------------------------------------------------
# Прототипы: конфигурационный менеджер
# ---------------------------------------------------------------------------
cfgmgr32.CM_Get_DevNode_Status.argtypes = [
    ctypes.POINTER(wintypes.ULONG),
    ctypes.POINTER(wintypes.ULONG),
    DEVINST,
    wintypes.ULONG,
]
cfgmgr32.CM_Get_DevNode_Status.restype = CONFIGRET

cfgmgr32.CM_Get_Parent.argtypes = [
    ctypes.POINTER(DEVINST),
    DEVINST,
    wintypes.ULONG,
]
cfgmgr32.CM_Get_Parent.restype = CONFIGRET

cfgmgr32.CM_Get_Device_IDW.argtypes = [
    DEVINST,
    wintypes.LPWSTR,
    wintypes.ULONG,
    wintypes.ULONG,
]
cfgmgr32.CM_Get_Device_IDW.restype = CONFIGRET

cfgmgr32.CM_Request_Device_EjectW.argtypes = [
    DEVINST,
    ctypes.POINTER(ctypes.c_int),
    wintypes.LPWSTR,
    wintypes.ULONG,
    wintypes.ULONG,
]
cfgmgr32.CM_Request_Device_EjectW.restype = CONFIGRET

cfgmgr32.CM_Locate_DevNodeW.argtypes = [
    ctypes.POINTER(DEVINST),
    wintypes.LPCWSTR,
    wintypes.ULONG,
]
cfgmgr32.CM_Locate_DevNodeW.restype = CONFIGRET

# ---------------------------------------------------------------------------
# Прототипы: ядро, реестр, окна, NT
# ---------------------------------------------------------------------------
kernel32.QueryDosDeviceW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
kernel32.QueryDosDeviceW.restype = wintypes.DWORD

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = HANDLE

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = HANDLE

kernel32.GetCurrentProcessId.argtypes = []
kernel32.GetCurrentProcessId.restype = wintypes.DWORD

kernel32.DuplicateHandle.argtypes = [
    HANDLE,
    HANDLE,
    HANDLE,
    ctypes.POINTER(HANDLE),
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
]
kernel32.DuplicateHandle.restype = BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

advapi32.RegQueryValueExW.argtypes = [
    HKEY,
    wintypes.LPCWSTR,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.POINTER(wintypes.DWORD),
]
advapi32.RegQueryValueExW.restype = wintypes.LONG

advapi32.RegCloseKey.argtypes = [HKEY]
advapi32.RegCloseKey.restype = wintypes.LONG

advapi32.OpenProcessToken.argtypes = [
    HANDLE,
    wintypes.DWORD,
    ctypes.POINTER(HANDLE),
]
advapi32.OpenProcessToken.restype = BOOL

advapi32.LookupPrivilegeValueW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.POINTER(LUID),
]
advapi32.LookupPrivilegeValueW.restype = BOOL

advapi32.AdjustTokenPrivileges.argtypes = [
    HANDLE,
    wintypes.BOOL,
    ctypes.POINTER(TOKEN_PRIVILEGES),
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
advapi32.AdjustTokenPrivileges.restype = BOOL

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.WORD

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = LRESULT

user32.GetMessageW.argtypes = [
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.GetMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT

user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostMessageW.restype = BOOL

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = BOOL

ntdll.NtQuerySystemInformation.argtypes = [
    wintypes.ULONG,
    ctypes.c_void_p,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
ntdll.NtQuerySystemInformation.restype = NTSTATUS

ntdll.NtQueryObject.argtypes = [
    HANDLE,
    wintypes.ULONG,
    ctypes.c_void_p,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
ntdll.NtQueryObject.restype = NTSTATUS

shell32.IsUserAnAdmin.argtypes = []
shell32.IsUserAnAdmin.restype = BOOL

shell32.ShellExecuteW.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_int,
]
shell32.ShellExecuteW.restype = wintypes.HINSTANCE
