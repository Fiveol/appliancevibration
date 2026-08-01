/**
 * ApplianceVibration sidebar panel.
 *
 * Self-contained ES module (no bare imports): the Home Assistant frontend
 * loads this file as a module via `module_url` without an import map, so
 * everything is hand-rolled on top of the page's design tokens.
 *
 * The frontend assigns `hass`, `panel`, `narrow` and `route` properties.
 * All integration state is fetched through the `appliancevibration/*`
 * websocket commands and live-updated from `state_changed` events.
 */

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "devices", label: "Devices" },
  { id: "settings", label: "Settings" },
];

const PALETTE = [
  "#1e88e5", "#43a047", "#f4511e", "#8e24aa", "#00897b",
  "#e53935", "#6d4c41", "#fb8c00", "#3949ab", "#00acc1",
];

const STAGE_LABELS = {
  idle: "Idle", soak: "Soak", wash: "Wash", rinse: "Rinse",
  drain: "Drain", spin: "Spin", pause: "Pause",
};

const STAGE_COLORS = {
  idle: "#9e9e9e", soak: "#8e24aa", wash: "#1e88e5", rinse: "#00897b",
  drain: "#757575", spin: "#f4511e", pause: "#9e9e9e",
};

const ICON_SVG = `
  <svg viewBox="0 0 24 24" class="icon" aria-hidden="true">
    <path fill="currentColor" d="M16,19H8V5H16M16.5,3H7.5A1.5,1.5 0 0,0 6,4.5V19.5A1.5,1.5 0 0,0 7.5,21H16.5A1.5,1.5 0 0,0 18,19.5V4.5A1.5,1.5 0 0,0 16.5,3Z"/>
  </svg>`;

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

const fmtMinutes = (minutes) => {
  const total = Math.max(0, Math.round(Number(minutes) || 0));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  return hours ? `${hours}h ${mins}m` : `${mins}m`;
};

const fmtRemaining = (seconds) => {
  const total = Math.max(0, Math.ceil(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const mins = Math.ceil((total % 3600) / 60);
  return hours ? `${hours}h ${mins}m` : `${mins}m`;
};

const fmtAgo = (iso) => {
  if (!iso) return "";
  const seconds = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

const fmtClock = (iso) =>
  new Date(iso).toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" });

class ApplianceVibrationPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._panel = null;
    this._config = null;
    this._tab = "overview";
    this._histories = {};
    this._renderScheduled = false;
    this._subscribed = false;
    this._refreshTimer = null;
    this._panelInited = false;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${this._style()}</style><div id="app"></div>`;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
  }

  set hass(value) {
    this._hass = value;
    if (!this._subscribed && value && value.connection) {
      this._subscribed = true;
      value.connection.subscribeEvents(
        (event) => this._onStateChanged(event),
        "state_changed"
      ).catch(() => {});
    }
    if (!this._panelInited) {
      this._panelInited = true;
      this._refresh();
    }
    this._scheduleRender();
  }

  set panel(value) {
    this._panel = value;
    this._scheduleRender();
  }

  set narrow(value) {}

  set route(value) {}

  connectedCallback() {
    this._scheduleRender();
    if (this._hass && !this._panelInited) {
      this._panelInited = true;
      this._refresh();
    }
  }

  disconnectedCallback() {
    this._subscribed = false;
    if (this._refreshTimer) clearTimeout(this._refreshTimer);
  }

  /* ------------------------------------------------------------------ */

  _scheduleRender() {
    if (this._renderScheduled) return;
    this._renderScheduled = true;
    Promise.resolve().then(() => {
      this._renderScheduled = false;
      this._render();
    });
  }

  _send(type, data = {}) {
    return this._hass.connection.sendMessagePromise({
      type: `appliancevibration/${type}`,
      ...data,
    });
  }

  async _refresh() {
    if (!this._hass || !this._hass.connection) return;
    try {
      this._config = await this._send("config");
      this._scheduleRender();
    } catch (err) {
      if (this._config === null) this._toast(`Failed to load: ${err.message}`, true);
    }
  }

  _scheduleRefresh(delay = 1500) {
    if (this._refreshTimer) return;
    this._refreshTimer = setTimeout(() => {
      this._refreshTimer = null;
      this._refresh();
    }, delay);
  }

  async _mutate(name, payload, success = "Saved") {
    try {
      await this._send(name, payload);
      await this._refresh();
      if (success) this._toast(success);
      return true;
    } catch (err) {
      this._toast(err.message || "Something went wrong", true);
      return false;
    }
  }

  /* ------------------------------------------------------------------ */

  _title() {
    const config = this._panel && this._panel.config;
    return (config && config.title) || "Appliance Vibration";
  }

  _render() {
    const root = this.shadowRoot;
    if (!root) return;
    const app = root.querySelector("#app");
    if (!app) return;
    const config = this._config;

    app.innerHTML = `
      <div class="header">
        ${ICON_SVG}
        <div>
          <h1 class="title">${esc(this._title())}</h1>
          <div class="subtitle">ApplianceVibration</div>
        </div>
      </div>
      <div class="tabs" role="tablist">
        ${TABS.map((tab) => `
          <button type="button" role="tab"
            aria-selected="${this._tab === tab.id}"
            class="tab${this._tab === tab.id ? " active" : ""}"
            data-action="tab" data-tab="${tab.id}">
            ${tab.label}
            ${tab.id === "devices" && config && config.devices.length
              ? `<span class="badge">${config.devices.length}</span>` : ""}
          </button>`).join("")}
      </div>
      <div class="content" role="tabpanel">
        ${config === null
          ? this._loading()
          : this._tab === "overview" ? this._overviewView()
          : this._tab === "settings" ? this._settingsView()
          : this._devicesView()}
      </div>
    `;

    app.querySelectorAll("[data-spark]").forEach((canvas) => {
      const device = this._deviceById(canvas.dataset.spark);
      if (device) this._drawSparkFor(canvas, device);
    });
  }

  _drawSparkFor(canvas, device) {
    if (device.state.running) {
      const history = (this._histories[device.id] = this._histories[device.id] || []);
      if (history.length === 0 && device.state.magnitude > 0) history.push(device.state.magnitude);
      this._sparkline(canvas, history, true);
      return;
    }
    const history = this._histories[device.id];
    if (history && history.length) {
      this._sparkline(canvas, history, false);
      return;
    }
    const last = device.cycles[0];
    this._sparkline(
      canvas,
      last ? Array(48).fill(last.magnitude_mean) : [],
      false
    );
  }

  _style() {
    return `
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
      * { box-sizing: border-box; }
      button { font: inherit; cursor: pointer; }

      .header { display: flex; align-items: center; gap: 12px; padding: 4px 4px 12px; }
      .icon { width: 28px; height: 28px; color: var(--primary-color); flex: none; }
      .title { font-size: 20px; font-weight: 500; margin: 0; }
      .subtitle { color: var(--secondary-text-color); font-size: 12px; }

      .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--divider-color); margin-bottom: 16px; }
      .tab {
        appearance: none; background: none; border: none;
        border-bottom: 2px solid transparent;
        padding: 10px 16px; font-size: 14px; margin-bottom: -1px;
        color: var(--secondary-text-color); user-select: none;
        transition: color 180ms ease, border-color 180ms ease;
        display: flex; align-items: center; gap: 8px;
      }
      .tab:hover { color: var(--primary-text-color); }
      .tab.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
      .tab:focus-visible { outline: 2px solid var(--primary-color); outline-offset: -2px; }
      .badge {
        background: var(--primary-color); color: var(--text-primary-color, #fff);
        border-radius: 10px; font-size: 11px; min-width: 18px; height: 18px;
        display: inline-flex; align-items: center; justify-content: center; padding: 0 5px;
      }
      .content { max-width: 960px; }

      /* ---- shared bits ---- */
      .card {
        background: var(--card-background-color, var(--ha-card-background-color));
        border-radius: var(--ha-card-border-radius, 12px);
        border: 1px solid var(--ha-card-border-color, transparent);
        box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.08));
        padding: 16px; margin-bottom: 16px;
      }
      .card h2 { margin: 0 0 4px; font-size: 16px; font-weight: 500; }
      .muted { color: var(--secondary-text-color); }
      .row { display: flex; align-items: center; gap: 8px; }

      .btn {
        border: none; border-radius: 8px; padding: 8px 16px;
        font-size: 14px; font-weight: 500; transition: filter 150ms ease;
      }
      .btn:hover { filter: brightness(1.1); }
      .btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
      .btn.ghost { background: transparent; color: var(--primary-color); }
      .btn.outline { background: transparent; color: var(--primary-text-color); border: 1px solid var(--divider-color); }
      .btn.danger { background: var(--error-color); color: var(--text-primary-color, #fff); }
      .btn:disabled { opacity: 0.5; cursor: default; }

      .icon-btn {
        background: none; border: none; padding: 6px; border-radius: 50%;
        color: var(--secondary-text-color); display: inline-flex;
        transition: color 150ms ease, background 150ms ease;
      }
      .icon-btn:hover { color: var(--primary-text-color); background: var(--divider-color); }
      .icon-btn svg { width: 18px; height: 18px; }

      .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
      .stat { border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); padding: 12px 16px; }
      .stat .value { font-size: 24px; font-weight: 500; line-height: 1.2; }
      .stat .label { color: var(--secondary-text-color); font-size: 12px; margin-top: 4px; }

      .chip {
        display: inline-flex; align-items: center; gap: 6px;
        border-radius: 10px; padding: 2px 10px; font-size: 12px;
        background: var(--divider-color, rgba(128, 128, 128, 0.2));
        color: var(--primary-text-color); border: none; white-space: nowrap;
      }
      .chip .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
      .chip.ghost-chip { background: transparent; border: 1px dashed var(--divider-color); color: var(--secondary-text-color); }
      .chip.ghost-chip:hover { color: var(--primary-color); border-color: var(--primary-color); }

      .pulse { animation: av-pulse 1.6s ease-in-out infinite; }
      @keyframes av-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(67, 160, 71, 0.5); }
        50% { box-shadow: 0 0 0 5px rgba(67, 160, 71, 0); }
      }

      .empty {
        text-align: center; padding: 48px 16px; color: var(--secondary-text-color);
      }
      .empty .big-icon { width: 56px; height: 56px; margin: 0 auto 12px; color: var(--primary-color); opacity: 0.6; }
      .empty h2 { color: var(--primary-text-color); margin: 0 0 4px; }

      .list-row {
        display: flex; align-items: center; gap: 10px;
        padding: 8px 0; border-bottom: 1px solid var(--divider-color);
      }
      .list-row:last-child { border-bottom: none; }
      .list-row .grow { flex: 1; min-width: 0; }
      .list-row .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .list-row .sub { color: var(--secondary-text-color); font-size: 12px; }

      .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
      .toolbar h2 { margin: 0; font-size: 18px; font-weight: 500; }

      .device-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }

      .device-card { position: relative; overflow: hidden; }
      .device-card.running { border-color: var(--success-color, #43a047); }
      .device-top { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
      .device-avatar {
        width: 34px; height: 34px; border-radius: 50%; flex: none;
        display: flex; align-items: center; justify-content: center;
        background: var(--divider-color);
      }
      .device-avatar svg { width: 20px; height: 20px; color: var(--primary-color); }
      .device-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .status-chip {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 12px; font-weight: 500; padding: 3px 10px; border-radius: 10px;
      }
      .status-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
      .status-chip.running { color: var(--success-color, #43a047); background: rgba(67, 160, 71, 0.12); }
      .status-chip.idle { color: var(--secondary-text-color); background: var(--divider-color); }
      .status-chip .dot.running-dot { animation: av-blink 1.2s ease-in-out infinite; }
      @keyframes av-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

      .spark-wrap { margin: 4px 0 10px; }
      .spark { width: 100%; height: 44px; display: block; }

      .stage-chip {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 12px; font-weight: 500; padding: 3px 10px; border-radius: 10px;
        color: var(--primary-text-color); background: var(--divider-color);
      }
      .stage-chip .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
      .cycle-progress {
        height: 4px; border-radius: 2px; background: var(--divider-color);
        margin: 8px 0 4px; overflow: hidden;
      }
      .cycle-progress span {
        display: block; height: 100%; background: var(--success-color, #43a047);
        transition: width 500ms ease;
      }

      .mini-stats { display: flex; gap: 16px; margin-bottom: 10px; }
      .mini-stat .val { font-size: 16px; font-weight: 500; }
      .mini-stat .lbl { color: var(--secondary-text-color); font-size: 11px; }

      .section-label {
        font-size: 11px; font-weight: 500; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--secondary-text-color);
        margin: 12px 0 6px;
      }
      .chips { display: flex; flex-wrap: wrap; gap: 6px; }
      .conf { font-size: 11px; color: var(--secondary-text-color); }
      .unclassified { color: var(--warning-color, #f9a825); font-weight: 500; }

      /* ---- forms ---- */
      .field { margin-bottom: 14px; }
      .field label { display: block; font-size: 12px; color: var(--secondary-text-color); margin-bottom: 6px; }
      .field .optional { font-style: italic; opacity: 0.8; }
      input[type="text"], input[type="number"], select, .picker {
        width: 100%; padding: 10px 12px; border-radius: 8px;
        border: 1px solid var(--divider-color); background: var(--input-background-color, transparent);
        color: var(--primary-text-color); font: inherit;
      }
      input:focus, select:focus, .picker:focus-within { outline: 2px solid var(--primary-color); outline-offset: -1px; }
      input.invalid { border-color: var(--error-color); }
      .field-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
      details.advanced { margin-top: 4px; }
      details.advanced summary {
        cursor: pointer; font-size: 12px; color: var(--primary-color); user-select: none;
      }

      /* ---- dialogs ---- */
      .overlay {
        position: fixed; inset: 0; z-index: 1000;
        background: rgba(0, 0, 0, 0.45); display: flex; align-items: center; justify-content: center;
        animation: av-fade 150ms ease;
      }
      @keyframes av-fade { from { opacity: 0; } to { opacity: 1; } }
      .dialog {
        width: min(480px, calc(100vw - 32px)); max-height: 88vh; overflow: auto;
        background: var(--card-background-color, var(--ha-card-background-color));
        border-radius: var(--ha-card-border-radius, 16px);
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
        padding: 20px; animation: av-rise 180ms ease;
      }
      @keyframes av-rise { from { transform: translateY(12px); opacity: 0; } to { transform: none; opacity: 1; } }
      .dialog h3 { margin: 0 0 16px; font-size: 18px; font-weight: 500; }
      .dialog .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
      .dialog .danger-zone {
        margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--divider-color);
        display: flex; justify-content: space-between; align-items: center; gap: 12px;
      }
      .dialog .danger-zone .dz-text { font-size: 13px; }
      .dialog .danger-zone .dz-title { font-weight: 500; color: var(--error-color); }
      .swatches { display: flex; gap: 6px; flex-wrap: wrap; }
      .swatch {
        width: 26px; height: 26px; border-radius: 50%; border: 2px solid transparent; padding: 0;
        transition: transform 120ms ease;
      }
      .swatch:hover { transform: scale(1.15); }
      .swatch.selected { border-color: var(--primary-text-color); }

      /* ---- toast ---- */
      .toast {
        position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
        z-index: 1100; padding: 10px 18px; border-radius: 10px;
        background: #323232; color: #fff; font-size: 13px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
        animation: av-rise 180ms ease;
      }
      .toast.error { background: var(--error-color, #db4437); }

      .loader {
        display: flex; align-items: center; justify-content: center; padding: 60px 0;
        color: var(--secondary-text-color);
      }
      .spinner {
        width: 26px; height: 26px; border-radius: 50%;
        border: 3px solid var(--divider-color); border-top-color: var(--primary-color);
        animation: av-spin 0.8s linear infinite; margin-right: 12px;
      }
      @keyframes av-spin { to { transform: rotate(360deg); } }

      .divider { border: none; border-top: 1px solid var(--divider-color); margin: 16px 0; }
    `;
  }

  _loading() {
    return `<div class="loader"><div class="spinner"></div>Loading…</div>`;
  }

  /* ------------------------------------------------------------------ */
  /*  Overview                                                           */

  _overviewView() {
    const devices = this._config.devices;
    if (devices.length === 0) {
      return `
        <div class="card empty">
          <div class="big-icon">${ICON_SVG}</div>
          <h2>No devices yet</h2>
          <p class="muted">Create your first device and assign a vibration sensor to start tracking cycles.</p>
          <button class="btn primary" data-action="add-device">Add your first device</button>
        </div>`;
    }

    const running = devices.filter((d) => d.state.running);
    const now = Date.now();
    const dayMs = 86400000;
    const cyclesToday = devices.reduce(
      (sum, d) => sum + d.cycles.filter((c) => now - Date.parse(c.ended) < dayMs).length, 0);
    const totalCycles = devices.reduce((sum, d) => sum + d.cycles.length, 0);
    const labeled = devices.reduce(
      (sum, d) => sum + d.cycles.filter((c) => c.program_id || c.labeled).length, 0);
    const rate = totalCycles ? Math.round((labeled / totalCycles) * 100) : 0;

    const recent = devices
      .flatMap((d) => d.cycles.slice(0, 5).map((c) => ({ ...c, device: d })))
      .sort((a, b) => Date.parse(b.ended) - Date.parse(a.ended))
      .slice(0, 10);

    return `
      <div class="stat-grid">
        <div class="stat"><div class="value">${devices.length}</div><div class="label">Devices</div></div>
        <div class="stat"><div class="value">${running.length}</div><div class="label">Running now</div></div>
        <div class="stat"><div class="value">${cyclesToday}</div><div class="label">Cycles today</div></div>
        <div class="stat"><div class="value">${rate}%</div><div class="label">Labeled cycles</div></div>
      </div>

      ${running.length ? `
        <div class="section-label">Running now</div>
        <div class="device-grid">
          ${running.map((d) => this._deviceCard(d)).join("")}
        </div>` : ""}

      <div class="section-label">Recent cycles</div>
      <div class="card">
        ${recent.length ? recent.map((c) => this._cycleRow(c.device, c, false)).join("")
          : `<div class="empty" style="padding: 20px;">No cycles recorded yet. Run your appliance and the integration will detect the cycle automatically.</div>`}
      </div>`;
  }

  _cycleRow(device, cycle, withLabel) {
    const program = device.programs.find((p) => p.id === cycle.program_id);
    return `
      <div class="list-row">
        <span class="name" style="min-width: 130px;">${esc(device.name)}</span>
        <span class="grow">
          ${program
            ? `<span class="chip"><span class="dot" style="background:${esc(program.color)}"></span>${esc(program.name)}</span>`
            : `<span class="chip unclassified">Not classified</span>`}
          ${cycle.confidence != null ? `<span class="conf"> · ${Math.round(cycle.confidence * 100)}%</span>` : ""}
        </span>
        <span class="muted">${fmtMinutes(cycle.duration)}</span>
        <span class="muted" style="min-width: 64px; text-align: right;">${fmtAgo(cycle.ended)}</span>
        ${cycle.stages && cycle.stages.length
          ? `<button class="btn outline" style="padding: 4px 12px; font-size: 12px;" data-action="cycle-detail" data-device="${esc(device.id)}" data-cycle="${esc(cycle.id)}">${cycle.stages.length} stage${cycle.stages.length === 1 ? "" : "s"}</button>`
          : ""}
        ${withLabel && !program
          ? `<button class="btn outline" style="padding: 4px 12px; font-size: 12px;" data-action="label-cycle" data-device="${esc(device.id)}" data-cycle="${esc(cycle.id)}">Label</button>`
          : ""}
      </div>`;
  }

  /* ------------------------------------------------------------------ */
  /*  Devices                                                            */

  _devicesView() {
    const devices = this._config.devices;
    return `
      <div class="toolbar">
        <h2>Devices</h2>
        <button class="btn primary" data-action="add-device">Add device</button>
      </div>
      ${devices.length ? `
        <div class="device-grid">
          ${devices.map((d) => this._deviceCard(d)).join("")}
        </div>` : `
        <div class="card empty">
          <div class="big-icon">${ICON_SVG}</div>
          <h2>No devices yet</h2>
          <p class="muted">Add an appliance, pick its vibration sensor, and ApplianceVibration will learn its programs.</p>
          <button class="btn primary" data-action="add-device">Add device</button>
        </div>`}`;
  }

  _deviceCard(device) {
    const running = device.state.running;
    const level = device.state.magnitude || 0;
    const history = this._histories[device.id] || [];
    const lastCycle = device.cycles[0];
    const lastProgram = lastCycle && device.programs.find((p) => p.id === lastCycle.program_id);
    const stage = running ? this._stageFor(device) : "idle";
    const progress = running ? (device.state.progress || 0) : 0;

    return `
      <div class="card device-card${running ? " running" : ""}" data-device-card="${esc(device.id)}">
        <div class="device-top">
          <div class="device-avatar">${ICON_SVG}</div>
          <div class="device-name" title="${esc(device.name)}">${esc(device.name)}</div>
          <span class="status-chip ${running ? "running" : "idle"}" data-status="${esc(device.id)}">
            <span class="dot ${running ? "running-dot" : ""}"></span>
            ${running ? "Running" : "Idle"}
          </span>
          <button class="icon-btn" title="Edit device" data-action="edit-device" data-device="${esc(device.id)}">
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z"/></svg>
          </button>
          <button class="icon-btn" title="Delete device" data-action="delete-device" data-device="${esc(device.id)}">
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19M8,9H16V19H8V9M15.5,4L14.5,3H9.5L8.5,4H5V6H19V4H15.5Z"/></svg>
          </button>
        </div>
        <div class="spark-wrap">
          <canvas class="spark" data-spark="${esc(device.id)}"></canvas>
        </div>
        ${running ? `
          <div class="row" style="margin-bottom: 4px;">
            <span class="stage-chip" data-stage="${esc(device.id)}">
              <span class="dot" style="background:${esc(STAGE_COLORS[stage] || STAGE_COLORS.idle)}"></span>
              <span class="stage-label">${esc(STAGE_LABELS[stage] || "Running")}</span>
            </span>
          </div>
          <div class="cycle-progress" data-progress="${esc(device.id)}">
            <span style="width:${Math.max(0, Math.min(100, progress * 100))}%"></span>
          </div>` : ""}
        <div class="mini-stats">
          <div class="mini-stat">
            <div class="val" data-level="${esc(device.id)}">${level.toFixed(2)}</div>
            <div class="lbl">Vibration</div>
          </div>
          <div class="mini-stat">
            <div class="val" data-dur="${esc(device.id)}">
              ${running && device.state.since ? fmtMinutes((Date.now() - device.state.since * 1000) / 60000) : lastCycle ? fmtMinutes(lastCycle.duration) : "—"}
            </div>
            <div class="lbl">${running ? "Elapsed" : "Last cycle"}</div>
          </div>
          <div class="mini-stat">
            <div class="val" data-remaining="${esc(device.id)}">
              ${running && device.state.time_remaining != null ? fmtRemaining(device.state.time_remaining) : "—"}
            </div>
            <div class="lbl">Remaining</div>
          </div>
          <div class="mini-stat">
            <div class="val" data-cycles="${esc(device.id)}">${device.cycles.length}</div>
            <div class="lbl">Cycles</div>
          </div>
        </div>
        ${device.programs.length ? `
          <div class="section-label">Programs</div>
          <div class="chips" style="margin-bottom: 4px;">
            ${device.programs.map((p) => `
              <span class="chip" title="${p.samples} labeled cycle${p.samples === 1 ? "" : "s"}">
                <span class="dot" style="background:${esc(p.color)}"></span>
                ${esc(p.name)} · ${p.samples}
              </span>`).join("")}
          </div>` : `
          <div class="section-label">Programs</div>
          <div class="muted" style="font-size: 12px; margin-bottom: 4px;">
            No programs yet — label a cycle to start teaching the device.
          </div>`}

        <div class="section-label">Recent cycles</div>
        <div>
          ${device.cycles.slice(0, 4).map((c) => this._cycleRow(device, c, true)).join("")}
          ${device.cycles.length === 0 ? `<div class="muted" style="font-size: 12px;">No cycles recorded yet.</div>` : ""}
        </div>
      </div>`;
  }

  /* ------------------------------------------------------------------ */
  /*  Settings                                                           */

  _settingsView() {
    const panelConfig = (this._panel && this._panel.config) || {};
    return `
      <div class="card">
        <h2>Panel</h2>
        <div class="list-row"><span class="grow muted">Title</span><b>${esc(this._title())}</b></div>
        <div class="list-row"><span class="grow muted">Sidebar icon</span><b>${esc(panelConfig.icon || "mdi:vibrate")}</b></div>
        <div class="list-row"><span class="grow muted">Config entry version</span><b>${esc(panelConfig.version || "unknown")}</b></div>
      </div>
      <div class="card">
        <h2>How it works</h2>
        <p class="muted">ApplianceVibration watches the sensors you assign to a device and learns the programs of your appliances.</p>
        <div class="list-row">
          <span class="chip"><span class="dot" style="background:var(--primary-color)"></span>1</span>
          <span class="grow name">Create a device and assign its vibration binary sensor — it decides IF vibration is happening. Optionally add X/Y/Z movement sensors to measure HOW strongly (raw accelerometer output works out of the box).</span>
        </div>
        <div class="list-row">
          <span class="chip"><span class="dot" style="background:var(--primary-color)"></span>2</span>
          <span class="grow name">Run a cycle. When it finishes, the integration asks you what program it was.</span>
        </div>
        <div class="list-row">
          <span class="chip"><span class="dot" style="background:var(--primary-color)"></span>3</span>
          <span class="grow name">After a few labeled cycles, future cycles are classified automatically by duration and vibration profile.</span>
        </div>
        <div class="list-row">
          <span class="chip"><span class="dot" style="background:var(--primary-color)"></span>4</span>
          <span class="grow name">While a cycle runs, the current stage (Wash, Spin, …) and the estimated time remaining are shown live.</span>
        </div>
      </div>
      <div class="card">
        <h2>Danger zone</h2>
        <div class="list-row">
          <div class="grow name">Remove all devices and learning data</div>
          <button class="btn danger" data-action="reset-all">Reset everything</button>
        </div>
      </div>`;
  }

  /* ------------------------------------------------------------------ */
  /*  Live updates                                                       */

  _magnitudeFor(device) {
    const ids = device.entity_ids || {};
    if (ids.level) {
      const state = this._hass.states[ids.level];
      const value = state && parseFloat(state.state);
      if (Number.isFinite(value)) return value;
    }
    const axes = device.entities || {};
    let sum = 0;
    let count = 0;
    for (const axis of ["x", "y", "z"]) {
      const state = axes[axis] && this._hass.states[axes[axis]];
      const value = state && parseFloat(state.state);
      if (Number.isFinite(value)) { sum += value * value; count += 1; }
    }
    return count ? Math.sqrt(sum) : 0;
  }

  _onStateChanged(event) {
    if (!this._config) return;
    const entityId = event.data && event.data.entity_id;
    if (!entityId) return;
    const device = this._config.devices.find(
      (d) => Object.values(d.entity_ids || {}).includes(entityId)
        || Object.values(d.entities || {}).includes(entityId));
    if (!device) return;

    const magnitude = this._magnitudeFor(device);
    const history = (this._histories[device.id] = this._histories[device.id] || []);
    if (magnitude > 0 || history.length === 0) history.push(magnitude);
    if (history.length > 120) history.shift();

    const root = this.shadowRoot;
    if (root) this._patchDevice(root, device, magnitude);
    this._scheduleRefresh();
  }

  _patchDevice(root, device, magnitude) {
    const card = root.querySelector(`[data-device-card="${CSS.escape(device.id)}"]`);
    if (!card) return;

    const level = card.querySelector(`[data-level="${CSS.escape(device.id)}"]`);
    if (level) level.textContent = magnitude.toFixed(2);

    const canvas = card.querySelector(`[data-spark="${CSS.escape(device.id)}"]`);
    if (canvas) this._sparkline(canvas, this._histories[device.id] || [], device.state.running);

    const status = card.querySelector(`[data-status="${CSS.escape(device.id)}"]`);
    if (status) {
      const running = device.state.running;
      status.className = `status-chip ${running ? "running" : "idle"}`;
      status.innerHTML = `<span class="dot ${running ? "running-dot" : ""}"></span>${running ? "Running" : "Idle"}`;
      card.classList.toggle("running", running);
    }

    const dur = card.querySelector(`[data-dur="${CSS.escape(device.id)}"]`);
    if (dur) {
      dur.textContent = device.state.running && device.state.since
        ? fmtMinutes((Date.now() - device.state.since * 1000) / 60000)
        : device.cycles[0] ? fmtMinutes(device.cycles[0].duration) : "—";
    }

    const stageChip = card.querySelector(`[data-stage="${CSS.escape(device.id)}"]`);
    if (stageChip) {
      const stage = this._stageFor(device);
      const dot = stageChip.querySelector(".dot");
      const label = stageChip.querySelector(".stage-label");
      if (dot) dot.style.background = STAGE_COLORS[stage] || STAGE_COLORS.idle;
      if (label) label.textContent = STAGE_LABELS[stage] || "Running";
    }

    const progress = card.querySelector(`[data-progress="${CSS.escape(device.id)}"]`);
    if (progress) {
      const bar = progress.firstElementChild;
      if (bar) {
        const pct = Math.max(0, Math.min(100, (device.state.progress || 0) * 100));
        bar.style.width = `${pct}%`;
      }
    }

    const remaining = card.querySelector(`[data-remaining="${CSS.escape(device.id)}"]`);
    if (remaining) {
      remaining.textContent = device.state.running && device.state.time_remaining != null
        ? fmtRemaining(device.state.time_remaining) : "—";
    }
  }

  _stageFor(device) {
    const id = device.entity_ids && device.entity_ids.stage;
    const state = id && this._hass && this._hass.states[id];
    if (state && state.state && STAGE_LABELS[state.state]) return state.state;
    return (device.state && device.state.stage) || "idle";
  }

  _sparkline(canvas, values, running) {
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || canvas.parentElement.clientWidth || 300;
    const height = canvas.clientHeight || 44;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const color = running
      ? getComputedStyle(this).getPropertyValue("--success-color").trim() || "#43a047"
      : getComputedStyle(this).getPropertyValue("--primary-color").trim() || "#1e88e5";
    const muted = getComputedStyle(this).getPropertyValue("--secondary-text-color").trim();

    if (values.length < 2) {
      ctx.strokeStyle = muted;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
      ctx.setLineDash([]);
      return;
    }

    const max = Math.max(...values, 1e-6);
    const step = width / 119;
    const points = values.map((v, i) => ({
      x: i * step,
      y: height - (Math.min(v, max) / max) * (height - 6) - 3,
    }));

    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, color + "55");
    gradient.addColorStop(1, color + "00");
    ctx.beginPath();
    ctx.moveTo(points[0].x, height);
    points.forEach((p) => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    points.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();
  }

  /* ------------------------------------------------------------------ */
  /*  Interactions                                                       */

  _onClick(event) {
    const action = event.target.closest("[data-action]");
    if (!action) return;
    const data = action.dataset;

    switch (data.action) {
      case "tab":
        this._tab = data.tab;
        this._scheduleRender();
        break;
      case "add-device":
        this._openDeviceDialog(null);
        break;
      case "edit-device":
        this._openDeviceDialog(this._deviceById(data.device));
        break;
      case "delete-device":
        this._confirmDeleteDevice(this._deviceById(data.device));
        break;
      case "label-cycle":
        this._openLabelDialog(this._deviceById(data.device), data.cycle);
        break;
      case "cycle-detail":
        this._openCycleDialog(this._deviceById(data.device), data.cycle);
        break;
      case "reset-all":
        this._confirmResetAll();
        break;
      case "dialog-cancel":
        this._closeDialog(action.closest(".overlay"));
        break;
      case "dialog-ok":
        this._submitDialog(action.closest(".overlay"));
        break;
      case "label-ok":
        this._submitLabel(action.closest(".overlay"));
        break;
      case "label-new":
        this._toggleNewProgram(action.closest(".overlay"));
        break;
      case "pick-program":
        this._pickProgram(action.closest(".overlay"), data.program);
        break;
      case "pick-swatch":
        this._pickSwatch(action.closest(".overlay"), data.color);
        break;
      case "device-reset":
        this._resetLearning(this._deviceById(data.device));
        break;
    }
  }

  _deviceById(id) {
    return this._config.devices.find((d) => d.id === id);
  }

  _closeDialog(overlay) {
    if (overlay) overlay.remove();
  }

  _toast(message, isError = false) {
    const root = this.shadowRoot;
    if (!root) return;
    root.querySelectorAll(".toast").forEach((t) => t.remove());
    const toast = document.createElement("div");
    toast.className = `toast${isError ? " error" : ""}`;
    toast.textContent = message;
    root.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  /* ---- entity picker helper ---- */

  _entityPicker(device, key, domain, label, required, value) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const id = `f-${device}-${key}`;
    wrap.innerHTML = `
      <label for="${id}">${esc(label)}${required ? "" : ' <span class="optional">(optional)</span>'}</label>
      <div class="picker-host"></div>`;
    const host = wrap.querySelector(".picker-host");

    if (customElements.get("ha-entity-picker")) {
      const picker = document.createElement("ha-entity-picker");
      picker.hass = this._hass;
      picker.includeDomains = [domain];
      picker.value = value || "";
      picker.label = label;
      picker.addEventListener("value-changed", (ev) => {
        const input = host.querySelector("input") || picker;
        input.dataset.value = ev.detail.value || "";
        input.classList.remove("invalid");
      });
      host.appendChild(picker);
      const input = document.createElement("input");
      input.type = "hidden";
      input.dataset.value = value || "";
      host.appendChild(input);
      return { wrap, read: () => input.dataset.value || "", markInvalid: () => input.classList.add("invalid") };
    }

    const select = document.createElement("select");
    select.id = id;
    const none = document.createElement("option");
    none.value = "";
    none.textContent = required ? "Select an entity…" : "— not assigned —";
    select.appendChild(none);
    for (const entityId of Object.keys(this._hass.states).sort()) {
      if (!entityId.startsWith(`${domain}.`)) continue;
      const option = document.createElement("option");
      option.value = entityId;
      option.textContent = entityId;
      select.appendChild(option);
    }
    select.value = value || "";
    host.appendChild(select);
    return { wrap, read: () => select.value, markInvalid: () => select.classList.add("invalid") };
  }

  /* ---- device dialog ---- */

  _openDeviceDialog(device) {
    const root = this.shadowRoot;
    if (!root) return;
    const isEdit = Boolean(device);

    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-modal="true">
        <h3>${isEdit ? `Edit ${esc(device.name)}` : "Add device"}</h3>
        <div class="field">
          <label for="f-name">Device name</label>
          <input type="text" id="f-name" value="${isEdit ? esc(device.name) : ""}" placeholder="e.g. Washing Machine">
        </div>
        <div class="picker-fields"></div>
        <details class="advanced">
          <summary>Advanced settings</summary>
          <div class="field-row" style="margin-top: 10px;">
            <div class="field">
              <label for="f-threshold">Activity threshold</label>
              <input type="number" id="f-threshold" min="0" max="100000" step="0.01" value="${this._setting(device, "threshold")}">
            </div>
            <div class="field">
              <label for="f-confidence">Min. confidence</label>
              <input type="number" id="f-confidence" min="0.5" max="0.99" step="0.05" value="${this._setting(device, "min_confidence")}">
            </div>
            <div class="field">
              <label for="f-start">Cycle start delay (s)</label>
              <input type="number" id="f-start" min="0" max="300" step="1" value="${this._setting(device, "start_delay")}">
            </div>
            <div class="field">
              <label for="f-end">Cycle end delay (s)</label>
              <input type="number" id="f-end" min="10" max="600" step="1" value="${this._setting(device, "end_delay")}">
            </div>
          </div>
        </details>
        ${isEdit ? `
          <div class="danger-zone">
            <div>
              <div class="dz-title">Danger zone</div>
              <div class="dz-text muted">Reset programs and cycle history.</div>
            </div>
            <button class="btn outline" data-action="device-reset" data-device="${esc(device.id)}">Reset learning</button>
          </div>` : ""}
        <div class="actions">
          <button class="btn ghost" data-action="dialog-cancel">Cancel</button>
          <button class="btn primary" data-action="dialog-ok">${isEdit ? "Save" : "Create device"}</button>
        </div>
      </div>`;
    root.appendChild(overlay);

    const fieldsHost = overlay.querySelector(".picker-fields");
    const fields = {};
    fields.vibration = this._entityPicker(
      "new", "vibration", "binary_sensor", "Vibration sensor", true,
      isEdit ? device.entities.vibration : "");
    fields.x = this._entityPicker("new", "x", "sensor", "X movement sensor", false,
      isEdit ? device.entities.x : "");
    fields.y = this._entityPicker("new", "y", "sensor", "Y movement sensor", false,
      isEdit ? device.entities.y : "");
    fields.z = this._entityPicker("new", "z", "sensor", "Z movement sensor", false,
      isEdit ? device.entities.z : "");
    for (const field of Object.values(fields)) fieldsHost.appendChild(field.wrap);
    overlay._fields = fields;
    overlay._device = device;

    const nameInput = overlay.querySelector("#f-name");
    nameInput.focus();
  }

  _setting(device, key) {
    return device ? (device.settings[key] ?? 0.2) : { threshold: 0.2, min_confidence: 0.7, start_delay: 10, end_delay: 60 }[key];
  }

  _submitDialog(overlay) {
    const nameInput = overlay.querySelector("#f-name");
    const name = nameInput.value.trim();
    if (!name) {
      nameInput.classList.add("invalid");
      nameInput.focus();
      this._toast("A device name is required", true);
      return;
    }
    const fields = overlay._fields;
    const vibration = fields.vibration.read();
    if (!vibration) {
      fields.vibration.markInvalid();
      this._toast("Please assign a vibration sensor", true);
      return;
    }

    const settings = {
      threshold: parseFloat(overlay.querySelector("#f-threshold").value),
      min_confidence: parseFloat(overlay.querySelector("#f-confidence").value),
      start_delay: parseInt(overlay.querySelector("#f-start").value, 10),
      end_delay: parseInt(overlay.querySelector("#f-end").value, 10),
    };

    if (overlay._device) {
      this._mutate("device/update", {
        id: overlay._device.id,
        name,
        entities: {
          vibration,
          x: fields.x.read() || null,
          y: fields.y.read() || null,
          z: fields.z.read() || null,
        },
        settings,
      }, "Device updated").then((ok) => { if (ok) this._closeDialog(overlay); });
    } else {
      this._mutate("device/create", {
        name,
        entities: {
          vibration,
          x: fields.x.read() || null,
          y: fields.y.read() || null,
          z: fields.z.read() || null,
        },
        settings,
      }, "Device created").then((ok) => { if (ok) this._closeDialog(overlay); });
    }
  }

  _confirmDeleteDevice(device) {
    this._openConfirm({
      title: `Delete ${device.name}?`,
      text: `This removes the device, its entities and all learned programs and cycles. This cannot be undone.`,
      okLabel: "Delete",
      danger: true,
      onOk: () => this._mutate("device/remove", { id: device.id }, "Device deleted"),
    });
  }

  _confirmResetAll() {
    this._openConfirm({
      title: "Reset everything?",
      text: "All devices, programs and cycle history will be permanently removed.",
      okLabel: "Reset everything",
      danger: true,
      onOk: () => this._mutate("reset_all", {}, "All data removed"),
    });
  }

  _openConfirm({ title, text, okLabel, danger, onOk }) {
    const root = this.shadowRoot;
    if (!root) return;
    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.innerHTML = `
      <div class="dialog" role="alertdialog" aria-modal="true">
        <h3>${esc(title)}</h3>
        <p class="muted" style="margin: 0;">${esc(text)}</p>
        <div class="actions">
          <button class="btn ghost" data-action="dialog-cancel">Cancel</button>
          <button class="btn ${danger ? "danger" : "primary"}" data-action="confirm-ok">${esc(okLabel)}</button>
        </div>
      </div>`;
    overlay.addEventListener("click", (ev) => {
      const ok = ev.target.closest('[data-action="confirm-ok"]');
      if (ok) {
        this._closeDialog(overlay);
        onOk();
      }
    });
    root.appendChild(overlay);
  }

  _resetLearning(device) {
    this._openConfirm({
      title: `Reset learning for ${device.name}?`,
      text: "All programs and cycle history of this device will be removed.",
      okLabel: "Reset",
      danger: true,
      onOk: () => this._mutate("device/reset_learning", { id: device.id }, "Learning reset"),
    });
  }

  /* ---- cycle detail dialog ---- */

  _openCycleDialog(device, cycleId) {
    const root = this.shadowRoot;
    if (!root) return;
    const cycle = device.cycles.find((c) => c.id === cycleId);
    if (!cycle) return;
    const program = device.programs.find((p) => p.id === cycle.program_id);
    const stages = cycle.stages || [];
    const maxDur = Math.max(...stages.map((s) => (s.end || 0) - (s.start || 0)), 1);
    const mean = cycle.magnitude_mean != null ? Number(cycle.magnitude_mean).toFixed(3) : "—";
    const peak = cycle.magnitude_max != null ? Number(cycle.magnitude_max).toFixed(3) : "—";
    const active = cycle.active_ratio != null ? `${Math.round(cycle.active_ratio * 100)}%` : "—";

    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-modal="true">
        <h3>Cycle details</h3>
        <p class="muted" style="margin: 0 0 12px;">
          ${esc(device.name)} · ${fmtMinutes(cycle.duration)} · ${fmtClock(cycle.ended)}
        </p>
        ${program
          ? `<span class="chip" style="margin-bottom: 12px;"><span class="dot" style="background:${esc(program.color)}"></span>${esc(program.name)}</span>`
          : `<span class="chip unclassified" style="margin-bottom: 12px;">Not classified</span>`}
        <div class="section-label">Stages (${stages.length})</div>
        ${stages.length ? `
          <div>
            ${stages.map((s) => {
              const dur = Math.max(0, (s.end || 0) - (s.start || 0));
              const pct = Math.max(0, Math.min(100, (dur / maxDur) * 100));
              const color = STAGE_COLORS[s.id] || "#9e9e9e";
              return `
                <div class="list-row">
                  <span style="width:10px;height:10px;border-radius:50%;background:${esc(color)};flex:none;"></span>
                  <span class="name" style="min-width:70px;">${esc(STAGE_LABELS[s.id] || s.id)}</span>
                  <div style="flex:1;height:8px;border-radius:4px;background:var(--divider-color);overflow:hidden;">
                    <div style="width:${pct}%;height:100%;background:${esc(color)};"></div>
                  </div>
                  <span class="muted" style="min-width:64px;text-align:right;">${fmtMinutes(dur / 60)}</span>
                </div>`;
            }).join("")}
          </div>` : `
          <div class="muted" style="font-size:12px;">No stage data recorded for this cycle.</div>`}
        <div class="section-label">Vibration</div>
        <div class="mini-stats">
          <div class="mini-stat"><div class="val">${mean}</div><div class="lbl">Mean</div></div>
          <div class="mini-stat"><div class="val">${peak}</div><div class="lbl">Peak</div></div>
          <div class="mini-stat"><div class="val">${active}</div><div class="lbl">Active</div></div>
        </div>
        <div class="actions">
          <button class="btn ghost" data-action="dialog-cancel">Close</button>
        </div>
      </div>`;
    root.appendChild(overlay);
  }

  /* ---- label dialog ---- */

  _openLabelDialog(device, cycleId) {
    const root = this.shadowRoot;
    if (!root) return;
    const cycle = device.cycles.find((c) => c.id === cycleId);
    if (!cycle) return;

    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-modal="true">
        <h3>What program was this?</h3>
        <p class="muted" style="margin: 0 0 4px;">
          ${esc(device.name)} · ${fmtMinutes(cycle.duration)} cycle
          <span class="conf">${fmtClock(cycle.ended)}</span>
        </p>
        <div class="section-label" style="margin-top: 14px;">Label cycle as</div>
        <div class="chips" data-program-chips>
          ${device.programs.map((p) => `
            <button class="chip" data-action="pick-program" data-program="${esc(p.id)}">
              <span class="dot" style="background:${esc(p.color)}"></span>${esc(p.name)}
            </button>`).join("")}
          ${device.programs.length ? "" : '<div class="muted" style="font-size: 12px;">No programs yet — create one below.</div>'}
        </div>
        <button class="btn ghost" style="margin-top: 8px;" data-action="label-new">
          ${"＋"} Save as new program…
        </button>
        <div class="new-program" hidden>
          <div class="field" style="margin-top: 12px;">
            <label for="f-prog-name">Program name</label>
            <input type="text" id="f-prog-name" placeholder="e.g. Cotton 40°">
          </div>
          <div class="field">
            <label>Color</label>
            <div class="swatches">
              ${PALETTE.map((color, i) => `
                <button class="swatch${i === 0 ? " selected" : ""}" style="background:${color};"
                  data-action="pick-swatch" data-color="${color}" aria-label="Color ${i + 1}"></button>`).join("")}
            </div>
          </div>
        </div>
        <div class="actions">
          <button class="btn ghost" data-action="dialog-cancel">Cancel</button>
          <button class="btn primary" data-action="label-ok">Label</button>
        </div>
      </div>`;
    overlay._device = device;
    overlay._cycleId = cycleId;
    overlay._selectedProgram = null;
    root.appendChild(overlay);
  }

  _toggleNewProgram(overlay) {
    const panel = overlay.querySelector(".new-program");
    panel.hidden = !panel.hidden;
    if (!panel.hidden) overlay.querySelector("#f-prog-name").focus();
  }

  _pickProgram(overlay, programId) {
    overlay._selectedProgram = programId;
    overlay.querySelectorAll("[data-program-chips] .chip").forEach((chip) => {
      chip.style.outline = chip.dataset.program === programId ? "2px solid var(--primary-color)" : "";
    });
  }

  _pickSwatch(overlay, color) {
    overlay.querySelectorAll(".swatch").forEach((swatch) => {
      swatch.classList.toggle("selected", swatch.dataset.color === color);
    });
    overlay._selectedColor = color;
  }

  async _submitLabel(overlay) {
    const device = overlay._device;
    const newPanel = overlay.querySelector(".new-program");
    const isNew = !newPanel.hidden;
    const name = isNew ? overlay.querySelector("#f-prog-name").value.trim() : "";

    if (isNew && !name) {
      overlay.querySelector("#f-prog-name").classList.add("invalid");
      overlay.querySelector("#f-prog-name").focus();
      this._toast("A program name is required", true);
      return;
    }

    const payload = { id: device.id, cycle_id: overlay._cycleId };
    if (isNew) {
      payload.new_program_name = name;
      payload.new_program_color = overlay._selectedColor || PALETTE[0];
    } else {
      payload.program_id = overlay._selectedProgram;
    }
    if (!payload.program_id && !isNew && !overlay._selectedProgram) {
      this._toast("Pick a program first", true);
      return;
    }

    const ok = await this._mutate(
      "device/label_cycle", payload,
      isNew ? `Program "${name}" created` : "Cycle labeled");
    if (ok) this._closeDialog(overlay);
  }
}

customElements.define("appliance-vibration-panel", ApplianceVibrationPanel);
