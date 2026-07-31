# ApplianceVibration

Home Assistant custom component that adds an ApplianceVibration sidebar panel
with a tabbed view.

## Features

- Added entirely through the UI (config flow) - no YAML configuration needed
- Creates a sidebar panel with a tabbed view (Overview / Devices / Settings)
- Panel title and sidebar icon are configurable and can be changed later via
  the reconfigure flow (Settings > Devices & services > ApplianceVibration)

## Installation

1. Copy the `custom_components/appliancevibration` directory into your Home
   Assistant `custom_components` directory, or install via HACS.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and pick
   **ApplianceVibration**.
4. Give the panel a name and an icon, then submit.

The panel appears in the sidebar immediately. Remove the integration again
under **Settings > Devices & services** to remove the sidebar panel.

## Structure

- `config_flow.py` - config flow (add + reconfigure the integration)
- `__init__.py` - serves the panel bundle and registers the sidebar panel
- `frontend/panel.js` - self-contained frontend module implementing the
  tabbed view (no build step or external dependencies)

## Development

See the scripts in `scripts/` and the workflows in `.github/workflows/`.

```bash
python3 -m pip install --requirement requirements_common.txt
python3 -m pip install --requirement requirements_dev.txt
```
