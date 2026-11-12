/*
 * Retail Plus Lite - static recompilation host.
 *
 * A 32-bit host on pcrecomp's runtime/native32 (the native bridge, callbacks
 * and the machine lock; see its header). The lifted PLUSLITE.EXE is
 * CA-Visual Objects 2.x code; its runtime (CAVORT20, CAVO2GUI, CAVO2RDD, ...)
 * and the report DLLs are loaded natively from the app folder and called
 * through the bridge, and they call back into lifted code. What is here is only the guest
 * image, its folder, its command line and the fault report. From the
 * MechWarrior 3 host (mw3-recomp src/runtime/host.c).
 *
 * Linked at /BASE:0x60000000 (CMakeLists.txt) so 0x00400000 is free when
 * main() maps the image.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <psapi.h>

#include "native32.h"
#include "recomp_trace.h"

extern const uint32_t rp_entry_va;       /* recomp_dispatch.c */

#define RP_BASE 0x00400000u

static DWORD g_watchdog_s;
static char  g_app[MAX_PATH];            /* the app folder, with a trailing '\' */
static char  g_guest_exe[MAX_PATH], g_guest_cmdline[MAX_PATH + 1024];

#define ARG(n) MEM32(g_esp + 4 + 4 * (n))
#define RET(v, nargs) do { g_eax = (uint32_t)(v); g_esp += 4 + 4 * (nargs); } while (0)

/* The guest is PLUSLITE.EXE, not this host: its hInstance (menus, dialogs,
 * icons, strings) is GetModuleHandleA(NULL), which the VO start-up passes
 * on as the app's resource handle. */
static void shim_GetModuleHandleA(void) {
    uint32_t name = ARG(0);
    RET(name ? (uint32_t)(uintptr_t)GetModuleHandleA((const char*)(uintptr_t)name) : RP_BASE, 1);
}

/* The app reads its DBFs, reports and pictures from its own folder. */
static void shim_GetModuleFileNameA(void) {
    uint32_t h = ARG(0), size = ARG(2);
    char* out = (char*)(uintptr_t)ARG(1);
    if (h == 0 || h == RP_BASE) {
        uint32_t n = (uint32_t)strlen(g_guest_exe);
        if (size) {
            if (n >= size) n = size - 1;
            memcpy(out, g_guest_exe, n);
            out[n] = 0;
        }
        RET(n, 3);
        return;
    }
    RET(GetModuleFileNameA((HMODULE)(uintptr_t)h, out, size), 3);
}

static void shim_GetCommandLineA(void) { RET((uintptr_t)g_guest_cmdline, 0); }

static void shim_ExitProcess(void) {
    fprintf(stderr, "[exit] ExitProcess(%u)\n", ARG(0));
    ExitProcess(ARG(0));
}

/* The runtime DLLs ask Windows directly who the program is, and get this
 * host: GetModuleFileNameA(NULL) is build\retailplusrecomp.exe, so the
 * default inventory was looked for in build\TestData. Their imports of these
 * two are pointed here, so they see PLUSLITE.EXE in the app folder too. */
static DWORD WINAPI app_GetModuleFileNameA(HMODULE h, LPSTR out, DWORD size) {
    if (h == NULL || h == GetModuleHandleA(NULL) || (uintptr_t)h == RP_BASE) {
        DWORD n = (DWORD)strlen(g_guest_exe);
        if (!size) return 0;
        if (n >= size) n = size - 1;
        memcpy(out, g_guest_exe, n);
        out[n] = 0;
        return n;
    }
    return GetModuleFileNameA(h, out, size);
}

static HMODULE WINAPI app_GetModuleHandleA(LPCSTR name) {
    return name ? GetModuleHandleA(name) : (HMODULE)(uintptr_t)RP_BASE;
}

static void app_module(HMODULE m);

/* The database drivers (*.RDD) are loaded later, by CAVO2RDD: each one gets
 * the same treatment when it arrives. (Loading them all up front instead
 * crashed in ntdll: VO registers a driver when it loads it.) */
static HMODULE WINAPI app_LoadLibraryA(LPCSTR name) {
    HMODULE m = LoadLibraryA(name);
    if (m) app_module(m);
    return m;
}

/* --native-trace: the runtime DLLs' own file I/O, which no bridge sees. */
static HANDLE WINAPI app_CreateFileA(LPCSTR n, DWORD a, DWORD sh, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t) {
    HANDLE h = CreateFileA(n, a, sh, sa, c, f, t);
    if (native32_trace_native) fprintf(stderr, "[dll] CreateFileA %s -> %p (%lu)\n", n, h, GetLastError());
    return h;
}

static BOOL WINAPI app_ReadFile(HANDLE h, LPVOID b, DWORD n, LPDWORD got, LPOVERLAPPED o) {
    BOOL r = ReadFile(h, b, n, got, o);
    if (native32_trace_native) {
        fprintf(stderr, "[dll] ReadFile %p %lu -> %d %lu:", h, n, r, got ? *got : 0);
        for (DWORD i = 0; got && i < *got && i < 16; i++) fprintf(stderr, " %02X", ((uint8_t*)b)[i]);
        fprintf(stderr, "\n");
    }
    return r;
}

static void patch_iat(HMODULE m) {
    uint8_t* b = (uint8_t*)m;
    IMAGE_NT_HEADERS32* nt = (IMAGE_NT_HEADERS32*)(b + ((IMAGE_DOS_HEADER*)b)->e_lfanew);
    IMAGE_DATA_DIRECTORY* dd = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dd->VirtualAddress) return;
    for (IMAGE_IMPORT_DESCRIPTOR* d = (IMAGE_IMPORT_DESCRIPTOR*)(b + dd->VirtualAddress); d->Name; d++) {
        if (_stricmp((char*)(b + d->Name), "KERNEL32.DLL") || !d->OriginalFirstThunk) continue;
        IMAGE_THUNK_DATA32* n = (IMAGE_THUNK_DATA32*)(b + d->OriginalFirstThunk);
        IMAGE_THUNK_DATA32* a = (IMAGE_THUNK_DATA32*)(b + d->FirstThunk);
        for (; n->u1.AddressOfData; n++, a++) {
            if (n->u1.Ordinal & IMAGE_ORDINAL_FLAG32) continue;
            const char* fn = (const char*)((IMAGE_IMPORT_BY_NAME*)(b + n->u1.AddressOfData))->Name;
            void* to = !strcmp(fn, "GetModuleFileNameA") ? (void*)app_GetModuleFileNameA
                     : !strcmp(fn, "GetModuleHandleA") ? (void*)app_GetModuleHandleA
                     : !strcmp(fn, "LoadLibraryA") ? (void*)app_LoadLibraryA
                     : !strcmp(fn, "CreateFileA") ? (void*)app_CreateFileA
                     : !strcmp(fn, "ReadFile") ? (void*)app_ReadFile : NULL;
            DWORD old;
            if (to && VirtualProtect(&a->u1.Function, 4, PAGE_READWRITE, &old)) {
                a->u1.Function = (DWORD)(uintptr_t)to;
                VirtualProtect(&a->u1.Function, 4, old, &old);
            }
        }
    }
}

/* The Visual Objects runtime is called the way VO's compiler calls it, not
 * by the C ABI: every function's prologue runs `mov eax, esp; call
 * INCKidStackPtr` and `call __chkstk` (which moves esp), and _NCARG, _GAS
 * and friends read the caller's frame through ebp. Through native_bridge
 * (host stack, C arguments only) _NCARG returned the bytes of a function
 * prologue and the app stopped at a MessageBox of garbage. So every DLL from
 * the app folder (the VO runtime, its database drivers and the report DLLs)
 * is entered on the guest's stack with the guest's registers
 * (native32_add_guest_abi), and its imports are patched as above. */
static void app_module(HMODULE m) {
    static HMODULE done[256];
    static int ndone;
    char path[MAX_PATH];
    MODULEINFO mi;
    for (int i = 0; i < ndone; i++)
        if (done[i] == m) return;
    if (!GetModuleFileNameA(m, path, MAX_PATH) || _strnicmp(path, g_app, strlen(g_app))) return;
    if (!GetModuleInformation(GetCurrentProcess(), m, &mi, sizeof mi) || ndone == 256) return;
    done[ndone++] = m;
    native32_add_guest_abi((uint32_t)(uintptr_t)mi.lpBaseOfDll, mi.SizeOfImage);
    patch_iat(m);
    fprintf(stderr, "  %s: guest registers\n", path + strlen(g_app));
}

static void enter_app_dlls_with_guest_registers(void) {
    HMODULE mods[256];
    DWORD need = 0;
    if (!EnumProcessModules(GetCurrentProcess(), mods, sizeof mods, &need)) return;
    for (DWORD i = 0; i < need / sizeof mods[0] && i < 256; i++) app_module(mods[i]);
}

static native32_shim_t g_shims[] = {
    { "GetModuleHandleA", shim_GetModuleHandleA },
    { "GetModuleFileNameA", shim_GetModuleFileNameA },
    { "GetCommandLineA", shim_GetCommandLineA },
    { "ExitProcess", shim_ExitProcess },
};

/* ------------------------------------------------------------ reports */

recomp_func_t recomp_lookup_manual(uint32_t va) { (void)va; return NULL; }

/* Added after native32's own handler, so callbacks are resolved first and
 * only real faults get here. */
static LONG CALLBACK crash(EXCEPTION_POINTERS* ep) {
    EXCEPTION_RECORD* r = ep->ExceptionRecord;
    if ((r->ExceptionCode & 0xF0000000u) != 0xC0000000u) {
        fprintf(stderr, "[exception] 0x%08lX at 0x%p, in sub_%08X, last native call %s\n",
                r->ExceptionCode, r->ExceptionAddress, g_cur_func, g_cur_import);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    fprintf(stderr, "\n=== fault 0x%08lX at 0x%p ===\n", r->ExceptionCode, r->ExceptionAddress);
    if (r->ExceptionCode == EXCEPTION_ACCESS_VIOLATION && r->NumberParameters >= 2) {
        ULONG_PTR op = r->ExceptionInformation[0];
        uint32_t at = (uint32_t)r->ExceptionInformation[1];
        fprintf(stderr, "  %s of 0x%08X%s\n", op == 0 ? "read" : op == 1 ? "write" : "execute", at,
                native32_in_guest(at) ? " (inside the guest image)" : at < 0x10000 ? " (null/low)" : "");
    }
    recomp_trace_flush();
    fprintf(stderr, "  in lifted sub_%08X, last native call %s\n", g_cur_func, g_cur_import);
    fprintf(stderr, "  eax=%08X ecx=%08X edx=%08X ebx=%08X esp=%08X ebp=%08X esi=%08X edi=%08X\n",
            g_eax, g_ecx, g_edx, g_ebx, g_esp, g_ebp, g_esi, g_edi);
    native32_dump_icalls(12);
    recomp_dump_trace("fault");
    TerminateProcess(GetCurrentProcess(), 3);
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI watchdog(LPVOID unused) {
    (void)unused;
    Sleep(g_watchdog_s * 1000);
    fprintf(stderr, "\n[watchdog] %lu s: in sub_%08X, last native call %s\n",
            g_watchdog_s, g_cur_func, g_cur_import);
    TerminateProcess(GetCurrentProcess(), 4);
    return 0;
}

int main(int argc, char** argv) {
    const char* app = "game";
    const char* args = "";
    int run = 0, native_exe = 0;
    setvbuf(stderr, NULL, _IONBF, 0);
    for (int i = 1; i < argc; i++) {
        int n = recomp_trace_arg(argc, argv, i);
        if (n) { i += n - 1; continue; }
        if (!strcmp(argv[i], "--run")) run = 1;
        else if (!strcmp(argv[i], "--game") && i + 1 < argc) app = argv[++i];
        else if (!strcmp(argv[i], "--args") && i + 1 < argc) args = argv[++i];
        else if (!strcmp(argv[i], "--watchdog") && i + 1 < argc) g_watchdog_s = strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--native-trace")) native32_trace_native = 1;
        else if (!strcmp(argv[i], "--callbacks")) native32_trace_callbacks = 1;
        else if (!strcmp(argv[i], "--native-exe")) native_exe = 1;
        else {
            printf("usage: retailplusrecomp  [--run] [--game DIR] [--args \"GUEST ARGS\"] [--watchdog S]\n"
                   "                         [--native-trace] [--callbacks]\n"
                   "  without --run: map and bind PLUSLITE.EXE, then stop (no window)\n");
            recomp_trace_help();
            return argv[i][1] == 'h' || argv[i][2] == 'h' ? 0 : 1;
        }
    }
    GetFullPathNameA(app, MAX_PATH - 1, g_app, NULL);
    if (g_app[strlen(g_app) - 1] != '\\') strcat(g_app, "\\");
    _snprintf(g_guest_exe, sizeof g_guest_exe - 1, "%sPLUSLITE.EXE", g_app);
    _snprintf(g_guest_cmdline, sizeof g_guest_cmdline - 1, "\"%s\" %s", g_guest_exe, args);

    /* The VO runtime and report DLLs load natively, from the app folder. */
    SetDllDirectoryA(g_app);
    native32_init();
    AddVectoredExceptionHandler(0, crash);
    printf("Retail Plus Lite recomp host\n  lifted functions in dispatch: %u\n", recomp_dispatch_count);
    uint32_t span = native32_map(g_guest_exe, RP_BASE);
    if (!span) { fprintf(stderr, "cannot map %s at 0x%08X\n", g_guest_exe, RP_BASE); return 1; }
    printf("  mapped PLUSLITE.EXE: 0x%08X-0x%08X\n", RP_BASE, RP_BASE + span);
    int unresolved = native32_bind(RP_BASE, g_shims, (int)(sizeof g_shims / sizeof g_shims[0]));
    printf("  imports bound, %d unresolved\n", unresolved);
    if (unresolved) return 1;
    enter_app_dlls_with_guest_registers();
    /* Bisection: PLUSLITE.EXE's original code instead of its lift. */
    if (native_exe && native32_set_native(RP_BASE)) printf("  PLUSLITE.EXE runs natively (--native-exe)\n");
    if (!run) {
        printf("\n(dry run: image mapped and bound; --run enters 0x%08X)\n", rp_entry_va);
        return 0;
    }
    if (!SetCurrentDirectoryA(g_app)) { fprintf(stderr, "cannot enter %s\n", g_app); return 1; }
    if (g_watchdog_s) CloseHandle(CreateThread(NULL, 0, watchdog, NULL, 0, NULL));
    printf("  entering 0x%08X\n\n", rp_entry_va);
    fflush(stdout);
    native32_call_guest(rp_entry_va, 0, NULL);
    printf("\nentry returned eax=%08X\n", g_eax);
    return (int)g_eax;
}
