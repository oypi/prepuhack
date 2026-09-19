import re
import os
import sys
import struct
import time
import json
import base64
import shutil
import zipfile
import io
import platform
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_LINUX = SYSTEM == "Linux"
IS_MACOS = SYSTEM == "Darwin"


def detect_gd_path() -> Path:
    candidates: List[Path] = []
    if IS_WINDOWS:
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        candidates = [
            Path(pf86) / "Steam" / "steamapps" / "common" / "Geometry Dash",
            Path(pf) / "Steam" / "steamapps" / "common" / "Geometry Dash",
        ]
    elif IS_LINUX:
        home = Path.home()
        xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        candidates = [
            home / ".steam" / "steam" / "steamapps" / "common" / "Geometry Dash",
            home / ".steam" / "root" / "steamapps" / "common" / "Geometry Dash",
            home / ".steam" / "debian-installation" / "steamapps" / "common" / "Geometry Dash",
            xdg_data / "Steam" / "steamapps" / "common" / "Geometry Dash",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam" / "steamapps" / "common" / "Geometry Dash",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "common" / "Geometry Dash",
            home / "snap" / "steam" / "common" / ".steam" / "steam" / "steamapps" / "common" / "Geometry Dash",
        ]
    elif IS_MACOS:
        home = Path.home()
        candidates = [
            home / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / "Geometry Dash" / "Geometry Dash.app" / "Contents" / "Resources",
            home / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / "Geometry Dash",
        ]

    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if candidates else Path(".")


def detect_localappdata() -> Path:
    if IS_WINDOWS:
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            return Path(appdata)
        return Path.home() / "AppData" / "Local"

    home = Path.home()
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    proton_prefixes = [
        home / ".steam" / "steam" / "steamapps" / "compatdata" / "322170" / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local",
        home / ".steam" / "root" / "steamapps" / "compatdata" / "322170" / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local",
        xdg_data / "Steam" / "steamapps" / "compatdata" / "322170" / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local",
        home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "compatdata" / "322170" / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / "322170" / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local",
    ]
    for p in proton_prefixes:
        if p.exists():
            return p
    return proton_prefixes[0]


def detect_geode_data_dir() -> Path:
    if IS_WINDOWS:
        return detect_localappdata() / "GeometryDash" / "geode"
    home = Path.home()
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    linux_candidates = [
        xdg_data / "GeometryDash" / "geode",
        home / ".local" / "share" / "GeometryDash" / "geode",
        detect_localappdata() / "GeometryDash" / "geode",
    ]
    for c in linux_candidates:
        if c.exists():
            return c
    return linux_candidates[0]


GD_PATH = detect_gd_path()
LOCALAPPDATA = detect_localappdata()
GEODE_DATA = detect_geode_data_dir()
ORIGINAL_MOD_ID = "absolllute.megahack"
CUSTOM_MOD_ID = "oneypi.prepuhack"
ORIGINAL_DLL = f"{ORIGINAL_MOD_ID}.dll"
CUSTOM_DLL = f"{CUSTOM_MOD_ID}.dll"
GEODE_FILENAME = f"{CUSTOM_MOD_ID}.geode"

CUSTOM_NAME = "PrepuHack"
CUSTOM_DEVELOPER = "oneypi"
CUSTOM_DESCRIPTION = "long live the prepubros!"
CUSTOM_ABOUT = """# PrepuHack

PrepuHack is a customized Geometry Dash mod menu built by oneypi. long live the prepubros!

Press TAB to open the menu.

## Links

Made with love by the prepubros.
"""
CUSTOM_LOGO = Path(__file__).parent / "logo.png"
CYAN_ACCENT = 0x00CED1
CYAN_BACKGROUND = 0x1A2A2D
CYAN_TAB_TEXT = 0xFFFFFF

INSTALL_JSON_URL = "https://absolllute.com/api/mega_hack/v9/install.json"

RET_TRUE  = b"\xb8\x01\x00\x00\x00\xc3"
RET_FALSE = b"\xb8\x00\x00\x00\x00"
RET_VOID  = b"\xc3"

PROLOGUES = [
    re.compile(rb'\x56\x57\x48\x83\xEC'),
    re.compile(rb'\x55\x41\x56\x56\x57\x53'),
    re.compile(rb'\x55\x41\x57\x41\x56\x56\x57'),
    re.compile(rb'\x55\x41\x57\x41\x56\x41\x55'),
    re.compile(rb'\x48\x89\x5C\x24'),
    re.compile(rb'\x40\x53\x48\x83\xEC'),
    re.compile(rb'\x55\x56\x57\x48\x81\xEC'),
    re.compile(rb'\x55\x56\x57\x48\x83\xEC'),
]


def err(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def find_by_regex(data, pattern):
    m = pattern.search(data)
    return m.start() if m else None


def find_function_by_string_xref(data, anchor_string, search_back, prologue_patterns):
    image_base = 0x180000000
    str_offset = data.find(anchor_string)
    if str_offset == -1:
        return None
    str_va = image_base + str_offset
    text_end = min(len(data), 0x534000)
    for off in range(0, text_end - 7):
        if data[off] == 0x48 and data[off + 1] == 0x8d:
            modrm = data[off + 2]
            if (modrm & 0x07) == 5:
                disp = struct.unpack('<i', data[off + 3:off + 7])[0]
                target = image_base + off + 7 + disp
                if target == str_va:
                    for back in range(off, max(0, off - search_back), -1):
                        for pat in prologue_patterns:
                            if pat.match(data[back:back + 20]):
                                return back
    return None


def find_by_unique_constant(data, constant_bytes, search_back, prologue_patterns):
    text_end = min(len(data), 0x534000)
    matches = [m.start() for m in re.finditer(re.escape(constant_bytes), data) if m.start() < text_end]
    if not matches:
        return None
    for off in matches:
        for back in range(off, max(0, off - search_back), -1):
            for pat in prologue_patterns:
                if pat.match(data[back:back + 20]):
                    return back
    return None


def find_key_bypass_contextual(data):
    pat = re.compile(rb'\xBA\x10\x00\x00\x00.{0,20}\xE8....(?=\x48\x83\x7F)', re.DOTALL)
    m = pat.search(data)
    if m:
        sub = m.group()
        e8_pos = sub.rfind(b'\xe8')
        if e8_pos >= 0:
            return m.start() + e8_pos
    return None


def _try_strategies(name, strategies, payload):
    for strat_name, finder in strategies:
        offset = finder()
        if offset is not None:
            print(f"  [OK] '{strat_name}' -> {hex(offset)}")
            return (offset, strat_name, payload)
        else:
            print(f"  [--] '{strat_name}' no match")
    err(f"All strategies failed for {name}")


def find_all_targets(data):
    results = {}

    print("\n[1/4] ID_CHECK")
    results["ID_CHECK"] = _try_strategies("ID_CHECK", [
        ("primary_regex", lambda: find_by_regex(data,
            re.compile(rb'\x56\x57\x48\x83\xEC.\x48\x83\x79\x10\x40', re.DOTALL))),
        ("unique_cmp_0x40", lambda: find_by_unique_constant(data,
            b'\x48\x83\x79\x10\x40', 200, PROLOGUES)),
        ("near_MachineGuid", lambda: find_function_by_string_xref(data,
            b'MachineGuid\x00', 0x400, PROLOGUES)),
    ], RET_TRUE)

    print("\n[2/4] JSON_SIGNATURE_CHECK")
    results["JSON_SIG"] = _try_strategies("JSON_SIG", [
        ("primary_regex", lambda: find_by_regex(data,
            re.compile(rb'\x55\x41\x56\x56\x57\x53\x48\x83\xEC.\x48\x8D\x6C\x24.'
                        rb'\x48\xC7\x45.........\x0F\x84....\x4C\x89\xC7', re.DOTALL))),
        ("near_sig_invalid", lambda: find_function_by_string_xref(data,
            b'Error: Signature is INVALID\x00', 0x200, PROLOGUES)),
        ("near_pubkey_load", lambda: find_function_by_string_xref(data,
            b'failed to load public key from memory\x00', 0x300, PROLOGUES)),
        ("relaxed_regex", lambda: find_by_regex(data,
            re.compile(rb'\x55\x41\x56\x56\x57\x53\x48\x83\xEC.\x48\x8D\x6C\x24.'
                        rb'\x48\xC7\x45.{5,15}\x0F\x84', re.DOTALL))),
    ], RET_TRUE)

    print("\n[3/4] KEY_BYPASS")
    results["KEY_BYPASS"] = _try_strategies("KEY_BYPASS", [
        ("primary_regex", lambda: find_by_regex(data,
            re.compile(rb'(?<=.\x10\x00\x00\x00)\xE8....(?=\x48\x83\x7F)', re.DOTALL))),
        ("contextual", lambda: find_key_bypass_contextual(data)),
        ("relaxed_mov_edx", lambda: find_by_regex(data,
            re.compile(rb'\xBA\x10\x00\x00\x00.{0,8}\xE8....(?=\x48\x83\x7F)', re.DOTALL))),
    ], RET_FALSE)

    print("\n[4/4] BYPASS_VERIFY")
    verify_prologues = [re.compile(rb'\x55\x41\x57\x41\x56\x56\x57\x53\x48\x81\xEC')]
    results["BYPASS_VERIFY"] = _try_strategies("BYPASS_VERIFY", [
        ("primary_regex", lambda: find_by_regex(data,
            re.compile(rb'\x55\x41\x57\x41\x56\x56\x57\x53\x48\x81\xEC....'
                        rb'\x48\x8D\xAC\x24....\x48\xC7\x85........'
                        rb'\x48\x89\xD7\x48\x89\xCB', re.DOTALL))),
        ("near_LICENSE", lambda: find_function_by_string_xref(data,
            b'LICENSE\x00', 0x800, verify_prologues)),
        ("relaxed_large_frame", lambda: find_by_regex(data,
            re.compile(rb'\x55\x41\x57\x41\x56\x56\x57\x53\x48\x81\xEC..\x01\x00'
                        rb'\x48\x8D\xAC\x24', re.DOTALL))),
        ("relaxed_mov_rdi_rcx", lambda: find_by_regex(data,
            re.compile(rb'\x55\x41\x57\x41\x56(?:\x41\x55|\x41\x54)?\x56\x57\x53'
                        rb'\x48\x81\xEC.{2,4}\x48\x8D\xAC\x24.{2,6}'
                        rb'\x48\xC7\x85.{5,12}\x48\x89\xD7\x48\x89\xCB', re.DOTALL))),
    ], RET_VOID)

    return results


def apply_patches(data, targets):
    patched = bytearray(data)
    print("\nApplying patches:")
    for name, (offset, strategy, payload) in targets.items():
        original = bytes(patched[offset:offset + len(payload)])
        patched[offset:offset + len(payload)] = payload
        print(f"  {name:25s} @ {hex(offset):10s}  {original.hex()} -> {payload.hex()}  (via {strategy})")
    return bytes(patched)


def rename_in_dll(data, old_name, new_name):
    assert len(old_name) == len(new_name)
    count = data.count(old_name)
    if count > 0:
        data = data.replace(old_name, new_name)
        print(f"  Renamed {count}x '{old_name.decode()}' -> '{new_name.decode()}' in DLL")
    return data


def customize_mod_json(data):
    mod = json.loads(data.decode('utf-8'))
    mod['id'] = CUSTOM_MOD_ID
    mod['name'] = CUSTOM_NAME
    mod['developer'] = CUSTOM_DEVELOPER
    mod['description'] = CUSTOM_DESCRIPTION
    # Keep resource entries intact without modifying inner paths so Geode can uncompress and resolve them cleanly
    return json.dumps(mod, indent='\t').encode('utf-8')


def generate_license():
    chacha_key = bytes.fromhex("0E841FA5BFE5CE8FC91EB11ADD1DCEF694045BEEAFCF521BF4341D3997C1C219")
    identifier = os.urandom(32).hex().upper()
    token = os.urandom(16).hex().upper()
    secret = os.urandom(16).hex().upper()
    inner = json.dumps({
        "id": identifier, "token": token, "secret": secret,
        "timestamp": str(int(time.time())), "guid2": chacha_key.hex().upper(),
    }, separators=(",", ":"))
    return json.dumps({
        "data": base64.b64encode(inner.encode()).decode(),
        "sig": base64.b64encode(os.urandom(256)).decode(),
        "token": token,
    }, separators=(",", ":"))


def deploy_license(license_str):
    locations = []
    dirs_to_try = [
        LOCALAPPDATA / ORIGINAL_MOD_ID,
        LOCALAPPDATA / CUSTOM_MOD_ID,
        GEODE_DATA / "mods" / ORIGINAL_MOD_ID if GEODE_DATA else None,
        GEODE_DATA / "mods" / CUSTOM_MOD_ID if GEODE_DATA else None,
    ]
    if GD_PATH and GD_PATH.exists():
        dirs_to_try.extend([
            GD_PATH / ORIGINAL_MOD_ID,
            GD_PATH / CUSTOM_MOD_ID,
            GD_PATH,
        ])
    for d in dirs_to_try:
        if d:
            try:
                d.mkdir(parents=True, exist_ok=True)
                target = d / "license"
                target.write_text(license_str)
                locations.append(target)
            except Exception as e:
                print(f"  [WARN] Could not write license to {d}: {e}")
    return locations


def apply_cyanish_theme():
    config_dirs = [
        LOCALAPPDATA / "GeometryDash" / "geode" / "mods" / CUSTOM_MOD_ID / "v9",
        GEODE_DATA / "mods" / CUSTOM_MOD_ID / "v9",
        GD_PATH / "geode" / "unzipped" / CUSTOM_MOD_ID / "v9" if GD_PATH else None,
    ]
    home_config = {
        "V_BOOL": {"HOME/DOT": False, "HOME/LIGHT_MODE": False,
                    "HOME/SEARCH/AUTO_SELECT": True, "HOME/SEARCH/AUTO_UPDATE": True},
        "V_BYTES": {"HOME/SHORTCUT/ALT": [], "HOME/SHORTCUT/ICONIC": []},
        "V_DECIMAL": {"HOME/FLOATER/X": 0.0, "HOME/FLOATER/Y": 0.0, "HOME/SCALE": 0.9},
        "V_INT": {"HOME/ACCENT": CYAN_ACCENT, "HOME/ANIM_SPEED": 250,
                   "HOME/BACKGROUND": CYAN_BACKGROUND, "HOME/HEIGHT": 1080,
                   "HOME/TAB_TEXT": CYAN_TAB_TEXT, "HOME/WIDTH": 1920},
        "V_STRING": {"HOME/LANGUAGE": "en-GB"}
    }
    written = []
    for d in config_dirs:
        if d:
            try:
                d.mkdir(parents=True, exist_ok=True)
                p = d / "home.json"
                p.write_text(json.dumps(home_config, indent=2))
                written.append(p)
            except Exception as e:
                print(f"  [WARN] Could not write theme config to {d}: {e}")
    return written


def fetch_fresh_geode():
    print("Fetching release metadata...")
    try:
        r = urlopen(Request(INSTALL_JSON_URL, headers={"User-Agent": "Mozilla/5.0"}))
        pkg_data = json.load(r)
    except Exception as e:
        err(f"Failed to fetch install.json: {e}")

    cur_package = pkg_data["packages"][0]
    bundles = cur_package["bundles"]
    bundle = None
    for b in bundles:
        if b.get("geode", False):
            bundle = b
            break
    if not bundle:
        bundle = bundles[0]

    version = bundle.get("version", bundle["name"])
    group = bundle["group"]
    filename = bundle["file"]
    url = f"https://absolllute.com/api/mega_hack/v9/files/{group}/{filename}"

    print(f"Downloading {bundle['name']} ({version})...")
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"})) as r:
            return r.read(), version
    except Exception as e:
        err(f"Download failed: {e}")


def patch_geode_package(geode_zip_bytes, output_path: Path):
    custom_logo_data = None
    if CUSTOM_LOGO and CUSTOM_LOGO.exists():
        custom_logo_data = CUSTOM_LOGO.read_bytes()
        print(f"  Custom logo: {len(custom_logo_data):,} bytes")

    with zipfile.ZipFile(io.BytesIO(geode_zip_bytes), 'r') as zin:
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                file_data = zin.read(item.filename)
                out_name = item.filename

                if item.filename == ORIGINAL_DLL:
                    print(f"\nPatching {ORIGINAL_DLL} ({len(file_data):,} bytes)")
                    targets = find_all_targets(file_data)
                    file_data = apply_patches(file_data, targets)
                    if CUSTOM_NAME and len(CUSTOM_NAME) == len("Mega Hack"):
                        file_data = rename_in_dll(file_data, b'Mega Hack', CUSTOM_NAME.encode())
                    out_name = CUSTOM_DLL
                    print(f"  Renamed DLL: {ORIGINAL_DLL} -> {CUSTOM_DLL}")

                elif item.filename == 'mod.json':
                    print("\nCustomizing mod.json")
                    file_data = customize_mod_json(file_data)
                    print(f"  id={CUSTOM_MOD_ID}, name={CUSTOM_NAME}, dev={CUSTOM_DEVELOPER}")

                elif item.filename == 'about.md':
                    print("  Replaced about.md")
                    file_data = CUSTOM_ABOUT.encode('utf-8')

                elif item.filename == 'logo.png' and custom_logo_data:
                    file_data = custom_logo_data
                    print("  Replaced logo.png")

                zout.writestr(out_name, file_data)
    return output_path


def deploy_to_geode(patched_file_path: Path):
    target_dirs = []
    if GD_PATH:
        target_dirs.append(GD_PATH / "geode" / "mods")
    if GEODE_DATA:
        target_dirs.append(GEODE_DATA / "mods")

    deployed = False
    for mods_dir in target_dirs:
        try:
            if not mods_dir.is_dir():
                if mods_dir.parent.exists():
                    mods_dir.mkdir(parents=True, exist_ok=True)
                else:
                    continue

            for old_id in [ORIGINAL_MOD_ID, CUSTOM_MOD_ID]:
                stale = mods_dir.parent / "unzipped" / old_id
                if stale.is_dir():
                    shutil.rmtree(stale)
                    print(f"  Removed stale cache: {old_id}")
                old_geode = mods_dir / f"{old_id}.geode"
                if old_geode.exists():
                    old_geode.unlink()
                    print(f"  Removed old mod: {old_geode.name}")

            dest = mods_dir / GEODE_FILENAME
            shutil.copy(str(patched_file_path), str(dest))
            print(f"  Deployed: {dest}")
            deployed = True
        except Exception as e:
            print(f"  [WARN] Could not deploy to {mods_dir}: {e}")

    return deployed


def main():
    print("=" * 60)
    print(f"  {CUSTOM_NAME} Patcher ({SYSTEM})")
    print(f"  by {CUSTOM_DEVELOPER}")
    print("=" * 60)
    print(f"  Detected Platform:   {SYSTEM}")
    print(f"  Detected GD Path:   {GD_PATH}")
    print(f"  Detected AppData:   {LOCALAPPDATA}")
    print(f"  Detected Geode Data:{GEODE_DATA}\n")

    geode_zip, version = fetch_fresh_geode()
    print(f"  Downloaded {len(geode_zip):,} bytes (version {version})")

    # Process inside a temporary directory that auto-deletes on exit
    with tempfile.TemporaryDirectory(prefix="prepuhack_") as temp_dir:
        temp_geode = Path(temp_dir) / GEODE_FILENAME
        patched_file = patch_geode_package(geode_zip, temp_geode)

        print(f"\n{'='*50}")
        print("  LICENSE")
        print(f"{'='*50}")
        for loc in deploy_license(generate_license()):
            print(f"  {loc}")

        print(f"\n{'='*50}")
        print("  THEME")
        print(f"{'='*50}")
        for loc in apply_cyanish_theme():
            print(f"  {loc}")

        print(f"\n{'='*50}")
        print("  DEPLOY")
        print(f"{'='*50}")
        deploy_to_geode(patched_file)

    # Cleanup any leftover .geode files in working directory if present
    for old_file in Path.cwd().glob("*.geode"):
        try:
            old_file.unlink()
            print(f"  Cleaned up local file: {old_file.name}")
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"  {CUSTOM_NAME} is ready! Launch GD and press Tab!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
