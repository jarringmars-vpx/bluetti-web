# BLUETTI Web v0.2.11

Local phone-friendly web interface for BLUETTI devices.

This version replaces the mock backend with the real Community-library
persistent encrypted BLE session for the EL30V2.

## Architecture

```text
iPhone Safari / Home Screen
        |
        | LAN HTTP + WebSocket
        v
Windows/Linux PC running BLUETTI Web
        |
        | persistent encrypted BLE
        v
BLUETTI EL30V2
```

The browser does **not** access Bluetooth directly.

## Current live telemetry

- R102 SOC
- R140 DC output power
- R142 AC output power
- R144 PV/DC input power
- R146 AC/grid input power
- R154 PV Generation (raw / 10 kWh)
- R1153 temperature (raw / 10 C)
- R133 + R137 fault indicator candidates
- R2011 AC output state/control
- R2012 DC output state/control
- R2020 Charging Mode state/control
- R6003 battery voltage (raw / 100 V)
- R6004 battery current magnitude (raw / 10 A)
- R6009 battery flow state
- R6350 fan/cooling state

Battery current is a magnitude. R6009 supplies the charging/discharging
direction.

## Important before running

Exit the desktop BLUETTI GUI first. Do not have two applications competing
for the EL30V2 BLE connection.

The modified Community library checkout must be installed in the Python
environment used to run this server.

Windows development checkout:

```bat
cd /d C:\Users\clay\bluetti-bt-lib
C:\Python310\python.exe -m pip install -e .
```

## Install web dependencies

Windows:

```bat
cd /d C:\Users\clay\bluetti-web
install_dependencies.bat
```

Or cross-platform:

```text
python -m pip install -r requirements.txt
```

## Run on Windows

```bat
cd /d C:\Users\clay\bluetti-web
run_web_app.bat
```

Then open on the PC:

```text
http://127.0.0.1:8080
```

On an iPhone on the same LAN:

```text
http://<PC-LAN-IP>:8080
```

The current Windows PC LAN address during development has been
192.168.40.217, but DHCP can change it.

## BLE device selection

By default BLUETTI Web scans for a BLE device whose advertised name matches
EL30V2.

Optionally set `BLUETTI_BLE_ADDRESS` in the environment before starting the
server to target a specific local BLE address. Do not commit private device
identifiers to the repository.

## Controls

AC, DC, and Charging Mode use the Community library's persistent encrypted
`DeviceSession`.

The UI updates optimistically. While a write is pending, stale polling is
suppressed. After readback verification, a short hold prevents a stale poll
from making the control flicker.

## Transient BLE failures

A single timeout or malformed/foreign response does not automatically tear
down the BLE session. The service keeps the same authenticated session while
it remains connected and ready, matching the behavior validated in the
Community-library project.

## Security

This is intended for a private LAN. Do not expose TCP port 8080 directly to
the Internet.

No Wi-Fi password registers are read by this application.

## v0.2.1 visual update

- Added the cleaned EL30V2 device image to the responsive web dashboard.
- The active Charging Mode button now uses the same green active-state treatment as AC/DC.
- No BLE backend, polling, or control behavior changed from v0.2.0.

## v0.2.2 UI update

- Added an in-app Refresh button for Home Screen / standalone iPhone use.
- Reordered Charging Mode buttons to Silent, Standard, Turbo.
- Added live AC/DC state overlays on the EL30V2 image.
- The AC/DC buttons on the device image are now clickable/tappable and invoke
  the same real controls as the dashboard AC/DC buttons.
- The image controls reflect the normalized AC/DC state and use the same
  optimistic/pending backend behavior as the existing controls.
- No BLE polling cadence or protocol behavior changed from v0.2.1.

## v0.2.3 image-control alignment

- Recalibrated the DC and AC interactive image overlays independently from
  the desktop/iPhone screenshot.
- DC overlay moved slightly left.
- AC overlay moved farther left.
- No BLE, polling, write, readback, or other UI behavior changed.

## v0.2.4 image-control calibration

User-validated final EL30V2 image-control overlay geometry:

- DC: left 36.25%, top 45.25%, width 5.45%, height 5.85%
- AC: left 55%, top 45.25%, width 5.45%, height 5.85%

No BLE/backend behavior changed.

## v0.2.5 EL30V2 LCD telemetry overlays

- Added live Input Watts, SOC, and Output Watts to the EL30V2 image display.
- Input Watts = AC input + DC/PV input.
- Output Watts = AC output + DC output.
- SOC is displayed in the center of the image LCD.
- Overlays use transparent backgrounds and responsive positioning so they scale
  with the device image on desktop and iPhone.
- Preserved the user-validated AC/DC image-control geometry from v0.2.4.
- No BLE/backend behavior changed.

## v0.2.6 device-relative LCD font sizing

- `.device-visual` is now an inline-size CSS container.
- EL30V2 LCD overlay font sizes now use container query width (`cqw`) units,
  so they scale with the rendered device image rather than the browser viewport.
- Input Watts: 3cqw
- SOC: 3.5cqw
- Output Watts: 3cqw
- Existing LCD positions are unchanged from v0.2.5.
- User-validated AC/DC image-control geometry remains unchanged.
- No BLE/backend behavior changed.

## v0.2.7 user-validated LCD overlay calibration

- Input: left 41.8%, top 37.4%, width 7.5%, font-size 2.3cqw
- SOC: left 48.5%, top 37.3%, width 10%, font-size 2.7cqw
- Output: left 55.4%, top 37.4%, width 7.5%, font-size 2.3cqw
- No BLE/backend behavior changed.

## v0.2.8 display and settings update

- EL30V2 image SOC percent sign is now independently styled at 55% of the SOC digit size and raised slightly to better match the physical display.
- Added a Settings button and modal settings panel.
- Added Temperature Display preference: °F, °C, or Both.
- Temperature preference is stored in browser localStorage, so each browser/device can remember its own choice.
- Existing user-validated LCD overlay positions/sizes remain unchanged:
  - Input: 41.8% / 37.4%, 2.3cqw
  - SOC: 48.5% / 37.3%, 2.7cqw
  - Output: 55.4% / 37.4%, 2.3cqw
- Existing user-validated AC/DC image-control positions remain unchanged.
- No BLE/backend behavior changed.

## v0.2.11 controlled rollback diagnostic build

This build intentionally returns to the known-good v0.2.8 application/UI baseline.

Included:
- v0.2.8 smaller SOC percent sign
- v0.2.8 Settings panel
- v0.2.8 Temperature Display setting: °F / °C / Both
- all v0.2.8 calibrated EL30V2 image overlay values
- static asset cache-busting using `?v=0.2.11`
- embedded favicon to remove `/favicon.ico` 404 noise
- lightweight console lifecycle logging for the Community BLE service

Intentionally NOT included:
- v0.2.9 Time Remaining display
- v0.2.9 Instantaneous/Averaged runtime setting
- v0.2.9 battery-power averaging JavaScript

BLE polling intervals, DeviceSession configuration, control behavior, register reads,
and reconnect behavior are unchanged from v0.2.8.

## v0.2.12 restore Time Remaining enhancement

Built from the validated, working v0.2.11 rollback baseline after the Windows
Bluetooth driver-state problem was resolved independently of the web app.

Restored from v0.2.9:
- Time Remaining display below State of Charge
- Discharging estimate for time to empty
- Charging estimate for time to full
- Settings choice between Instantaneous and Averaged calculation
- 30-second rolling battery-power average for the Averaged mode
- Per-browser persistence of the runtime calculation preference using localStorage
- EL30V2 nominal battery capacity of 288 Wh for runtime estimation

Preserved from v0.2.11:
- embedded favicon
- static asset cache-busting, updated to `?v=0.2.12`
- Community BLE lifecycle/diagnostic console logging
- v0.2.11 shutdown/cancellation handling
- all v0.2.8 calibrated EL30V2 image overlay values and controls

No BLE polling interval, DeviceSession configuration, register-read set, control
write behavior, reconnect behavior, or protocol handling was changed for v0.2.12.
