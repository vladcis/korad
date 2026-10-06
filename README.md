# KORAD KA3005PS / KA3005P control software – USB remote control app for Linux, Windows and macOS

Open-source **KORAD KA3005PS** and **KORAD KA3005P** control software: remote control, live charting, data logging,
programmable sequences and Python scripting (e.g. battery charging) for the KORAD 30 V / 5 A programmable
DC lab power supply over USB. Works with the KA3005P / KA3005PS clones too: **Tenma 72-2535,
RND Lab RND 320-KA3005P, Velleman LABPS3005D** and other rebrands that use the same serial protocol.

A free alternative to the original KORAD PC software. It runs on **Linux (Debian, Ubuntu, Raspberry Pi), Windows 10/11
and macOS**, as a native desktop app or in a web browser (including from a tablet on your LAN).

![KORAD KA3005PS control panel](docs/panel.png)

Charging a Li-ion cell with the `10_charge_liion.py` script: CV phase at 4.20 V, the current falls from 1.25 A, and at
0.125 A (C/20) the script switches the output off.

![KORAD KA3005P Li-ion charging – CV phase](docs/charging.png)

## Features

- **Front panel** like the real KA3005PS: 7-segment V / A / W display and CV, CC, OCP, OVP, ON and LOCK indicators.
  While the output is off it shows the set values; while it is on it shows the measured values.
- **Live trend** of U / I / P built into the display. One click opens it in a separate window (a second monitor works well).
- Set voltage and current by typing, with a slider or with step buttons. Output ON/OFF, OCP, OVP, BEEP, A/mA,
  memories M1–M5 (recall / save) and 6 V/I presets.
- **Program**: a programmable step test like in the original software. A table of U / I / time steps, start and end
  step, and a number of cycles (0 = infinite).
- **Scripts**: Python scripts with a `psu` object. You can save, edit, run and stop them, with output in real time.
  Includes ready-made **battery chargers** for Li-ion, LiFePO4, lead-acid and NiMH.
- **Logs**: CSV logging of U / I / P with a configurable interval, shown as a chart and a table, and downloadable.
- **Console**: send raw commands to the supply (`VSET1:05.00`, `STATUS?`…), with command and event history.
- OCP / OVP protection: switch it on and set the trip thresholds (KA3005PS).
- While a script or program runs, the panel is locked (only Stop works), so a manual change cannot spoil a measurement.
- Automatic reconnect after a USB drop-out, with port and baud rate selection.

## 1. Download (no Python needed)

Ready-made builds are in **[Releases](https://github.com/vladcis/korad/releases/latest)**.

### Native desktop app (own window) – recommended

| System | File | How to run |
|---|---|---|
| **Windows 10/11** (64-bit) | `korad-windows-x64.exe` | Double-click. On first start SmartScreen shows *More info → Run anyway* (the app is not signed). |
| **macOS** (Apple Silicon M1–M4) | `korad-macos-arm64.zip` | Unzip and move `korad.app` to Applications. The first time, **right-click → Open** (Gatekeeper), or run `xattr -d com.apple.quarantine /Applications/korad.app` in Terminal. Intel Mac: run from source (section 2). |
| **Debian 12+, Ubuntu 22.04+, Raspberry Pi OS** (any CPU) | `korad_<version>_all.deb` | `sudo apt install ./korad_*_all.deb`, then start **KORAD KA3005P** from the app menu or run `korad`. Uses the system WebKitGTK (small download), and installs a udev rule: the logged-in desktop user gets access to the supply without the `dialout` group, and ModemManager leaves it alone. |
| **Linux, any distro** (x86-64, glibc ≥ 2.35) | `korad-linux-x86_64.AppImage` | `chmod +x korad-linux-x86_64.AppImage && ./korad-linux-x86_64.AppImage`. Self-contained (Qt WebEngine bundled, ~210 MB). |

### Web app (UI in your browser)

| System | File | How to run |
|---|---|---|
| **Linux** (x86-64, glibc ≥ 2.35) | `korad-linux-x86_64-web` | `chmod +x korad-linux-x86_64-web && ./korad-linux-x86_64-web`. Starts the server and opens your default browser. A single small file with no dependencies, also good for headless use (`--server --port 8585`). |
| **Any OS** | source code | `python3 app.py` → http://127.0.0.1:8585 (section 2). Use `--host 0.0.0.0` to reach the UI from another device on your network. |

After start the app finds the power supply on USB by itself. If it does not, pick the port in the top bar and click **Connect**.

**Where your scripts and logs are** (created on first start; the path is also printed in the app console):

| System | folder |
|---|---|
| Windows | `%APPDATA%\Korad\` (e.g. `C:\Users\name\AppData\Roaming\Korad\`) |
| macOS | `~/Library/Application Support/Korad/` |
| Linux | `~/.local/share/korad/` |

Set another folder with the `KORAD_HOME` environment variable.
Example scripts you have not edited are updated (or removed, if renamed) automatically with each new version;
edited examples and your own scripts are never touched.

### What each system needs

**Windows 11**: nothing. The supply shows up as `COMx` after you plug it in (the `usbser` driver ships with Windows).
The native window uses WebView2, which is built into Windows 11 (on Windows 10 an Edge update installs it if needed).

**macOS**: nothing. The supply is `/dev/cu.usbmodemXXXX`. If macOS asks "Allow accessory to connect" when you plug it in, allow it.

**Linux** (AppImage, web binary or source; the `.deb` does this for you): you need access to the serial port, and
ModemManager must leave the supply alone (otherwise it probes it as a modem and breaks the communication):
```sh
sudo usermod -aG dialout $USER          # then log out and back in
sudo curl -o /etc/udev/rules.d/99-korad.rules https://raw.githubusercontent.com/vladcis/korad/main/99-korad.rules
sudo udevadm control --reload && sudo udevadm trigger
```

## 2. Run from source (all platforms, including Intel Mac and Raspberry Pi)

You need Python 3.10+ and git (or download the ZIP via *Code → Download ZIP*).

**Linux / macOS**
```sh
git clone https://github.com/vladcis/korad.git && cd korad
python3 -m pip install -r requirements.txt       # flask, pyserial
python3 app.py                                   # web server -> http://127.0.0.1:8585
# or the desktop window:
python3 -m pip install pywebview                 # Linux also: sudo apt install python3-gi gir1.2-webkit2-4.1
python3 desktop.py
```
On macOS you can double-click `run.command` (opens the browser). Python on macOS: `brew install python` or the installer from python.org.

**Windows**
1. Install Python from [python.org](https://www.python.org/downloads/windows/) and tick **Add python.exe to PATH**.
2. Download the repository (ZIP or `git clone`), then open PowerShell / cmd in the folder:
```bat
pip install -r requirements.txt
pip install pywebview        :: optional, native window
python desktop.py            :: native window, or:  python app.py  -> http://127.0.0.1:8585
```
Or double-click `run.bat` (opens the browser).

**Optional parameters**: `python app.py --port 9000 --device COM5 --host 0.0.0.0` (`--host 0.0.0.0` makes the UI reachable on your LAN, e.g. from a tablet).
The environment variable `KORAD_HIDE_SN=1` hides the supply's serial number in the UI (for screen sharing and screenshots).

## 3. Build it yourself

Build on each OS separately (PyInstaller cannot cross-compile):
```sh
pip install -r requirements.txt pyinstaller pywebview
python build.py        # -> dist/korad (Linux), dist/korad.exe (Windows), dist/korad.app (macOS)
```
Linux packages:
```sh
sh packaging/linux/build_deb.sh 1.1.0             # -> dist/korad_1.1.0_all.deb   (needs python3-pip, dpkg-deb)
pip install -r requirements.txt pyinstaller pywebview qtpy PyQt6 PyQt6-WebEngine
sh packaging/linux/build_appimage.sh              # -> dist/korad-linux-x86_64.AppImage
```
GitHub Actions (`.github/workflows/build.yml`) builds everything automatically when you push a `v*` tag and attaches the files to the release.

## Scripting

Scripts live in the `scripts/` folder (see the paths above) and run in a server thread. Available: `psu`, `print`/`log`, `time`, `math`.
Scripts can import your own `lib_*.py` libraries from the same folder (they are reloaded on every run).

| call | meaning |
|---|---|
| `psu.set_v(12.0)`, `psu.set_i(0.5)`, `psu.set(volts=, amps=)` | set U [V], I [A] |
| `psu.on()`, `psu.off()`, `psu.output(bool)` | output |
| `psu.vout`, `psu.iout`, `psu.power`, `psu.vset`, `psu.iset` | measured / set values |
| `psu.status()` | `{"cv","ocp","ovp","output","beep"}` |
| `psu.wait(s)` (= `time.sleep`) | pause; the Stop button interrupts it |
| `psu.ramp_v(start, end, duration, step)`, `psu.ramp_i(...)` | linear ramp |
| `psu.ocp(b)`, `psu.ovp(b)`, `psu.beep(b)`, `psu.save(n)`, `psu.recall(n)` | functions, memories 1–5 |
| `psu.set_ocp(A)`, `psu.set_ovp(V)`, `psu.ocp_limit`, `psu.ovp_limit` | protection thresholds (KA3005PS) |
| `psu.log_start("name", interval)`, `psu.log_stop()` | CSV logging |
| `psu.raw("VSET1:05.00")`, `psu.raw("STATUS?", 1)` | any command |
| `psu.safe_off = False` | do not switch the output off on error / stop (by default it is switched off) |

### Battery charging

Scripts `10_` to `17_` use the `scripts/lib_batt.py` library (`cccv_charge`, `nimh_charge`, `float_stage`).
The parameters (cell count, capacity, C-rate, end voltage) are at the top of each script.

| script | chemistry | method |
|---|---|---|
| `10_charge_liion.py` | Li-ion / LiPo 1S–7S | precharge → CC → CV, ends at C/20 |
| `11_charge_lifepo4.py` | LiFePO4 (4S = 12 V) | CC → CV 3.60 V/cell, ends at C/20 |
| `12_charge_lead_acid.py` | Lead-acid 12 V (AGM, gel, flooded) | bulk → absorption 14.4 V → float 13.6 V |
| `13_charge_nimh.py` | NiMH / NiCd | CC with −ΔV termination, or slow 0.1 C on a timer |
| `14_charge_custom.py` | anything | CC/CV with your own values |
| `15_battery_check.py` | – | only measures the battery voltage |
| `16_charge_panasonic_cgr18650cg.py` | Panasonic CGR18650CG (18650) | datasheet values: 1.5 A (0.7 It), 4.20 V, ends at 110 mA |
| `17_charge_sanyo_ur18650a.py` | Sanyo UR18650A (18650) | datasheet values: 1.51 A, 4.20 V, precharge below 3.0 V |

Before it starts, the library checks that a battery is connected and that its voltage is in a sane range. It counts
the charged Ah, reports the CC → CV transition, and switches the output off on a time limit, capacity overrun, error or the Stop button.
**The supply cannot measure temperature: charge under supervision, and check the polarity and cell count.**

## KORAD KA3005P serial protocol (for the console)

`*IDN?`, `STATUS?` (byte: bit0 CV/CC, bit4 beep, bit5 OCP, bit6 output, bit7 OVP), `VSET1:xx.xx`, `VSET1?`,
`ISET1:x.xxx`, `ISET1?`, `VOUT1?`, `IOUT1?`, `OUT0/1`, `OCP0/1`, `OVP0/1`, `BEEP0/1`, `SAV1-5`, `RCL1-5`.
The KA3005PS also has protection thresholds: `OCP1:x.xxx`, `OCP1?`, `OVP1:xx.xx`, `OVP1?` (undocumented, verified on firmware V1.5).
9600 baud, no line terminator. The supply needs ~50–100 ms between commands; the driver handles that itself.
USB ID `0416:5011` (Winbond / Nuvoton virtual COM port).
Note: only one program may talk to the supply at a time, otherwise the replies get mixed up and the supply resets its USB.

## Project structure
```
app.py        Flask server, REST API, SSE stream, supply polling
korad.py      serial driver (port auto-detection, Linux/macOS/Windows)
scripting.py  script runner (psu object)
sequencer.py  programmable test -> script
datalog.py    CSV logging + events
desktop.py    desktop window (pywebview) / launcher
build.py      PyInstaller build
packaging/    Linux .deb and AppImage build scripts
static/       HTML / CSS / JS
scripts/      example scripts + lib_batt.py      data/  presets and sequences      logs/  CSV logs
```

*Keywords: KORAD KA3005PS software, KORAD KA3005P software, KA3005P Python, KA3005PS USB driver Linux, Tenma 72-2535 software,
programmable DC power supply remote control, lab bench power supply GUI, battery charger with lab power supply.*

## License

[MIT](LICENSE) © 2026 vladcis
