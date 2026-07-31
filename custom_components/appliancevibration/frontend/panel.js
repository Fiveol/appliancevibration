/**
 * ApplianceVibration sidebar panel.
 *
 * Self-contained ES module (no bare imports): the Home Assistant frontend
 * loads this file as a module via `module_url` without an import map, so
 * everything is hand-rolled on top of the page's design tokens.
 *
 * The frontend assigns `hass`, `panel`, `narrow` and `route` properties.
 */

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "devices", label: "Devices" },
  { id: "settings", label: "Settings" },
];

const ICON_SVG = `
  <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
    <path fill="currentColor" d="M16,19H8V5H16M16.5,3H7.5A1.5,1.5 0 0,0 6,4.5V19.5A1.5,1.5 0 0,0 7.5,21H16.5A1.5,1.5 0 0,0 18,19.5V4.5A1.5,1.5 0 0,0 16.5,3Z"/>
  </svg>`;

class ApplianceVibrationPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._panel = null;
    this._tab = "overview";
    this._renderScheduled = false;
    this.attachShadow({ mode: "open" });
  }

  set hass(value) {
    this._hass = value;
    this._scheduleRender();
  }

  set panel(value) {
    this._panel = value;
    this._scheduleRender();
  }

  set narrow(value) {
    /* Not needed for this layout. */
  }

  set route(value) {
    /* Not needed for this layout. */
  }

  connectedCallback() {
    this._scheduleRender();
  }

  _scheduleRender() {
    if (this._renderScheduled) return;
    this._renderScheduled = true;
    Promise.resolve().then(() => {
      this._renderScheduled = false;
      this._render();
    });
  }

  _render() {
    const root = this.shadowRoot;
    if (!root) return;

    root.innerHTML = `
      <style>
        :host {
          display: block;
          box-sizing: border-box;
          min-height: 100vh;
          padding: 16px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--primary-font-family, Roboto, sans-serif);
          font-size: 14px;
          line-height: 1.5;
        }
        .header {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 4px 4px 12px;
        }
        .icon {
          width: 28px;
          height: 28px;
          color: var(--primary-color);
          flex: none;
        }
        .title {
          font-size: 20px;
          font-weight: 500;
          color: var(--primary-text-color);
          margin: 0;
        }
        .subtitle {
          color: var(--secondary-text-color);
          font-size: 12px;
          margin-top: 2px;
        }
        .tabs {
          display: flex;
          gap: 4px;
          border-bottom: 1px solid var(--divider-color);
          margin-bottom: 16px;
        }
        .tab {
          appearance: none;
          background: none;
          border: none;
          border-bottom: 2px solid transparent;
          padding: 10px 16px;
          font: inherit;
          font-size: 14px;
          color: var(--secondary-text-color);
          cursor: pointer;
          user-select: none;
          margin-bottom: -1px;
          transition: color 180ms ease-in-out, border-color 180ms ease-in-out;
        }
        .tab:hover {
          color: var(--primary-text-color);
        }
        .tab.active {
          color: var(--primary-color);
          border-bottom-color: var(--primary-color);
        }
        .tab:focus-visible {
          outline: 2px solid var(--primary-color);
          outline-offset: -2px;
        }
        .content {
          max-width: 900px;
        }
        .card {
          background: var(--card-background-color, var(--ha-card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          border: 1px solid var(--ha-card-border-color, transparent);
          box-shadow: var(--ha-card-box-shadow, none);
          padding: 16px;
          margin-bottom: 16px;
        }
        .card h2 {
          margin: 0 0 8px;
          font-size: 16px;
          font-weight: 500;
        }
        .card p {
          margin: 0 0 12px;
          color: var(--secondary-text-color);
        }
        .stat-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
          gap: 12px;
        }
        .stat {
          background: var(--state-icon-color, transparent);
          border: 1px solid var(--divider-color);
          border-radius: var(--ha-card-border-radius, 12px);
          padding: 12px 16px;
        }
        .stat .value {
          font-size: 24px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .stat .label {
          color: var(--secondary-text-color);
          font-size: 12px;
          margin-top: 4px;
        }
        .empty {
          text-align: center;
          padding: 24px 8px;
          color: var(--secondary-text-color);
        }
        .setting-row {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color);
          color: var(--secondary-text-color);
        }
        .setting-row:last-child {
          border-bottom: none;
        }
        .setting-row .key {
          color: var(--primary-text-color);
          font-weight: 500;
        }
        .setting-row .value {
          text-align: right;
          word-break: break-all;
        }
      </style>

      <div class="header">
        ${ICON_SVG}
        <div>
          <h1 class="title">${this._title()}</h1>
          <div class="subtitle">ApplianceVibration</div>
        </div>
      </div>

      <div class="tabs" role="tablist">
        ${TABS.map(
          (tab) => `
          <button
            type="button"
            role="tab"
            aria-selected="${this._tab === tab.id}"
            class="tab${this._tab === tab.id ? " active" : ""}"
            data-tab="${tab.id}"
          >${tab.label}</button>
        `
        ).join("")}
      </div>

      <div class="content" role="tabpanel">${this._tabContent()}</div>
    `;

    root.querySelector(".tabs").addEventListener("click", (ev) => {
      const button = ev.target.closest("[data-tab]");
      if (!button || button.dataset.tab === this._tab) return;
      this._tab = button.dataset.tab;
      this._render();
    });
  }

  _title() {
    const panelConfig = this._panel && this._panel.config;
    return (panelConfig && panelConfig.title) || "Appliance Vibration";
  }

  _tabContent() {
    switch (this._tab) {
      case "devices":
        return this._devicesTab();
      case "settings":
        return this._settingsTab();
      default:
        return this._overviewTab();
    }
  }

  _overviewTab() {
    const hass = this._hass;
    const entities = hass ? Object.keys(hass.states).length : 0;
    const version = hass && hass.config ? hass.config.version : "unknown";
    const now = new Date().toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });

    return `
      <div class="card">
        <h2>Welcome</h2>
        <p>
          This panel is provided by the ApplianceVibration integration. Its
          tabs are ready to be filled in with your appliance data.
        </p>
        <div class="stat-grid">
          <div class="stat"><div class="value">${entities}</div><div class="label">Entities</div></div>
          <div class="stat"><div class="value">${version}</div><div class="label">Home Assistant</div></div>
          <div class="stat"><div class="value">${now}</div><div class="label">Last update</div></div>
        </div>
      </div>
    `;
  }

  _devicesTab() {
    const hass = this._hass;
    const ownEntities = hass
      ? Object.values(hass.states).filter(
          (state) => state.entity_id.startsWith("appliancevibration.")
      )
      : [];

    if (ownEntities.length === 0) {
      return `
        <div class="card">
          <h2>Devices</h2>
          <div class="empty">
            No appliance_vibration entities found yet.<br />
            Sensors created by this integration will be listed here.
          </div>
        </div>
      `;
    }

    return `
      <div class="card">
        <h2>Devices</h2>
        <div class="stat-grid">
          ${ownEntities
            .map(
              (state) => `
                <div class="stat">
                  <div class="value">${state.state}</div>
                  <div class="label">${state.entity_id}</div>
                </div>
              `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  _settingsTab() {
    const panelConfig =
      (this._panel && this._panel.config) || {};
    const icon = panelConfig.icon || "mdi:vibrate";
    const version = panelConfig.version || "unknown";

    return `
      <div class="card">
        <h2>Settings</h2>
        <div class="setting-row">
          <span class="key">Panel title</span>
          <span class="value">${this._title()}</span>
        </div>
        <div class="setting-row">
          <span class="key">Sidebar icon</span>
          <span class="value">${icon}</span>
        </div>
        <div class="setting-row">
          <span class="key">Config entry version</span>
          <span class="value">${version}</span>
        </div>
      </div>
    `;
  }
}

customElements.define("appliance-vibration-panel", ApplianceVibrationPanel);
