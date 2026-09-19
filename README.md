# PrepuHack

> **Free Mega Hack v9 Patcher for Geometry Dash (Geode)**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![Geode Compatible](https://img.shields.io/badge/geode-v9.x-brightgreen.svg)](https://geode-sdk.org/)

PrepuHack is an automated patcher tool that unlocks Mega Hack v9 for Geometry Dash without requiring a purchased account or license key. It downloads the latest official Mega Hack `.geode` release package, bypasses all authentication and DRM license checks, generates offline license tokens, and deploys it directly into your Geode mod loader.

---

## What This Tool Does

1. **Unlocks Mega Hack v9 for Free**: Bypasses Mega Hack's online account check, hardware ID verification, and license signature checks.
2. **Automated Setup**: Downloads the newest official release package directly from the server — no manual extraction required.
3. **Cross-Platform**: Works natively on Windows, Linux (Steam Deck, Proton, Flatpak, Snap), and macOS.
4. **Zero Dependencies**: Pure Python standard library implementation.

---

## Security & License Bypasses

The patcher modifies the x86_64 DLL machine code inside the `.geode` package to neutralize DRM verification:

| Target Patch | Purpose | Action / Patch Code |
| :--- | :--- | :--- |
| `ID_CHECK` | Bypasses machine GUID / hardware ID verification | Forces `return true` (`B8 01 00 00 00 C3`) |
| `JSON_SIG` | Bypasses RSA license signature verification | Forces `return true` (`B8 01 00 00 00 C3`) |
| `KEY_BYPASS` | Bypasses secret key validation | Forces `return false` (`B8 00 00 00 00`) |
| `BYPASS_VERIFY` | Completely skips main license validation routine | Immediate `ret` (`C3`) |

It also generates local valid license files in all required system AppData and Geode directories so Mega Hack initializes smoothly without contacting authentication servers.

---

## System Path Auto-Detection

PrepuHack automatically locates Steam and Geode installation paths:

### Windows
- Steam Path: `C:\Program Files (x86)\Steam\steamapps\common\Geometry Dash`
- AppData / Geode: `%LOCALAPPDATA%\GeometryDash\geode`

### Linux (Steam / Proton / Steam Deck)
- Steam Path: `~/.steam/steam/steamapps/common/Geometry Dash` (or Flatpak/Snap paths)
- Proton AppData: `~/.steam/steam/steamapps/compatdata/322170/pfx/drive_c/users/steamuser/AppData/Local`
- Native Geode: `$XDG_DATA_HOME/GeometryDash/geode` (`~/.local/share/GeometryDash/geode`)

### macOS
- Steam Path: `~/Library/Application Support/Steam/steamapps/common/Geometry Dash`

---

## Quick Start

### Prerequisites
- **Python 3.8+**
- **Geometry Dash** installed via Steam with the **Geode** mod loader.

### Running the Patcher

```bash
python3 prepuhack.py
```
*(On Windows: `python prepuhack.py`)*

Once finished, launch Geometry Dash and press **TAB** to open Mega Hack!

---

## Repository Structure

```
PrepuHack/
├── prepuhack.py       # Main patcher and deployment script
├── requirements.txt   # Standard library declaration
└── README.md          # Project documentation
```

---

## Disclaimer

This project is created for educational research, reverse engineering, and personal testing purposes. All product names, logos, and brands belong to their respective owners.
