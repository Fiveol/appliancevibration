# ApplianceVibration

Home Assistant custom component that adds an ApplianceVibration sidebar panel
with a tabbed view, monitors your appliances' vibration, detects washing
cycles and learns to recognize their programs.

## Features

- Added entirely through the UI (config flow) - no YAML configuration needed
- Sidebar panel with a tabbed view (Overview / Devices / Settings)
- Create appliance devices and assign a vibration binary sensor plus optional
  X, Y, Z movement sensors
- Automatic cycle detection: a cycle starts after `start_delay` seconds of
  vibration and ends after `end_delay` seconds of silence
- Stage detection: while a cycle runs, the current stage (Wash, Rinse, Spin,
  Drain, Soak, ...) is detected live from the vibration pattern, matched
  against common stage sequences (e.g. wash -> drain -> rinse -> drain -> spin)
  and how long each stage lasts is recorded per cycle
- Time remaining: an estimated countdown is shown while a cycle runs, based on
  the learned program duration, the matched stage pattern, or the typical
  stage lengths
- Program learning: label completed cycles and the integration classifies
  future cycles by duration and vibration profile
- Every device is exposed as a proper Home Assistant device with entities:
  - `Cycle` (binary sensor, running device class)
  - `Stage` (enum sensor with the current stage)
  - `Stage duration` (sensor, how long the current stage has lasted)
  - `Time remaining` (sensor, estimated time left in the cycle)
  - `Program` (enum sensor with the detected program)
  - `Vibration level` (sensor, current magnitude in g)
  - `Cycle duration` (sensor)
  - `Cycle count` (diagnostic sensor)

## Installation

1. Copy the `custom_components/appliancevibration` directory into your Home
   Assistant `custom_components` directory, or install via HACS.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and pick
   **ApplianceVibration**.
4. Give the panel a name and an icon, then submit.

## Getting started

1. Open the ApplianceVibration panel from the sidebar and go to **Devices**.
2. Click **Add device**, name your appliance (e.g. "Washing Machine") and
   assign its vibration sensor. If your sensor reports X/Y/Z movement values,
   assign them too - the more data, the better the classification.
3. Run a normal cycle (e.g. your "Cotton" program). When it finishes, the
   integration records it and the panel asks you to label it.
4. Label each distinct program a couple of times. After that, new cycles are
   classified automatically and the detected program is shown on the device
   card, in the enum sensor and on the Overview tab.

While a cycle runs, the device card shows the current stage (e.g. **Spin**)
with a progress bar and an estimated **time remaining**. Click the stage
count on any cycle row to see its stage-by-stage breakdown (which stages ran
and how long each one lasted). Stage lengths also feed the time-remaining
estimate: once you have labeled cycles, the countdown uses the learned
program and stage durations instead of the built-in defaults.

Per-device settings (edit dialog > Advanced):

- **Activity threshold (g)** - magnitude that counts as vibration
- **Cycle start delay (s)** - sustained vibration needed to start a cycle
- **Cycle end delay (s)** - silence needed to consider a cycle finished
- **Min. confidence** - how certain the classifier must be before labeling a
  cycle automatically

## Structure

- `config_flow.py` - config flow (add + reconfigure the integration)
- `__init__.py` - serves the panel bundle and registers the sidebar panel
- `manager.py` - device lifecycle, device/entity registry, persistence
- `monitor.py` - per-device cycle state machine, stage detection, timers
- `stages.py` - common stage definitions, level bands and stage templates
- `classification.py` - cycle features and weighted program matching
- `entities.py` - the entities exposed per device
- `websocket.py` - the `appliancevibration/*` websocket commands used by the panel
- `frontend/panel.js` - self-contained frontend module implementing the
  tabbed view (no build step or external dependencies)

## Development

See the scripts in `scripts/` and the workflows in `.github/workflows/`.

```bash
python3 -m pip install --requirement requirements_common.txt
python3 -m pip install --requirement requirements_dev.txt
```
