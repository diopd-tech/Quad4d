# Paparazzi GCS strip icons

These SVG icons are vendored from **PprzGCS**
(<https://github.com/paparazzi/PprzGCS>, `resources/pictures/`), the
Paparazzi UAV ground control station, and are licensed under the GPL
like Paparazzi itself (compatible with this project's LICENSE).

Used in the operator window's drones panel to show, per drone, the
state of the position source (mocap), the RC link, the telemetry
downlink and the battery — the same visual language operators already
know from the GCS.

| file            | meaning                        |
|-----------------|--------------------------------|
| `gps_ok/nok`    | position source (mocap here)   |
| `rc_ok/nok`     | RC link                        |
| `link_ok/nok/warning` | telemetry downlink       |
| `battery_ok/warning/nok` | pack voltage (see below)  |

The `battery_*` icons are **not** from PprzGCS: they are drawn for this
project (original work) in the same flat style and colour palette
(green `#00d700`, amber `#e8a000`, red `#d70900`) so they sit next to
the vendored ones. `ok` = full, `warning` = low (plan to land), `nok` =
critical (land now); the voltage thresholds live in `drones_panel.py`
(`battery_state`).
