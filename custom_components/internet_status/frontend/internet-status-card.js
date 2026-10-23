/*
 * Internet Status card: internet, DNS and public IP at a glance, with Home
 * Assistant's own history graph of the ping times. Served and registered by
 * the Internet Status integration; finds the integration's entities itself.
 */
const VERSION = "1.1.7";
const DOMAIN = "internet_status";
const CARD_TYPE = "internet-status-card";
const EDITOR_TYPE = "internet-status-card-editor";

const TEXT = {
  en: {
    name: "Internet Status",
    description: "Internet, DNS and public IP at a glance, with the ping times of the last day.",
    internet: "Internet",
    dns: "DNS",
    public_ip: "Public IP",
    online: "Online",
    offline: "Offline",
    unknown: "Unknown",
    ok: "OK",
    no_answer: "No answer",
    loss: "loss",
    via: "via",
    ping: "Ping",
    not_set_up: "Set up the Internet Status integration first (Settings, Devices & services).",
    status_ok: "Internet OK",
    status_offline: "No internet",
    status_dns: "DNS not working",
    status_unknown: "Status unknown",
    title: "Title (optional)",
    device_id: "Internet Status device",
    show_details: "Show internet, DNS and public IP",
    show_graph: "Show the ping graph",
    hours_to_show: "Hours in the graph",
    tap_action: "Tap action (empty: open the details)",
  },
  nl: {
    name: "Internet Status",
    description: "Internet, DNS en publiek IP in één oogopslag, met de pingtijden van het afgelopen etmaal.",
    internet: "Internet",
    dns: "DNS",
    public_ip: "Publiek IP",
    online: "Online",
    offline: "Offline",
    unknown: "Onbekend",
    ok: "OK",
    no_answer: "Geen antwoord",
    loss: "verlies",
    via: "via",
    ping: "Ping",
    not_set_up: "Stel eerst de integratie Internet Status in (Instellingen, Apparaten & diensten).",
    status_ok: "Internet werkt",
    status_offline: "Geen internet",
    status_dns: "DNS werkt niet",
    status_unknown: "Status onbekend",
    title: "Titel (optioneel)",
    device_id: "Internet Status-apparaat",
    show_details: "Internet, DNS en publiek IP tonen",
    show_graph: "Pinggrafiek tonen",
    hours_to_show: "Uren in de grafiek",
    tap_action: "Tikactie (leeg: details openen)",
  },
};

const text = (hass, key) => {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return (TEXT[lang] || TEXT.en)[key] ?? TEXT.en[key];
};

const ROWS = [
  { key: "internet", entity: "online", icon: "mdi:web", iconOff: "mdi:web-off" },
  { key: "dns", entity: "dns", icon: "mdi:dns", iconOff: "mdi:dns-outline" },
  { key: "public_ip", entity: "public_ip", icon: "mdi:ip-network", iconOff: "mdi:ip-network" },
];

const usable = (stateObj) => stateObj && !["unavailable", "unknown"].includes(stateObj.state);
const number = (stateObj) => (usable(stateObj) && !isNaN(Number(stateObj.state)) ? Number(stateObj.state) : null);

class InternetStatusCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig() {
    return { show_details: true, show_graph: true, hours_to_show: 24 };
  }

  setConfig(config) {
    this._config = { show_details: true, show_graph: true, hours_to_show: 24, ...config };
    this._graphKey = undefined;
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    if (!this._config) return 7;
    return 1 + (this._config.show_details === false ? 0 : 3) + (this._config.show_graph === false ? 0 : 4);
  }

  getGridOptions() {
    // "full": the whole width of its section, also of a wide (multi-column) section.
    return { columns: "full", min_columns: 6, rows: "auto" };
  }

  /** The integration's entities by translation key, from the chosen (or the first) device. */
  _entities() {
    const found = {};
    const device = this._config.device_id;
    for (const ent of Object.values(this._hass.entities || {})) {
      if (ent.platform !== DOMAIN || !ent.translation_key) continue;
      if (device && ent.device_id !== device) continue;
      if (!device && found._device && ent.device_id !== found._device) continue;
      found._device = ent.device_id;
      found[ent.translation_key] = ent.entity_id;
    }
    return found;
  }

  _build() {
    const root = this.shadowRoot || this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .header { padding: 12px 16px 0; font-size: var(--ha-card-header-font-size, 20px); line-height: 32px; }
        .header:empty { display: none; }
        .status { display: flex; align-items: center; gap: 10px; margin: 12px; padding: 10px 14px;
          border-radius: var(--ha-card-border-radius, 12px); background: var(--status-color); color: white; cursor: pointer; }
        .status ha-icon { --mdc-icon-size: 26px; }
        .status-text { flex: 1; font-size: 18px; font-weight: 500; line-height: 24px; }
        .status-detail { font-size: 14px; opacity: 0.9; white-space: nowrap; }
        .rows { padding: 0 0 8px; }
        .row { display: flex; align-items: center; gap: 12px; padding: 6px 16px; cursor: pointer; }
        .row:focus-visible { outline: 2px solid var(--primary-color); outline-offset: -2px; }
        [hidden] { display: none !important; }
        .icon { position: relative; flex: none; width: 36px; height: 36px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center; color: var(--row-color); }
        .icon::before { content: ""; position: absolute; inset: 0; border-radius: 50%;
          background: var(--row-color); opacity: 0.2; }
        ha-icon { position: relative; --mdc-icon-size: 22px; }
        .info { min-width: 0; flex: 1; }
        .primary { font-weight: 500; font-size: 14px; line-height: 20px; color: var(--primary-text-color); }
        .secondary { font-size: 12px; line-height: 16px; color: var(--secondary-text-color);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .empty { padding: 16px; color: var(--secondary-text-color); }
        .graph { --ha-card-border-width: 0; --ha-card-box-shadow: none; --ha-card-background: transparent;
          border-top: 1px solid var(--divider-color); }
        .graph:empty { display: none; }
      </style>
      <ha-card>
        <div class="header"></div>
        <div class="status" tabindex="0" role="button">
          <ha-icon></ha-icon><div class="status-text"></div><div class="status-detail"></div>
        </div>
        <div class="rows">
          ${ROWS.map(
            (r) => `<div class="row" data-key="${r.key}" tabindex="0" role="button">
              <div class="icon"><ha-icon></ha-icon></div>
              <div class="info"><div class="primary"></div><div class="secondary"></div></div>
            </div>`
          ).join("")}
        </div>
        <div class="empty" hidden></div>
        <div class="graph"></div>
      </ha-card>`;
    root.querySelectorAll(".row, .status").forEach((row) => {
      const open = () => {
        const entityId = row.dataset.entityId;
        const tapAction = this._config.tap_action;
        if (tapAction) {
          // Home Assistant's own action handling: navigate, url, perform-action, more-info, none, ...
          const config = { entity: entityId || undefined, tap_action: tapAction };
          this.dispatchEvent(new CustomEvent("hass-action", { detail: { config, action: "tap" }, bubbles: true, composed: true }));
          return;
        }
        if (!entityId) return;
        this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
      };
      row.addEventListener("click", open);
      row.addEventListener("keydown", (ev) => (ev.key === "Enter" || ev.key === " ") && open());
    });
    this._built = true;
  }

  _update() {
    if (!this._config || !this._hass) return;
    if (!this._built) this._build();
    const hass = this._hass;
    const root = this.shadowRoot;
    const ids = this._entities();
    const st = (key) => (ids[key] ? hass.states[ids[key]] : undefined);
    root.querySelector(".header").textContent = this._config.title || "";
    const empty = root.querySelector(".empty");
    empty.hidden = Boolean(ids._device);
    empty.textContent = text(hass, "not_set_up");

    const online = st("online");
    const ping = number(st("ping"));
    const loss = number(st("packet_loss"));
    const dns = st("dns");
    const dnsTime = number(st("dns_response_time"));
    const ip = st("public_ip");
    const values = {
      internet: {
        good: usable(online) ? online.state === "on" : null,
        detail: !usable(online)
          ? text(hass, "unknown")
          : online.state === "on"
            ? [text(hass, "online"), ping !== null && `${Math.round(ping)} ms`, loss && `${Math.round(loss)}% ${text(hass, "loss")}`]
                .filter(Boolean).join(" · ")
            : text(hass, "offline"),
      },
      dns: {
        good: usable(dns) ? dns.state === "on" : null,
        detail: !usable(dns)
          ? text(hass, "unknown")
          : [
              dns.state === "on" ? text(hass, "ok") : dns.attributes.error || text(hass, "no_answer"),
              dns.state === "on" && dnsTime !== null && `${Math.round(dnsTime)} ms`,
              dns.attributes.server && `${text(hass, "via")} ${dns.attributes.server}`,
            ].filter(Boolean).join(" · "),
      },
      public_ip: {
        good: usable(ip) ? true : ip ? false : null,
        detail: usable(ip) ? ip.state : text(hass, "unknown"),
      },
    };
    for (const r of ROWS) {
      const row = root.querySelector(`.row[data-key="${r.key}"]`);
      const entityId = ids[r.entity];
      row.hidden = !entityId || this._config.show_details === false;
      if (row.hidden) continue;
      const v = values[r.key];
      row.dataset.entityId = entityId;
      row.style.setProperty(
        "--row-color",
        v.good === null ? "var(--disabled-color)" : v.good ? "var(--success-color, #43a047)" : "var(--error-color, #db4437)"
      );
      row.querySelector("ha-icon").icon = v.good === false ? r.iconOff : r.icon;
      row.querySelector(".primary").textContent = text(hass, r.key);
      row.querySelector(".secondary").textContent = v.detail;
    }
    root.querySelector(".rows").hidden = this._config.show_details === false;

    // The quick answer: green when the internet works, red when it does not.
    // Public IP does not count: a slow IP service does not mean the internet is down.
    const dnsGood = values.dns.good;
    const netGood = ids.online ? values.internet.good : dnsGood; // no ping possible: DNS decides
    let status = "status_unknown", color = "var(--disabled-color, #9e9e9e)", icon = "mdi:help-circle", target = ids.online || ids.dns;
    let detail = "";
    if (netGood === false) {
      [status, color, icon] = ["status_offline", "var(--error-color, #db4437)", "mdi:web-off"];
    } else if (dnsGood === false) {
      [status, color, icon, target] = ["status_dns", "var(--error-color, #db4437)", "mdi:dns-outline", ids.dns];
    } else if (netGood && dnsGood) {
      [status, color, icon] = ["status_ok", "var(--success-color, #43a047)", "mdi:check-circle"];
      detail = ping !== null ? `${Math.round(ping)} ms` : "";
    }
    const bar = root.querySelector(".status");
    bar.hidden = !ids._device;
    bar.style.setProperty("--status-color", color);
    bar.dataset.entityId = target || "";
    bar.querySelector("ha-icon").icon = icon;
    bar.querySelector(".status-text").textContent = text(hass, status);
    bar.querySelector(".status-detail").textContent = detail;
    this._updateGraph(ids.ping);
  }

  async _updateGraph(ping) {
    const key = this._config.show_graph !== false && ping ? `${ping}|${this._config.hours_to_show}` : null;
    if (key === this._graphKey) {
      if (this._graph) this._graph.hass = this._hass;
      return;
    }
    this._graphKey = key;
    const holder = this.shadowRoot.querySelector(".graph");
    holder.innerHTML = "";
    this._graph = null;
    if (!key || !window.loadCardHelpers) return;
    const helpers = await window.loadCardHelpers();
    if (this._graphKey !== key) return; // the config changed while loading
    const graph = await helpers.createCardElement({
      type: "history-graph",
      entities: [{ entity: ping, name: text(this._hass, "ping") }],
      hours_to_show: Number(this._config.hours_to_show) || 24,
    });
    graph.hass = this._hass;
    holder.appendChild(graph);
    this._graph = graph;
  }
}

class InternetStatusCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => text(this._hass, schema.name);
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        for (const key of ["title", "device_id", "tap_action"]) if (!config[key]) delete config[key];
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = [
      { name: "title", selector: { text: {} } },
      { name: "device_id", selector: { device: { integration: DOMAIN } } },
      { name: "show_details", selector: { boolean: {} } },
      { name: "show_graph", selector: { boolean: {} } },
      { name: "hours_to_show", selector: { number: { min: 1, max: 168, mode: "box", unit_of_measurement: "h" } } },
      { name: "tap_action", selector: { ui_action: {} } },
    ];
    this._form.data = { show_details: true, show_graph: true, hours_to_show: 24, ...this._config };
  }
}

const register = () => {
  if (customElements.get(CARD_TYPE)) return;
  customElements.define(CARD_TYPE, InternetStatusCard);
  customElements.define(EDITOR_TYPE, InternetStatusCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: text(undefined, "name"),
    description: text(undefined, "description"),
    preview: true,
    documentationURL: "https://github.com/milamaja/ha-internet-status",
  });
  console.info(
    `%c INTERNET-STATUS-CARD %c ${VERSION} `,
    "color: white; background: #43a047; font-weight: 700;",
    "color: #43a047; background: white; font-weight: 700;"
  );
};

// Home Assistant replaces the browser's custom element registry while it
// starts. A card defined before that lands in the old registry, where
// dashboards cannot find it ("Custom element doesn't exist"). This file can
// load before Home Assistant has started, so register only once Home
// Assistant's own app element is defined, which happens after the swap.
if (customElements.get("home-assistant")) {
  register();
} else {
  customElements.whenDefined("home-assistant").then(register);
}
