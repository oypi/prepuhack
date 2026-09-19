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
import argparse
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
ORIGINAL_DLL = f"{ORIGINAL_MOD_ID}.dll"
CUSTOM_LOGO = Path(__file__).parent / "logo.png"

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

DEFAULT_CONFIG = {
    "_comment_shared": "=== SHARED CONFIG (Affects BOTH Geode & Standalone) ===",
    "name": "PrepuHack",
    "developer": "oneypi",
    "logo_path": "logo.png",
    "theme": {
        "name": "Cyanish",
        "accent": "#00CED1",
        "background": "#1A2A2D",
        "tab_text": "#FFFFFF"
    },

    "_comment_geode": "=== GEODE ONLY CONFIG (Affects Geode mod package only) ===",
    "mod_id": "oneypi.prepuhack",
    "description": "long live the prepubros!",
    "about_path": "about.md",
    "changelog_path": "changelog.md"
}


def parse_color(val, default_val=0) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        v = val.strip().lstrip('#')
        if v.lower().startswith('0x'):
            v = v[2:]
        try:
            return int(v, 16)
        except ValueError:
            pass
    return default_val


def load_user_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        try:
            config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        except Exception:
            pass
        return DEFAULT_CONFIG
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        for gkey in ["geode", "geode_only", "geode_options"]:
            if gkey in data and isinstance(data[gkey], dict):
                merged.update(data[gkey])

        if "theme" in data and isinstance(data["theme"], dict):
            merged_theme = dict(DEFAULT_CONFIG["theme"])
            merged_theme.update(data["theme"])
            merged["theme"] = merged_theme
        return merged
    except Exception as e:
        print(f"  [WARN] Could not parse config.json ({e}), using default configuration.")
        return DEFAULT_CONFIG


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


def rename_in_dll(data: bytes, old_name: bytes, new_name: str) -> bytes:
    old_len = len(old_name)
    encoded = new_name.encode('utf-8')
    if len(encoded) > old_len:
        replacement = encoded[:old_len]
    else:
        replacement = encoded.ljust(old_len, b' ')

    count = data.count(old_name)
    if count > 0:
        data = data.replace(old_name, replacement)
        print(f"  Renamed {count}x '{old_name.decode()}' -> '{replacement.decode()}' in binary")
    return data


def customize_mod_json(data, mod_id: str, name: str, developer: str, description: str):
    mod = json.loads(data.decode('utf-8'))
    mod['id'] = mod_id
    mod['name'] = name
    mod['developer'] = developer
    mod['description'] = description
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


def deploy_license(license_str, active_mod_id: str):
    locations = []
    # Official Mega Hack only looks in %LOCALAPPDATA%\absolllute.megahack\license
    license_dir = LOCALAPPDATA / ORIGINAL_MOD_ID
    try:
        license_dir.mkdir(parents=True, exist_ok=True)
        target = license_dir / "license"
        target.write_text(license_str)
        locations.append(target)
    except Exception as e:
        print(f"  [WARN] Could not write license to {license_dir}: {e}")
    return locations


def apply_theme(active_mod_id: str, theme_info: dict):
    # Official Mega Hack stores settings/themes exclusively in %GEODE_DATA%\mods\absolllute.megahack\v9\home.json
    config_dir = GEODE_DATA / "mods" / ORIGINAL_MOD_ID / "v9"

    accent = parse_color(theme_info.get("accent", "#00CED1"), 0x00CED1)
    background = parse_color(theme_info.get("background", "#1A2A2D"), 0x1A2A2D)
    tab_text = parse_color(theme_info.get("tab_text", "#FFFFFF"), 0xFFFFFF)

    written = []
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        p = config_dir / "home.json"
        home_config = {}
        if p.exists():
            try:
                home_config = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                home_config = {}

        if "V_INT" not in home_config or not isinstance(home_config["V_INT"], dict):
            home_config["V_INT"] = {}

        home_config["V_INT"]["HOME/ACCENT"] = accent
        home_config["V_INT"]["HOME/BACKGROUND"] = background
        home_config["V_INT"]["HOME/TAB_TEXT"] = tab_text

        p.write_text(json.dumps(home_config, indent=2), encoding="utf-8")
        written.append(p)
    except Exception as e:
        print(f"  [WARN] Could not write theme config to {config_dir}: {e}")
    return written


def perform_cleanup(active_mod_id: str):
    print(f"\n{'='*50}")
    print("  CLEANUP OLD INSTALLATIONS & CACHES")
    print(f"{'='*50}")

    targets_to_clean = {ORIGINAL_MOD_ID, active_mod_id}

    search_dirs = []
    if GD_PATH and GD_PATH.exists():
        search_dirs.extend([
            GD_PATH / "geode" / "unzipped",
            GD_PATH / "geode" / "mods",
            GD_PATH / "geode" / "config",
            GD_PATH / "geode" / "save",
        ])
    if GEODE_DATA and GEODE_DATA.exists():
        search_dirs.extend([
            GEODE_DATA / "unzipped",
            GEODE_DATA / "mods",
            GEODE_DATA / "config",
            GEODE_DATA / "save",
        ])

    file_targets = {f"{t}.geode" for t in targets_to_clean} | {f"{t}.dll" for t in targets_to_clean}
    for base in search_dirs:
        if not base.exists():
            continue
        for child in list(base.iterdir()):
            if child.is_dir() and child.name in targets_to_clean:
                try:
                    shutil.rmtree(child)
                    print(f"  Purged cache/dir: {child}")
                except Exception as e:
                    print(f"  [WARN] Could not purge {child}: {e}")
            elif child.is_file() and child.name in file_targets:
                try:
                    child.unlink()
                    print(f"  Purged cache/file: {child}")
                except Exception as e:
                    print(f"  [WARN] Could not purge {child}: {e}")

    for loc in [LOCALAPPDATA / ORIGINAL_MOD_ID, LOCALAPPDATA / active_mod_id]:
        if loc and loc.exists():
            try:
                shutil.rmtree(loc)
                print(f"  Purged license dir: {loc}")
            except Exception as e:
                print(f"  [WARN] Could not purge {loc}: {e}")


def fetch_fresh_package(use_geode: bool = True) -> tuple[bytes, str]:
    print("\nFetching latest version metadata...")
    try:
        r = urlopen(Request(INSTALL_JSON_URL, headers={"User-Agent": "Mozilla/5.0"}))
        pkg_data = json.load(r)
    except Exception as e:
        err(f"Failed to fetch install.json: {e}")

    cur_package = pkg_data["packages"][0]
    bundles = cur_package["bundles"]
    bundle = None
    for b in bundles:
        if b.get("geode", False) == use_geode:
            bundle = b
            break
    if not bundle:
        bundle = bundles[0]

    version = bundle.get("version", bundle["name"])
    group = bundle["group"]
    filename = bundle["file"]
    url = f"https://absolllute.com/api/mega_hack/v9/files/{group}/{filename}"

    print(f"Downloading {bundle['name']} ({version}, geode={use_geode})...")
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"})) as r:
            return r.read(), version
    except Exception as e:
        err(f"Download failed: {e}")


def patch_geode_package(geode_zip_bytes, output_path: Path, config: dict, rebrand: bool = True):
    target_mod_id = config.get("mod_id", ORIGINAL_MOD_ID) if rebrand else ORIGINAL_MOD_ID
    target_name = config.get("name", "PrepuHack") if rebrand else "Mega Hack"
    target_developer = config.get("developer", "oneypi") if rebrand else "Absolute"
    target_description = config.get("description", "") if rebrand else "#1 Geometry Dash mod menu"
    target_dll = f"{target_mod_id}.dll" if rebrand else ORIGINAL_DLL
    target_about = ""
    if rebrand:
        about_setting = config.get("about_path", "about.md")
        if about_setting:
            ap = Path(about_setting)
            candidates = [ap] if ap.is_absolute() else [Path(__file__).parent / ap, Path.cwd() / ap]
            for ab_file in candidates:
                if ab_file and ab_file.exists() and ab_file.is_file():
                    try:
                        target_about = ab_file.read_text(encoding="utf-8")
                        print(f"  Custom about loaded from: {ab_file}")
                        break
                    except Exception as e:
                        print(f"  [WARN] Could not read about from {ab_file}: {e}")

    target_changelog = ""
    if rebrand:
        changelog_setting = config.get("changelog_path", "changelog.md")
        if changelog_setting:
            cp = Path(changelog_setting)
            candidates = [cp] if cp.is_absolute() else [Path(__file__).parent / cp, Path.cwd() / cp]
            for cl_file in candidates:
                if cl_file and cl_file.exists() and cl_file.is_file():
                    try:
                        target_changelog = cl_file.read_text(encoding="utf-8")
                        print(f"  Custom changelog loaded from: {cl_file}")
                        break
                    except Exception as e:
                        print(f"  [WARN] Could not read changelog from {cl_file}: {e}")

    custom_logo_data = None
    if rebrand:
        logo_setting = config.get("logo_path")
        candidate_paths = []
        if logo_setting:
            lp = Path(logo_setting)
            if lp.is_absolute():
                candidate_paths.append(lp)
            else:
                candidate_paths.append(Path(__file__).parent / lp)
                candidate_paths.append(Path.cwd() / lp)
        candidate_paths.append(CUSTOM_LOGO)

        for logo_file in candidate_paths:
            if logo_file and logo_file.exists() and logo_file.is_file():
                try:
                    custom_logo_data = logo_file.read_bytes()
                    print(f"  Custom logo loaded from: {logo_file} ({len(custom_logo_data):,} bytes)")
                    break
                except Exception as e:
                    print(f"  [WARN] Could not read logo from {logo_file}: {e}")

    with zipfile.ZipFile(io.BytesIO(geode_zip_bytes), 'r') as zin:
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                file_data = zin.read(item.filename)
                out_name = item.filename

                if item.filename == ORIGINAL_DLL:
                    print(f"\nPatching {ORIGINAL_DLL} ({len(file_data):,} bytes)")
                    targets = find_all_targets(file_data)
                    file_data = apply_patches(file_data, targets)
                    if rebrand and target_name:
                        file_data = rename_in_dll(file_data, b'Mega Hack', target_name)
                    out_name = target_dll
                    print(f"  DLL: {ORIGINAL_DLL} -> {target_dll}")

                elif item.filename.endswith(('.so', '.dylib')) and rebrand and target_name:
                    file_data = rename_in_dll(file_data, b'Mega Hack', target_name)
                    if ORIGINAL_MOD_ID in item.filename:
                        out_name = item.filename.replace(ORIGINAL_MOD_ID, target_mod_id)

                elif item.filename == 'mod.json':
                    print("\nCustomizing mod.json")
                    file_data = customize_mod_json(file_data, target_mod_id, target_name, target_developer, target_description)
                    print(f"  id={target_mod_id}, name={target_name}, dev={target_developer}")

                elif item.filename == 'about.md' and rebrand and target_about:
                    print("  Replaced about.md")
                    file_data = target_about.encode('utf-8')

                elif item.filename == 'changelog.md' and rebrand and target_changelog:
                    print("  Replaced changelog.md")
                    file_data = target_changelog.encode('utf-8')

                elif item.filename == 'logo.png' and rebrand and custom_logo_data:
                    file_data = custom_logo_data
                    print("  Replaced logo.png")

                elif rebrand and ORIGINAL_MOD_ID in item.filename and item.filename != ORIGINAL_DLL and not item.filename.startswith("resources/"):
                    out_name = item.filename.replace(ORIGINAL_MOD_ID, target_mod_id)

                zout.writestr(out_name, file_data)
    return output_path


def is_real_geode_loader(dll_path: Path) -> bool:
    if not dll_path or not dll_path.exists() or not dll_path.is_file():
        return False
    # Geode's loader DLL is small (~50-100KB), whereas Standalone Mega Hack's proxy DLL is ~4MB
    try:
        return dll_path.stat().st_size < 500_000
    except Exception:
        return False


def fetch_and_restore_geode_loader() -> bool:
    if not GD_PATH or not GD_PATH.exists():
        return False

    xinput = GD_PATH / "XInput1_4.dll"
    if xinput.exists() and is_real_geode_loader(xinput):
        return True

    print("Fetching official Geode loader from GitHub...")
    try:
        if xinput.exists():
            try:
                xinput.unlink()
            except Exception:
                pass

        api_url = "https://api.github.com/repos/geode-sdk/geode/releases/latest"
        req = Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        download_url = None
        tag_name = "latest"

        try:
            with urlopen(req) as r:
                rel_data = json.load(r)
                tag_name = rel_data.get("tag_name", "latest")
                for asset in rel_data.get("assets", []):
                    aname = asset.get("name", "").lower()
                    if "win" in aname and aname.endswith(".zip"):
                        download_url = asset.get("browser_download_url")
                        break
        except Exception as e:
            print(f"  [WARN] GitHub API release lookup failed: {e}")

        if not download_url:
            download_url = "https://github.com/geode-sdk/geode/releases/latest/download/geode-v5.10.1-win.zip"

        dl_req = Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(dl_req) as r:
            with zipfile.ZipFile(io.BytesIO(r.read())) as z:
                for fname in ["XInput1_4.dll", "Geode.dll", "GeodeUpdater.exe"]:
                    if fname in z.namelist():
                        (GD_PATH / fname).write_bytes(z.read(fname))
                        print(f"  Restored official Geode file ({tag_name}): {fname}")
        return True
    except Exception as e:
        print(f"  [WARN] Could not auto-download Geode binaries: {e}")
        return False


def deploy_standalone(zip_bytes: bytes, config: dict, rebrand: bool = True):
    if not GD_PATH or not GD_PATH.exists():
        err("Geometry Dash path not found. Use --gd-path to specify your installation directory.")

    target_name = config.get("name", "PrepuHack") if rebrand else "Mega Hack"
    print(f"\nExtracting and patching Standalone package directly into {GD_PATH}")

    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
        for item in zf.infolist():
            filename = item.filename
            if filename.endswith("/"):
                (GD_PATH / filename.rstrip("/")).mkdir(parents=True, exist_ok=True)
            else:
                data = zf.read(filename)
                if filename == "hackpro.dll":
                    print(f"  Patching {filename} ({len(data):,} bytes)")
                    targets = find_all_targets(data)
                    data = apply_patches(data, targets)
                    if rebrand and target_name:
                        data = rename_in_dll(data, b'Mega Hack', target_name)
                elif filename.endswith(('.dll', '.so', '.dylib')) and rebrand and target_name:
                    data = rename_in_dll(data, b'Mega Hack', target_name)

                target_file = GD_PATH / filename
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_bytes(data)
                print(f"  Extracted: {target_file}")


def perform_uninstall(active_mod_id: str, mode: str = "all"):
    print("=" * 60)
    print("  UNINSTALLING MEGA HACK / PREPUHACK")
    print("=" * 60)

    removed = 0
    targets = {ORIGINAL_MOD_ID, active_mod_id}

    # 1. Geode Mod Files, Unzipped Caches, Config & Save Folders
    if mode in ("all", "geode"):
        geode_targets = []
        if GD_PATH:
            geode_targets.extend([
                GD_PATH / "geode" / "mods",
                GD_PATH / "geode" / "unzipped",
                GD_PATH / "geode" / "config",
                GD_PATH / "geode" / "save",
            ])
        if GEODE_DATA:
            geode_targets.extend([
                GEODE_DATA / "mods",
                GEODE_DATA / "unzipped",
                GEODE_DATA / "config",
                GEODE_DATA / "save",
            ])

        for gdir in geode_targets:
            if not gdir or not gdir.is_dir():
                continue
            try:
                for item in list(gdir.iterdir()):
                    name_lower = item.name.lower()
                    if any(t in name_lower for t in targets) or "prepuhack" in name_lower or "megahack" in name_lower:
                        try:
                            if item.is_dir():
                                shutil.rmtree(item)
                                print(f"  Removed dir:  {item}")
                            else:
                                item.unlink()
                                print(f"  Removed file: {item}")
                            removed += 1
                        except Exception as e:
                            print(f"  [WARN] Failed removing {item}: {e}")
            except Exception as e:
                print(f"  [WARN] Could not scan {gdir}: {e}")

    # 2. Standalone DLLs and Resources in GD_PATH
    if mode in ("all", "standalone") and GD_PATH and GD_PATH.exists():
        standalone_files = [
            GD_PATH / "hackpro.dll",
            GD_PATH / "license",
        ]
        for sf in standalone_files:
            if sf.exists() and sf.is_file():
                try:
                    sf.unlink()
                    print(f"  Removed file: {sf}")
                    removed += 1
                except Exception as e:
                    print(f"  [WARN] Failed removing {sf}: {e}")

        fetch_and_restore_geode_loader()

        res_dir = GD_PATH / "Resources"
        if res_dir.is_dir():
            try:
                for ritem in list(res_dir.iterdir()):
                    rname_lower = ritem.name.lower()
                    if any(t in rname_lower for t in targets) or "prepuhack" in rname_lower or "megahack" in rname_lower:
                        try:
                            if ritem.is_dir():
                                shutil.rmtree(ritem)
                                print(f"  Removed dir:  {ritem}")
                            else:
                                ritem.unlink()
                                print(f"  Removed file: {ritem}")
                            removed += 1
                        except Exception as e:
                            print(f"  [WARN] Failed removing {ritem}: {e}")
            except Exception as e:
                print(f"  [WARN] Could not scan {res_dir}: {e}")

    # 3. AppData & GD Root License Folders
    gd_appdata_dirs = []
    if LOCALAPPDATA and LOCALAPPDATA.exists():
        gd_appdata_dirs.extend([
            LOCALAPPDATA / ORIGINAL_MOD_ID,
            LOCALAPPDATA / active_mod_id,
        ])
    if GD_PATH and GD_PATH.exists():
        gd_appdata_dirs.extend([
            GD_PATH / ORIGINAL_MOD_ID,
            GD_PATH / active_mod_id,
        ])

    for ad in gd_appdata_dirs:
        if ad and ad.exists():
            try:
                if ad.is_dir():
                    shutil.rmtree(ad)
                    print(f"  Removed dir:  {ad}")
                else:
                    ad.unlink()
                    print(f"  Removed file: {ad}")
                removed += 1
            except Exception as e:
                print(f"  [WARN] Failed removing {ad}: {e}")

    print(f"\nUninstall complete. ({removed} item(s) removed)\n")


def deploy_to_geode(patched_file_path: Path, active_filename: str):
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

            dest = mods_dir / active_filename
            shutil.copy(str(patched_file_path), str(dest))
            print(f"  Deployed: {dest}")
            deployed = True
        except Exception as e:
            print(f"  [WARN] Could not deploy to {mods_dir}: {e}")

    return deployed


def main():
    parser = argparse.ArgumentParser(description="Mega Hack / PrepuHack Patcher & Installer")
    parser.add_argument("--standalone", action="store_true", help="Force deployment of standalone binaries directly to Geometry Dash instead of Geode mod package")
    parser.add_argument("--official", "--no-rebrand", action="store_true", help="Keep official Mega Hack branding and native theme from the official package")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall/remove Mega Hack and PrepuHack files, DLLs, and caches")
    parser.add_argument("--no-theme", action="store_true", help="Skip applying theme configuration")
    parser.add_argument("--no-cleanup", action="store_true", help="Skip cleaning up older cached installations")
    parser.add_argument("--gd-path", type=str, help="Specify path to Geometry Dash installation directory")
    parser.add_argument("--appdata-path", type=str, help="Specify path to local AppData directory / Wine prefix")
    args = parser.parse_args()

    global GD_PATH, LOCALAPPDATA, GEODE_DATA
    if args.gd_path:
        GD_PATH = Path(args.gd_path).expanduser().resolve()
    if args.appdata_path:
        LOCALAPPDATA = Path(args.appdata_path).expanduser().resolve()
        if IS_WINDOWS:
            GEODE_DATA = LOCALAPPDATA / "GeometryDash" / "geode"

    rebrand = not args.official
    use_geode = not args.standalone
    if args.official:
        user_config = {
            "mod_id": ORIGINAL_MOD_ID,
            "name": "Mega Hack",
            "developer": "Absolute",
            "description": "#1 Geometry Dash mod menu",
            "about": "",
        }
    else:
        user_config = load_user_config()

    active_mod_id = user_config.get("mod_id", ORIGINAL_MOD_ID)
    active_name = user_config.get("name", "Mega Hack")
    active_developer = user_config.get("developer", "Absolute")
    active_geode_filename = f"{active_mod_id}.geode"

    theme_info = user_config.get("theme", {})
    theme_name = theme_info.get("name", "Custom") if rebrand else "Official (Native from .geode)"

    print("=" * 60)
    print(f"  {active_name} Patcher ({SYSTEM})")
    print(f"  by {active_developer}")
    print("=" * 60)
    print(f"  Branding Mode:      {'Custom (' + active_name + ')' if rebrand else 'Mega Hack (Official)'}")
    print(f"  Target Type:        {'Geode Package' if use_geode else 'Standalone Binaries'}")
    print(f"  Theme Mode:         {theme_name}")
    print(f"  Detected Platform:  {SYSTEM}")
    print(f"  Detected GD Path:  {GD_PATH}")
    print(f"  Detected AppData:  {LOCALAPPDATA}")
    print(f"  Detected Geode Data:{GEODE_DATA}\n")

    if args.uninstall:
        mode = "standalone" if args.standalone else "geode"
        perform_uninstall(active_mod_id, mode=mode)
        return

    if not args.no_cleanup:
        perform_cleanup(active_mod_id)

    pkg_zip, version = fetch_fresh_package(use_geode=use_geode)
    print(f"  Downloaded {len(pkg_zip):,} bytes (version {version})")

    if use_geode:
        if GD_PATH and GD_PATH.exists():
            standalone_dll = GD_PATH / "hackpro.dll"
            if standalone_dll.exists():
                try:
                    standalone_dll.unlink()
                    print("  Removed standalone hackpro.dll to restore Geode compatibility")
                except Exception:
                    pass
            fetch_and_restore_geode_loader()

        # Process inside a temporary directory that auto-deletes on exit
        with tempfile.TemporaryDirectory(prefix="prepuhack_") as temp_dir:
            temp_geode = Path(temp_dir) / active_geode_filename
            patched_file = patch_geode_package(pkg_zip, temp_geode, config=user_config, rebrand=rebrand)

            print(f"\n{'='*50}")
            print("  LICENSE")
            print(f"{'='*50}")
            for loc in deploy_license(generate_license(), active_mod_id):
                print(f"  {loc}")

            if rebrand and not args.no_theme:
                print(f"\n{'='*50}")
                print(f"  THEME ({theme_name})")
                print(f"{'='*50}")
                for loc in apply_theme(active_mod_id, theme_info=theme_info):
                    print(f"  {loc}")
            elif not rebrand:
                print(f"\n{'='*50}")
                print("  THEME (Official - Native from .geode)")
                print(f"{'='*50}")
                print("  Using official native theme defaults directly from .geode package.")

            print(f"\n{'='*50}")
            print("  DEPLOY")
            print(f"{'='*50}")
            deploy_to_geode(patched_file, active_geode_filename)
    else:
        print(f"\n{'='*50}")
        print("  LICENSE")
        print(f"{'='*50}")
        for loc in deploy_license(generate_license(), active_mod_id):
            print(f"  {loc}")

        if rebrand and not args.no_theme:
            print(f"\n{'='*50}")
            print(f"  THEME ({theme_name})")
            print(f"{'='*50}")
            for loc in apply_theme(active_mod_id, theme_info=theme_info):
                print(f"  {loc}")

        print(f"\n{'='*50}")
        print("  DEPLOY (STANDALONE)")
        print(f"{'='*50}")
        deploy_standalone(pkg_zip, config=user_config, rebrand=rebrand)

    # Cleanup any leftover .geode files in working directory if present
    for old_file in Path.cwd().glob("*.geode"):
        try:
            old_file.unlink()
            print(f"  Cleaned up local file: {old_file.name}")
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"  {active_name} is ready! Launch GD and press Tab!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
