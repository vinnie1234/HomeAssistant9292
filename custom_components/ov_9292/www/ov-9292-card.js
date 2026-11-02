/*
 * 9292 OV card
 *
 * Public transport like 9292.nl: per route the next departure with delay, arrival, travel time and a
 * strip of the legs (walk, bus, train ...) with their line numbers, the upcoming journeys, and a map
 * with the start and end of the route.
 *
 *   type: custom:ov-9292-card
 *   show_map: true         # map next to / under the list
 *   show_legs: true        # the strip with walk / bus / train and line numbers
 *   show_upcoming: true    # list of the following journeys
 *   max_upcoming: 3        # how many following journeys
 *   show_person: true      # name and picture of the person linked to the route
 *   show_price: false      # price of the journey, when 9292 gives one
 *   person: person.vincent # only routes of this person
 *   my_routes_only: false  # only routes of the person linked to the logged-in user
 *   height: 520            # card height in px on wide screens
 *
 * Data comes from the 9292 OV integration over a websocket subscription.
 */

const BASE = "/ov_9292/";
const NETHERLANDS = [[50.75, 3.3], [53.55, 7.25]];
const WIDE_BREAKPOINT = 860;

const MODES = {
  Walking: { icon: "mdi:walk", color: "#78909c", label: "Lopen" },
  Bus: { icon: "mdi:bus", color: "#1976d2", label: "Bus" },
  FastTrain: { icon: "mdi:train", color: "#1565c0", label: "Sneltrein" },
  SlowTrain: { icon: "mdi:train", color: "#1565c0", label: "Stoptrein" },
  Train: { icon: "mdi:train", color: "#1565c0", label: "Trein" },
  Tram: { icon: "mdi:tram", color: "#7b1fa2", label: "Tram" },
  Subway: { icon: "mdi:subway-variant", color: "#00897b", label: "Metro" },
  Ferry: { icon: "mdi:ferry", color: "#0277bd", label: "Veer" },
};
const FALLBACK_MODE = { icon: "mdi:transit-connection-variant", color: "#546e7a", label: "OV" };
const modeOf = (name) => MODES[name] || FALLBACK_MODE;

const STYLE = `
  :host { display: block; color: var(--primary-text-color); }
  * { box-sizing: border-box; }
  ha-card { overflow: hidden; }
  .wrap { display: grid; grid-template-columns: 1fr; position: relative; }
  .wrap.wide { grid-template-columns: minmax(340px, 480px) 1fr; height: var(--card-height, 520px); }
  .panel { display: flex; flex-direction: column; min-height: 0; min-width: 0; }
  .wrap:not(.wide) .panel { order: 2; }
  .wide .panel { border-right: 1px solid var(--divider-color); }
  .wrap.nomap { grid-template-columns: 1fr; height: auto; }
  .nomap .panel { border-right: 0; }
  .nomap .mapbox, .nomap .route-show { display: none; }
  .list { flex: 1; overflow-y: auto; min-height: 0; padding: 12px 0 4px; }
  .nomap .list { max-height: var(--card-height, 520px); }

  .route { margin: 0 12px 12px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--divider-color);
    background: var(--card-background-color); }
  .route.selected { border-color: var(--primary-color); box-shadow: 0 0 0 1px var(--primary-color) inset; }
  .route-head { display: flex; align-items: center; gap: 10px; }
  .route-name { flex: 1; min-width: 0; font-weight: 600; font-size: 15px; }
  .person { display: inline-flex; align-items: center; gap: 5px; margin-left: 10px; padding: 2px 9px 2px 3px; border-radius: 12px;
    background: var(--secondary-background-color); font-size: 12px; font-weight: 500; vertical-align: middle; --mdc-icon-size: 16px; }
  .person img { width: 18px; height: 18px; border-radius: 50%; object-fit: cover; }
  .person ha-icon { margin-left: 3px; }
  .route-show { flex: none; cursor: pointer; padding: 6px 12px; border-radius: 6px; font: inherit; font-size: 13px; font-weight: 600;
    background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); }
  .route-show:hover, .route.selected .route-show { border-color: var(--primary-color); color: var(--primary-color); }
  .places { margin-top: 2px; font-size: 12.5px; color: var(--secondary-text-color); }
  .stats { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; margin-top: 8px; }
  .time { font-size: 28px; font-weight: 700; line-height: 1.1; }
  .time s { font-size: 14px; font-weight: 400; color: var(--secondary-text-color); margin-left: 6px; }
  .delay-tag { padding: 2px 10px; border-radius: 12px; font-size: 12.5px; font-weight: 700; color: #fff; background: #2e7d32; }
  .delay-tag.warn { background: #f57c00; }
  .delay-tag.bad { background: #d32f2f; }
  .sub { margin-top: 4px; font-size: 13px; color: var(--secondary-text-color); display: flex; flex-wrap: wrap; gap: 2px 12px; }

  .legs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 2px; margin-top: 10px; }
  .leg { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px 3px 5px; border-radius: 12px; color: #fff;
    font-size: 12px; font-weight: 700; --mdc-icon-size: 16px; background: var(--leg-color); }
  .leg.walk { background: transparent; color: var(--secondary-text-color); padding: 3px 2px; }
  .leg.cancelled { text-decoration: line-through; opacity: .6; }
  .legs .sep { color: var(--secondary-text-color); --mdc-icon-size: 14px; opacity: .7; }

  .upcoming { margin-top: 10px; border-top: 1px solid var(--divider-color); }
  .upcoming-title { padding: 8px 0 2px; font-size: 12px; font-weight: 700; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .4px; }
  .next { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 12px; padding: 7px 8px; margin: 0 -8px; border-radius: 8px; cursor: pointer; font-size: 13.5px; }
  .next:hover { background: var(--secondary-background-color); }
  .next.active { background: color-mix(in srgb, var(--primary-color) 12%, transparent); font-weight: 600; }
  .next.cancelled { text-decoration: line-through; opacity: .6; }
  .next .muted { color: var(--secondary-text-color); font-weight: 400; }
  .next .mini { display: inline-flex; gap: 2px; --mdc-icon-size: 16px; color: var(--secondary-text-color); }

  .empty { padding: 28px 16px; text-align: center; color: var(--secondary-text-color); }
  .empty ha-icon { --mdc-icon-size: 40px; opacity: .6; display: block; margin: 0 auto 8px; }
  .unavailable { margin-top: 6px; font-size: 13px; color: var(--secondary-text-color); }

  .mapbox { position: relative; isolation: isolate; z-index: 0; height: 320px; background: var(--secondary-background-color); }
  .wide .mapbox { height: auto; }
  .map { position: absolute; inset: 0; }
  .map-actions { position: absolute; top: 10px; right: 10px; z-index: 500; display: flex; flex-direction: column; gap: 6px; }
  .map-actions button { cursor: pointer; display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: 18px;
    border: 0; font: inherit; font-size: 12.5px; font-weight: 600; color: #1b1b1b; background: rgba(255,255,255,.95);
    box-shadow: 0 1px 4px rgba(0,0,0,.35); --mdc-icon-size: 16px; }
  .map-actions button:hover { background: #fff; }
  .status { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center;
    padding: 20px; color: var(--secondary-text-color); background: var(--card-background-color); z-index: 600; }
  .status[hidden] { display: none; }
  .endpoint { width: 26px; height: 26px; border-radius: 50%; border: 2px solid #fff; color: #fff; font-weight: 700; font-size: 13px;
    display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 5px rgba(0,0,0,.5); }
  .home-dot { width: 16px; height: 16px; border-radius: 50%; background: #1976d2; border: 3px solid #fff; box-shadow: 0 0 0 4px rgba(25,118,210,.3); }
  .leaflet-container { font: inherit; background: var(--secondary-background-color); }
`;

let leafletPromise = null;
function loadLeaflet() {
  if (!leafletPromise) {
    leafletPromise = (async () => {
      const css = await (await fetch(`${BASE}leaflet.css`)).text();
      if (!window.L) {
        await new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = `${BASE}leaflet.js`;
          script.onload = resolve;
          script.onerror = () => reject(new Error("leaflet.js kon niet geladen worden"));
          document.head.appendChild(script);
        });
      }
      return { L: window.L, css };
    })().catch((err) => {
      leafletPromise = null;
      throw err;
    });
  }
  return leafletPromise;
}

const esc = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clock = (iso) => new Date(iso).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });

class Ov9292Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._routes = [];
    this._selectedRoute = null;
    this._picked = new Map(); // route id -> index in route.upcoming chosen by the user
  }

  setConfig(config) {
    this._config = {
      show_map: true,
      show_legs: true,
      show_upcoming: true,
      max_upcoming: 3,
      show_person: true,
      show_price: false,
      my_routes_only: false,
      height: 520,
      ...config,
    };
    this.style.setProperty("--card-height", `${this._config.height}px`);
    this._build();
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return { show_map: true };
  }

  static getConfigElement() {
    return document.createElement("ov-9292-card-editor");
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._subscribe();
    const dark = !!hass.themes?.darkMode;
    if (dark !== this._dark) {
      this._dark = dark;
      this._applyTiles();
    }
  }

  connectedCallback() {
    if (this._hass && !this._unsub) this._subscribe();
    this._resizeObserver = new ResizeObserver(() => {
      this._root?.classList.toggle("wide", this.clientWidth >= WIDE_BREAKPOINT);
      this._map?.invalidateSize();
    });
    this._resizeObserver.observe(this);
  }

  disconnectedCallback() {
    this._resizeObserver?.disconnect();
    this._unsubscribe();
  }

  /* ---------- data ---------- */

  async _subscribe() {
    if (this._subscribing || this._unsub || !this.isConnected) return;
    this._subscribing = true;
    try {
      this._unsub = await this._hass.connection.subscribeMessage((data) => this._onData(data), {
        type: "ov_9292/subscribe",
      });
    } catch (err) {
      this._showStatus("9292 OV is niet geladen. Is de integratie toegevoegd?");
    } finally {
      this._subscribing = false;
    }
  }

  _unsubscribe() {
    if (this._unsub) this._unsub();
    this._unsub = null;
  }

  _onData(data) {
    this._routes = data.routes || [];
    if (this._selectedRoute && !this._routes.some((r) => r.id === this._selectedRoute)) this._selectedRoute = null;
    this._showStatus(null);
    this._renderList();
    this._drawRoute();
  }

  /** Routes to show: all, those of one person, or those of the logged-in user's person. */
  _visibleRoutes() {
    let wanted = this._config.person || null;
    if (this._config.my_routes_only) {
      const userId = this._hass?.user?.id;
      const mine = Object.values(this._hass?.states || {}).find(
        (s) => s.entity_id.startsWith("person.") && userId && s.attributes.user_id === userId
      );
      wanted = mine ? mine.entity_id : "none";
    }
    return wanted ? this._routes.filter((route) => route.person === wanted) : this._routes;
  }

  /** The journey shown for a route: the one the user picked, else the first that is not cancelled. */
  _journey(route) {
    const picked = this._picked.get(route.id);
    if (picked != null && route.upcoming[picked]) return route.upcoming[picked];
    return route.next;
  }

  /* ---------- skeleton ---------- */

  _build() {
    // setConfig can run again on an existing card (editor, card picker): start clean
    this._map?.remove();
    this._map = null;
    this._tiles = this._labels = null;
    this._fitted = false;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="wrap">
          <div class="panel"><div class="list"></div></div>
          <div class="mapbox">
            <div class="map"></div>
            <div class="map-actions">
              <button class="fit"><ha-icon icon="mdi:vector-line"></ha-icon>Hele route</button>
              <button class="nl"><ha-icon icon="mdi:map-outline"></ha-icon>Heel Nederland</button>
            </div>
            <div class="status" hidden></div>
          </div>
        </div>
      </ha-card>`;
    const $ = (selector) => this.shadowRoot.querySelector(selector);
    this._root = $(".wrap");
    this._root.classList.toggle("nomap", !this._config.show_map);
    this._root.classList.toggle("wide", this.clientWidth >= WIDE_BREAKPOINT);

    $(".list").addEventListener("click", (event) => {
      const show = event.target.closest(".route-show");
      if (show) return this._toggleRoute(show.dataset.route);
      const next = event.target.closest(".next");
      if (next) {
        this._picked.set(next.dataset.route, Number(next.dataset.index));
        this._renderList();
      }
    });
    $(".fit").addEventListener("click", () => this._drawRoute({ fit: true }));
    $(".nl").addEventListener("click", () => this._map?.fitBounds(NETHERLANDS));

    this._renderList();
    if (this._config.show_map) this._initMap();
  }

  _showStatus(message) {
    const status = this.shadowRoot.querySelector(".status");
    if (!status) return;
    status.hidden = !message;
    status.textContent = message || "";
  }

  /* ---------- list ---------- */

  _personHtml(entityId) {
    const state = entityId && this._hass?.states[entityId];
    if (!state || !this._config.show_person) return "";
    const name = state.attributes.friendly_name || entityId;
    const picture = state.attributes.entity_picture;
    return `<span class="person">${picture ? `<img src="${esc(picture)}" alt="" />` : '<ha-icon icon="mdi:account"></ha-icon>'}${esc(name)}</span>`;
  }

  _legsHtml(journey) {
    const parts = journey.legs.map((leg) => {
      const mode = modeOf(leg.mode);
      const walking = leg.mode === "Walking";
      return `<span class="leg ${walking ? "walk" : ""} ${leg.cancelled ? "cancelled" : ""}" style="--leg-color:${mode.color}" title="${esc(mode.label)}">
        <ha-icon icon="${mode.icon}"></ha-icon>${!walking && leg.line ? esc(leg.line) : ""}</span>`;
    });
    return `<div class="legs">${parts.join('<ha-icon class="sep" icon="mdi:chevron-right"></ha-icon>')}</div>`;
  }

  _upcomingHtml(route, shown) {
    const rows = route.upcoming.slice(0, Number(this._config.max_upcoming) || 0);
    if (!rows.length) return "";
    return `<div class="upcoming"><div class="upcoming-title">Volgende reizen</div>${rows
      .map((journey, index) => {
        const mini = journey.legs
          .filter((leg) => leg.mode !== "Walking")
          .map((leg) => `<ha-icon icon="${modeOf(leg.mode).icon}"></ha-icon>`)
          .join("");
        return `<div class="next ${journey === shown ? "active" : ""} ${journey.cancelled ? "cancelled" : ""}" data-route="${esc(route.id)}" data-index="${index}">
          <span>${clock(journey.departure_actual)} → ${clock(journey.arrival)}</span>
          <span class="muted">${Math.round(journey.duration_min)} min</span>
          ${journey.delay_min >= 1 ? `<span class="muted">+${journey.delay_min}</span>` : ""}
          <span class="mini">${mini}</span></div>`;
      })
      .join("")}</div>`;
  }

  _routeHtml(route) {
    const head = `<div class="route-head"><span class="route-name">${esc(route.name)}${this._personHtml(route.person)}</span>
      <button class="route-show" data-route="${esc(route.id)}">${route.id === this._selectedRoute ? "Verberg kaart" : "Bekijk op kaart"}</button></div>
      <div class="places">${esc(route.from.label)} → ${esc(route.to.label)}</div>`;
    const journey = this._journey(route);
    const selected = route.id === this._selectedRoute;
    if (route.error || !journey) {
      return `<div class="route ${selected ? "selected" : ""}">${head}
        <div class="unavailable">Geen reis beschikbaar: controleer de plaatsen of probeer het later opnieuw.</div></div>`;
    }
    const level = journey.delay_min >= 10 ? "bad" : journey.delay_min >= 1 ? "warn" : "";
    const planned = journey.delay_min >= 1 ? `<s>${clock(journey.departure)}</s>` : "";
    return `<div class="route ${selected ? "selected" : ""}" data-route="${esc(route.id)}">${head}
      <div class="stats">
        <span class="time">${clock(journey.departure_actual)}${planned}</span>
        <span class="delay-tag ${level}">${journey.delay_min >= 1 ? `+ ${journey.delay_min} min` : "Op tijd"}</span>
        <span>Aankomst ${clock(journey.arrival)}</span>
      </div>
      <div class="sub">
        <span>${Math.round(journey.duration_min)} min</span>
        <span>${journey.transfers} ${journey.transfers === 1 ? "overstap" : "overstappen"}</span>
        ${this._config.show_price && journey.price != null ? `<span>€ ${journey.price.toFixed(2).replace(".", ",")}</span>` : ""}
        ${journey.detour ? "<span>Omleiding</span>" : ""}
        ${journey.cancelled ? "<span>Vervallen</span>" : ""}
      </div>
      ${this._config.show_legs ? this._legsHtml(journey) : ""}
      ${this._config.show_upcoming ? this._upcomingHtml(route, journey) : ""}
    </div>`;
  }

  _renderList() {
    const list = this.shadowRoot.querySelector(".list");
    if (!list) return;
    const routes = this._visibleRoutes();
    list.innerHTML = routes.length
      ? routes.map((route) => this._routeHtml(route)).join("")
      : `<div class="empty"><ha-icon icon="mdi:train-bus"></ha-icon>Geen routes. Voeg een route toe via de integratie-instellingen.</div>`;
  }

  _toggleRoute(id) {
    this._selectedRoute = this._selectedRoute === id ? null : id;
    this._renderList();
    this._drawRoute({ fit: true });
    if (this._selectedRoute && !this._root.classList.contains("wide")) {
      this.shadowRoot.querySelector(".mapbox").scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  /* ---------- map ---------- */

  async _initMap() {
    const container = this.shadowRoot.querySelector(".map");
    try {
      const { L, css } = await loadLeaflet();
      if (!container.isConnected) return; // card was rebuilt meanwhile
      this._L = L;
      const style = document.createElement("style");
      style.textContent = css;
      this.shadowRoot.appendChild(style);

      this._map = L.map(container, { zoomControl: true, attributionControl: true });
      this._map.attributionControl.setPrefix(false);
      this._routeLayer = L.layerGroup().addTo(this._map);
      this._applyTiles();
      // Fit once the container has a real size, otherwise Leaflet picks a wrong zoom
      this._mapObserver = new ResizeObserver(() => {
        this._map.invalidateSize();
        if (!this._fitted && container.clientWidth > 0) {
          this._fitted = true;
          this._fitAll();
        }
      });
      this._mapObserver.observe(container);
      this._drawRoute();
    } catch (err) {
      this._showStatus("De kaart kon niet geladen worden.");
    }
  }

  /** Start and end of every visible route that has a known position. */
  _points(routes) {
    return routes.flatMap((route) => [route.from.latlong, route.to.latlong]).filter(Boolean);
  }

  _fitAll() {
    if (!this._map || !this._L) return;
    const points = this._points(this._visibleRoutes());
    if (points.length) this._map.fitBounds(this._L.latLngBounds(points), { padding: [50, 50], maxZoom: 13 });
    else this._map.fitBounds(NETHERLANDS);
  }

  _applyTiles() {
    if (!this._map || !this._L) return;
    this._tiles?.remove();
    this._labels?.remove();
    // Esri basemaps need no API key and no referrer (OpenStreetMap blocks the Home Assistant app)
    const esri = (path) => `https://server.arcgisonline.com/ArcGIS/rest/services/${path}/MapServer/tile/{z}/{y}/{x}`;
    const options = { maxZoom: 19, maxNativeZoom: this._dark ? 16 : 19, attribution: "Tiles © Esri" };
    this._tiles = this._L
      .tileLayer(esri(this._dark ? "Canvas/World_Dark_Gray_Base" : "World_Street_Map"), options)
      .addTo(this._map);
    this._tiles.bringToBack();
    if (this._dark) {
      this._labels = this._L
        .tileLayer(esri("Canvas/World_Dark_Gray_Reference"), { ...options, pane: "shadowPane" })
        .addTo(this._map);
    }
  }

  /** Start (A) and end (B) of the selected route, or of all visible routes when none is selected. */
  _drawRoute({ fit = false } = {}) {
    if (!this._map || !this._L) return;
    const L = this._L;
    this._routeLayer.clearLayers();
    const visible = this._visibleRoutes();
    const routes = this._selectedRoute ? visible.filter((r) => r.id === this._selectedRoute) : visible;

    const endpoint = (point, letter, color, label) =>
      L.marker(point, {
        icon: L.divIcon({ className: "", html: `<div class="endpoint" style="background:${color}">${letter}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }),
        keyboard: false,
        zIndexOffset: 500,
      })
        .bindTooltip(esc(label), { direction: "top", offset: [0, -12] })
        .addTo(this._routeLayer);

    for (const route of routes) {
      const { from, to } = route;
      if (from.latlong && to.latlong) {
        // 9292 gives no road geometry in the journey list: a dashed line shows the direction
        L.polyline([from.latlong, to.latlong], { color: "#1976d2", weight: 4, opacity: 0.8, dashArray: "2 10", lineCap: "round", interactive: false }).addTo(this._routeLayer);
      }
      if (from.latlong) endpoint(from.latlong, "A", "#2e7d32", from.label);
      if (to.latlong) endpoint(to.latlong, "B", "#c62828", to.label);
    }
    if (fit) {
      const points = this._points(routes);
      if (points.length) this._map.flyToBounds(L.latLngBounds(points), { padding: [60, 60], maxZoom: 13, duration: 0.7 });
    }
  }
}

const EDITOR_SCHEMA = [
  { name: "show_map", selector: { boolean: {} } },
  { name: "show_legs", selector: { boolean: {} } },
  { name: "show_upcoming", selector: { boolean: {} } },
  { name: "max_upcoming", selector: { number: { min: 1, max: 5, step: 1, mode: "slider" } } },
  { name: "show_person", selector: { boolean: {} } },
  { name: "show_price", selector: { boolean: {} } },
  { name: "my_routes_only", selector: { boolean: {} } },
  { name: "person", selector: { entity: { domain: "person" } } },
  { name: "height", selector: { number: { min: 300, max: 1400, step: 10, mode: "slider", unit_of_measurement: "px" } } },
];
const EDITOR_LABELS = {
  show_map: "Kaart tonen (uit = alleen de lijst)",
  show_legs: "Stappen van de reis tonen (lopen, bus, trein en lijnnummers)",
  show_upcoming: "Volgende reizen tonen",
  max_upcoming: "Aantal volgende reizen",
  show_person: "Persoon bij de route tonen",
  show_price: "Prijs tonen",
  my_routes_only: "Alleen mijn routes (de persoon die bij jouw gebruiker hoort)",
  person: "Alleen routes van deze persoon (leeg = alle routes)",
  height: "Hoogte van de kaart op brede schermen",
};
const EDITOR_DEFAULTS = {
  show_map: true,
  show_legs: true,
  show_upcoming: true,
  max_upcoming: 3,
  show_person: true,
  show_price: false,
  my_routes_only: false,
  height: 520,
};

class Ov9292CardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    // Home Assistant hands back what we just emitted: keep the form as it is then, otherwise
    // clearing a field (to type a new number) would snap back to the default straight away.
    if (JSON.stringify(config) !== this._emitted) this._data = { ...EDITOR_DEFAULTS, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  _render() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = EDITOR_SCHEMA;
      this._form.computeLabel = (schema) => EDITOR_LABELS[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (event) => {
        this._data = event.detail.value;
        this._emitted = JSON.stringify(this._data);
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._data }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._data;
  }
}

customElements.define("ov-9292-card", Ov9292Card);
customElements.define("ov-9292-card-editor", Ov9292CardEditor);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "ov-9292-card",
  name: "9292 OV",
  description: "Eerstvolgende reizen met het openbaar vervoer per route, met vertraging, stappen en een kaart.",
  preview: false,
  documentationURL: "https://github.com/vinnie1234/HomeAssistant9292",
});
