"""Run a program on a hidden desktop and drive its windows by message.

Nothing reaches the user's screens (works over RDP too). Shared by the probe
and the conformance harness."""
import ctypes, ctypes.wintypes as W, subprocess, time
u = ctypes.WinDLL('user32', use_last_error=True)
k = ctypes.WinDLL('kernel32', use_last_error=True)
EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
u.CreateDesktopW.restype = W.HANDLE
u.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]; u.SendMessageW.restype = W.LPARAM
u.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, ctypes.POINTER(ctypes.c_size_t)]
u.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
u.EnumDesktopWindows.argtypes = [W.HANDLE, EnumProc, W.LPARAM]
DESK = 'rpharness'
_desk = None


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [('cb', W.DWORD), ('r', W.LPWSTR), ('desk', W.LPWSTR), ('title', W.LPWSTR)] + \
               [(n, W.DWORD) for n in 'x y w h cx cy fill flags'.split()] + \
               [('show', W.WORD), ('r2', W.WORD), ('r3', ctypes.c_void_p), ('i', W.HANDLE), ('o', W.HANDLE), ('e', W.HANDLE)]


class PI(ctypes.Structure):
    _fields_ = [('hp', W.HANDLE), ('ht', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


def launch(cmdline, cwd, env=None, log=None):
    """Start cmdline on the hidden desktop; returns its pid. log: a file for its stdout and stderr."""
    global _desk
    if not _desk:
        _desk = u.CreateDesktopW(DESK, None, None, 0, 0x10000000, None)   # GENERIC_ALL
    si = STARTUPINFOW(); si.cb = ctypes.sizeof(si); si.desk = 'WinSta0\\' + DESK
    pi = PI()
    inherit = False
    if log:
        import msvcrt
        fh = open(log, 'wb')
        h = msvcrt.get_osfhandle(fh.fileno())
        k.SetHandleInformation(W.HANDLE(h), 1, 1)          # HANDLE_FLAG_INHERIT
        si.flags |= 0x100                                  # STARTF_USESTDHANDLES
        si.o = si.e = h
        inherit = True
    eb = None
    if env is not None:
        eb = ctypes.create_unicode_buffer(''.join('%s=%s\0' % kv for kv in env.items()) + '\0')
    if not k.CreateProcessW(None, ctypes.create_unicode_buffer(cmdline), None, None, inherit,
                            0x400 if eb else 0, eb, cwd, ctypes.byref(si), ctypes.byref(pi)):
        raise OSError(ctypes.get_last_error())
    return pi.pid


def kill(pid):
    subprocess.run(['taskkill', '/f', '/t', '/pid', str(pid)], capture_output=True)


def text(h):
    b = ctypes.create_unicode_buffer(1024)
    n = ctypes.c_size_t()
    u.SendMessageTimeoutW(h, 0x000D, 1024, ctypes.addressof(b), 2, 2000, ctypes.byref(n))   # WM_GETTEXT
    return b.value


def cls(h):
    c = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, c, 256); return c.value


def tops(pid):
    out = []
    def cb(h, _):
        p = W.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h): out.append(h)
        return True
    u.EnumDesktopWindows(_desk, EnumProc(cb), 0)
    return out


def kids(h):
    out = []
    u.EnumChildWindows(h, EnumProc(lambda c, _: out.append(c) or True), 0)
    return out


def dump(pid):
    for h in tops(pid):
        print('%08X %r [%s]' % (h, text(h), cls(h)))
        for c in kids(h):
            if u.IsWindowVisible(c):
                print('    %08X id=%d %r [%s]' % (c, u.GetDlgCtrlID(c), text(c), cls(c)))


def wait(fn, what, timeout=30):
    t = time.time() + timeout
    while time.time() < t:
        r = fn()
        if r: return r
        time.sleep(0.25)
    raise TimeoutError(what)


def snap(h, path):
    """PrintWindow into a PNG (works on the hidden desktop)."""
    from PIL import Image
    r = W.RECT(); u.GetWindowRect(h, ctypes.byref(r)); w, hh = r.right - r.left, r.bottom - r.top
    g = ctypes.windll.gdi32
    dc = u.GetDC(h); mdc = g.CreateCompatibleDC(dc); bmp = g.CreateCompatibleBitmap(dc, w, hh)
    g.SelectObject(mdc, bmp); u.PrintWindow(h, mdc, 2)
    buf = ctypes.create_string_buffer(w * hh * 4)
    bi = (ctypes.c_uint32 * 10)(40, w, (-hh) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    g.GetDIBits(mdc, bmp, 0, hh, buf, bi, 0)
    Image.frombuffer('RGBA', (w, hh), buf, 'raw', 'BGRA', 0, 1).convert('RGB').save(path)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(h, dc)


def menu(m, ind=''):
    """Print a menu tree: id and text."""
    for i in range(u.GetMenuItemCount(m)):
        b = ctypes.create_unicode_buffer(256); u.GetMenuStringW(m, i, b, 256, 0x400)
        print(ind, u.GetMenuItemID(m, i), b.value)
        s = u.GetSubMenu(m, i)
        if s: menu(s, ind + '  ')
