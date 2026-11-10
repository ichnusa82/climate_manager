"use strict";
/*
 * Climate Manager Card
 * Card Lovelace per le entità climate di Climate Manager (e qualsiasi climate di HA).
 *
 * Esempio:
 *   type: custom:climate-manager-card
 *   entity: climate.salone
 *   name: Salone              # opzionale
 *   show_modes: true          # opzionale (default true)
 *   show_presets: true        # opzionale (default true)
 *   entities:                 # opzionale: riga di stato
 *     - entity: switch.caldaia
 *       name: Caldaia
 *       icon: mdi:water-boiler
 *     - switch.pompa
 *     - binary_sensor.finestra_salone
 */
const CARD_VERSION = "1.1.2";
const I18N = {
    it: {
        heating: "Riscalda",
        cooling: "Raffresca",
        idle: "In attesa",
        off: "Spento",
        drying: "Deumidifica",
        fan: "Ventila",
        preheating: "Preriscalda",
        defrosting: "Sbrina",
        current: "Attuale",
        humidity: "Umidità",
        target: "Obiettivo",
        min: "Min",
        max: "Max",
        unavailable: "Non disponibile",
        modes: {
            off: "Spento",
            heat: "Caldo",
            cool: "Freddo",
            heat_cool: "Caldo/Freddo",
            auto: "Auto",
            dry: "Deumid.",
            fan_only: "Ventola",
        },
        presets: { none: "Nessuno", eco: "Eco", away: "Fuori casa", comfort: "Comfort", home: "Casa", sleep: "Notte", boost: "Boost", activity: "Attività" },
        states: { on: "Acceso", off: "Spento", open: "Aperta", closed: "Chiusa", unavailable: "N/D", unknown: "?" },
        editor: {
            entity: "Termostato",
            name: "Nome (opzionale)",
            show_modes: "Mostra modalità",
            show_presets: "Mostra preset",
            entities: "Entità di stato (caldaia, pompa, finestra...)",
        },
    },
    en: {
        heating: "Heating",
        cooling: "Cooling",
        idle: "Idle",
        off: "Off",
        drying: "Drying",
        fan: "Fan",
        preheating: "Preheating",
        defrosting: "Defrosting",
        current: "Current",
        humidity: "Humidity",
        target: "Target",
        min: "Min",
        max: "Max",
        unavailable: "Unavailable",
        modes: { off: "Off", heat: "Heat", cool: "Cool", heat_cool: "Heat/Cool", auto: "Auto", dry: "Dry", fan_only: "Fan" },
        presets: { none: "None", eco: "Eco", away: "Away", comfort: "Comfort", home: "Home", sleep: "Sleep", boost: "Boost", activity: "Activity" },
        states: { on: "On", off: "Off", open: "Open", closed: "Closed", unavailable: "N/A", unknown: "?" },
        editor: {
            entity: "Thermostat",
            name: "Name (optional)",
            show_modes: "Show modes",
            show_presets: "Show presets",
            entities: "Status entities (boiler, pump, window...)",
        },
    },
};
const MODE_ICONS = {
    off: "mdi:power",
    heat: "mdi:fire",
    cool: "mdi:snowflake",
    heat_cool: "mdi:sun-snowflake-variant",
    auto: "mdi:thermostat-auto",
    dry: "mdi:water-percent",
    fan_only: "mdi:fan",
};
const PRESET_ICONS = {
    eco: "mdi:leaf",
    away: "mdi:account-arrow-right",
    comfort: "mdi:sofa",
    home: "mdi:home",
    sleep: "mdi:weather-night",
    boost: "mdi:rocket-launch",
    activity: "mdi:motion-sensor",
};
// Colori per stato: [colore principale, colore chiaro per sfumatura]
const COLORS = {
    heating: ["#ff7a2f", "#ffb347"],
    heat: ["#ff7a2f", "#ffb347"],
    cooling: ["#2f9bff", "#7fd3ff"],
    cool: ["#2f9bff", "#7fd3ff"],
    heat_cool: ["#9a6bff", "#d38bff"],
    auto: ["#2fbf8f", "#7fe3c0"],
    dry: ["#e0b400", "#ffe066"],
    fan_only: ["#2fbfbf", "#8fe8e8"],
    off: ["#8a8f98", "#b5b9c0"],
};
const ON_STATES = ["on", "open", "heat", "cool", "heating", "cooling", "home", "detected", "true"];
// Geometria del quadrante (gradi, 0 = destra, senso orario in SVG)
const ARC_START = 135;
const ARC_SWEEP = 270;
const CX = 100;
const CY = 100;
const R = 82;
function polar(angle, r = R) {
    const a = (angle * Math.PI) / 180;
    return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}
function arcPath(a0, a1, r = R) {
    if (a1 - a0 < 0.01)
        a1 = a0 + 0.01;
    const [x0, y0] = polar(a0, r);
    const [x1, y1] = polar(a1, r);
    const large = a1 - a0 > 180 ? 1 : 0;
    return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}
function rgba(hex, al) {
    const h = String(hex).replace("#", "");
    if (h.length !== 6)
        return "rgba(128,128,128," + al + ")";
    return "rgba(" + parseInt(h.slice(0, 2), 16) + "," + parseInt(h.slice(2, 4), 16) + "," + parseInt(h.slice(4, 6), 16) + "," + al + ")";
}
function fmtState(hass, so, value) {
    // Usa le traduzioni di HA (es. "heating" -> "Riscaldamento") se disponibili
    try {
        if (hass && so && typeof hass.formatEntityState === "function") {
            return value === undefined ? hass.formatEntityState(so) : hass.formatEntityState(so, value);
        }
    }
    catch (e) { }
    return value === undefined ? (so ? so.state : "") : value;
}
function esc(s) {
    return String(s !== null && s !== void 0 ? s : "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
class ClimateManagerCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._pending = null; // { temperature } oppure { target_temp_low, target_temp_high }
        this._debounce = null;
        this._dragging = null;
        this._lastStateObj = null;
    }
    static getConfigElement() {
        return document.createElement("climate-manager-card-editor");
    }
    static getStubConfig(hass) {
        const ent = Object.keys((hass === null || hass === void 0 ? void 0 : hass.states) || {}).find((e) => e.startsWith("climate."));
        return { entity: ent || "climate.esempio", show_modes: true, show_presets: true };
    }
    setConfig(config) {
        if (!config || !config.entity || !String(config.entity).startsWith("climate.")) {
            throw new Error("Specifica un'entità climate (es. entity: climate.salone)");
        }
        this._config = Object.assign({ show_modes: true, show_presets: true }, config);
        this._lastStateObj = null;
        if (this._hass)
            this._render();
    }
    set hass(hass) {
        this._hass = hass;
        if (!this._config)
            return;
        const so = hass.states[this._config.entity];
        const extra = this._extraEntities().concat(this._selects()).map((e) => hass.states[e.entity]);
        const changed = so !== this._lastStateObj || extra.some((s, i) => s !== (this._lastExtra || [])[i]);
        if (!changed || this._dragging)
            return;
        this._lastStateObj = so;
        this._lastExtra = extra;
        // Se lo stato reale ha raggiunto il valore richiesto, azzera il pending
        if (this._pending && so && !this._debounce) {
            const a = so.attributes;
            const done = Object.entries(this._pending).every(([k, v]) => Number(a[k]) === v);
            if (done)
                this._pending = null;
        }
        this._render();
    }
    getCardSize() {
        return 6;
    }
    getGridOptions() {
        return { columns: 6, min_columns: 4, rows: "auto" };
    }
    get _t() {
        var _a, _b, _c;
        const lang = (((_b = (_a = this._hass) === null || _a === void 0 ? void 0 : _a.locale) === null || _b === void 0 ? void 0 : _b.language) || ((_c = this._hass) === null || _c === void 0 ? void 0 : _c.language) || "it").slice(0, 2);
        return I18N[lang] || I18N.en;
    }
    _selects() {
        return (this._config.selects || []).map((e) => (typeof e === "string" ? { entity: e } : e)).filter((e) => e && e.entity);
    }
    _extraEntities() {
        return (this._config.entities || []).map((e) => (typeof e === "string" ? { entity: e } : e)).filter((e) => e && e.entity);
    }
    _step(attrs) {
        return Number(this._config.step || attrs.target_temp_step || 0.5);
    }
    _fmt(v, step) {
        if (v == null || isNaN(v))
            return "--";
        const dec = step < 1 ? (String(step).split(".")[1] || "").length || 1 : 0;
        return Number(v).toFixed(dec);
    }
    _valueToAngle(v, min, max) {
        const f = Math.min(1, Math.max(0, (v - min) / (max - min)));
        return ARC_START + f * ARC_SWEEP;
    }
    _angleToValue(angle, min, max, step) {
        let a = angle - ARC_START;
        while (a < 0)
            a += 360;
        while (a >= 360)
            a -= 360;
        if (a > ARC_SWEEP)
            a = a - ARC_SWEEP < (360 - ARC_SWEEP) / 2 ? ARC_SWEEP : 0;
        const v = min + (a / ARC_SWEEP) * (max - min);
        return Math.min(max, Math.max(min, Math.round(v / step) * step));
    }
    _colorKey(so) {
        const action = so.attributes.hvac_action;
        if (so.state === "off")
            return "off";
        if (action && COLORS[action])
            return action;
        return COLORS[so.state] ? so.state : "heat";
    }
    _actionLabel(so) {
        const t = this._t;
        if (so.state === "off")
            return t.off;
        const a = so.attributes.hvac_action;
        if (!a)
            return t.modes[so.state] || so.state;
        return t[a] || a;
    }
    _render() {
        var _a, _b, _c, _d, _e;
        const hass = this._hass;
        const cfg = this._config;
        const so = hass.states[cfg.entity];
        const t = this._t;
        if (!so) {
            this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="warning">Entità non trovata: ${esc(cfg.entity)}</div></ha-card>`;
            return;
        }
        const a = so.attributes;
        const unavailable = so.state === "unavailable" || so.state === "unknown";
        const step = this._step(a);
        const min = Number((_a = a.min_temp) !== null && _a !== void 0 ? _a : 7);
        const max = Number((_b = a.max_temp) !== null && _b !== void 0 ? _b : 35);
        const isRange = a.temperature == null && a.target_temp_low != null && a.target_temp_high != null;
        const p = this._pending || {};
        const target = (_c = p.temperature) !== null && _c !== void 0 ? _c : (a.temperature != null ? Number(a.temperature) : null);
        const low = (_d = p.target_temp_low) !== null && _d !== void 0 ? _d : (a.target_temp_low != null ? Number(a.target_temp_low) : null);
        const high = (_e = p.target_temp_high) !== null && _e !== void 0 ? _e : (a.target_temp_high != null ? Number(a.target_temp_high) : null);
        const cur = a.current_temperature != null ? Number(a.current_temperature) : null;
        const ck = unavailable ? "off" : this._colorKey(so);
        const [c1, c2] = COLORS[ck];
        const off = so.state === "off" || unavailable;
        const active = ["heating", "cooling", "drying", "fan", "preheating"].includes(a.hvac_action);
        // --- Quadrante ---
        const end = ARC_START + ARC_SWEEP;
        let fill = "";
        let handles = "";
        if (!off) {
            if (isRange && low != null && high != null) {
                const al = this._valueToAngle(low, min, max);
                const ah = this._valueToAngle(high, min, max);
                fill = `<path class="fill" d="${arcPath(al, ah)}" stroke="url(#grad)"/>`;
                handles = [["target_temp_low", al], ["target_temp_high", ah]]
                    .map(([k, ang]) => {
                    const [x, y] = polar(ang);
                    return `<circle class="handle" data-key="${k}" cx="${x}" cy="${y}" r="9"/>`;
                })
                    .join("");
            }
            else if (target != null) {
                const at = this._valueToAngle(target, min, max);
                fill = `<path class="fill" d="${arcPath(ARC_START, at)}" stroke="url(#grad)"/>`;
                const [x, y] = polar(at);
                handles = `<circle class="handle" data-key="temperature" cx="${x}" cy="${y}" r="9"/>`;
            }
        }
        // tacche
        let ticks = "";
        const nTicks = 54;
        for (let i = 0; i <= nTicks; i++) {
            const ang = ARC_START + (i / nTicks) * ARC_SWEEP;
            const [x0, y0] = polar(ang, R - 15);
            const [x1, y1] = polar(ang, R - (i % 9 === 0 ? 21 : 18));
            ticks += `<line class="tick${i % 9 === 0 ? " major" : ""}" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}"/>`;
        }
        let curMarker = "";
        if (cur != null) {
            const ac = this._valueToAngle(cur, min, max);
            const [x0, y0] = polar(ac, R - 12);
            const [x1, y1] = polar(ac, R - 24);
            curMarker = `<line class="cur-marker" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}"/>`;
        }
        const [sx, sy] = polar(ARC_START, R + 14);
        const [ex, ey] = polar(end, R + 14);
        const centerValue = off
            ? `<div class="big off-label"><ha-icon icon="${unavailable ? "mdi:lan-disconnect" : "mdi:power"}"></ha-icon></div>`
            : isRange
                ? `<div class="big range">${this._fmt(low, step)}<span class="sep">–</span>${this._fmt(high, step)}<span class="unit">°</span></div>`
                : `<div class="big">${this._fmt(target, step)}<span class="unit">°</span></div>`;
        const dial = `
      <div class="dial-wrap"><div class="dial-box">
        <svg class="dial" viewBox="0 0 200 200">
          <defs>
            <linearGradient id="grad" x1="0" y1="1" x2="1" y2="0">
              <stop offset="0%" stop-color="${c2}"/>
              <stop offset="100%" stop-color="${c1}"/>
            </linearGradient>
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>
          <path class="track" d="${arcPath(ARC_START, end)}"/>
          ${ticks}
          <g class="${active ? "glow" : ""}">${fill}</g>
          ${curMarker}
          ${handles}
          <path class="hit" d="${arcPath(ARC_START, end)}"/>
          <text class="scale" x="${sx}" y="${sy}" text-anchor="middle">${this._fmt(min, 1)}°</text>
          <text class="scale" x="${ex}" y="${ey}" text-anchor="middle">${this._fmt(max, 1)}°</text>
        </svg>
        <div class="center">
          <div class="action ${active ? "on" : ""}" style="--c:${c1};--cp:${rgba(c1, 0.6)}">
            <span class="dot"></span>${esc(this._actionLabel(so))}
          </div>
          ${centerValue}
          <div class="current">
            <ha-icon icon="mdi:home-thermometer-outline"></ha-icon>${this._fmt(cur, 0.1)}°
            ${a.current_humidity != null ? `<span class="hum"><ha-icon icon="mdi:water-percent"></ha-icon>${Math.round(a.current_humidity)}%</span>` : ""}
          </div>
        </div>
      </div></div>`;
        // --- Pulsanti +/- ---
        let steppers = "";
        if (!off) {
            if (isRange) {
                steppers = `
          <div class="steppers two">
            ${this._stepper("target_temp_low", t.min, low, step)}
            ${this._stepper("target_temp_high", t.max, high, step)}
          </div>`;
            }
            else if (target != null) {
                steppers = `
          <div class="steppers">
            <button class="round" data-key="temperature" data-dir="-1" aria-label="-"><ha-icon icon="mdi:minus"></ha-icon></button>
            <button class="round" data-key="temperature" data-dir="1" aria-label="+"><ha-icon icon="mdi:plus"></ha-icon></button>
          </div>`;
            }
        }
        // --- Modalità ---
        let modes = "";
        if (cfg.show_modes && Array.isArray(a.hvac_modes) && a.hvac_modes.length) {
            modes = `<div class="modes">${a.hvac_modes
                .map((m) => {
                const [mc] = COLORS[m] || COLORS.heat;
                const sel = so.state === m;
                return `<button class="mode ${sel ? "sel" : ""}" data-mode="${esc(m)}" style="--c:${mc};--cs:${rgba(mc, 0.18)}" title="${esc(t.modes[m] || m)}">
              <ha-icon icon="${MODE_ICONS[m] || "mdi:thermostat"}"></ha-icon>
              <span>${esc(t.modes[m] || m)}</span>
            </button>`;
            })
                .join("")}</div>`;
        }
        // --- Selettori (select / input_select) ---
        const selects = this._selects()
            .map((sc) => {
            const ss = hass.states[sc.entity];
            if (!ss) return `<div class="section-title">${esc(sc.entity)}: ?</div>`;
            const opts = ss.attributes.options || [];
            const dis = ss.state === "unavailable" || ss.state === "unknown";
            const icons = sc.icons || {};
            const nm = sc.name || ss.attributes.friendly_name || sc.entity;
            const sub = sc.show_last_updated === false ? "" : `<span class="upd">${esc(relTime(ss.last_updated, (this._hass.locale && this._hass.locale.language) || this._hass.language || "it"))}</span>`;
            const btns = opts
                .map((o) => {
                const lbl = fmtState(this._hass, ss, o);
                const ic = icons[o] || icons[lbl] || optionIcon(o) || optionIcon(lbl);
                return `<button class="mode ${ss.state === o ? "sel" : ""}" data-select="${esc(sc.entity)}" data-opt="${esc(o)}" style="--c:${c1};--cs:${rgba(c1, 0.18)}" ${dis ? "disabled" : ""}>
                ${ic ? `<ha-icon icon="${esc(ic)}"></ha-icon>` : ""}<span>${esc(lbl)}</span>
              </button>`;
            })
                .join("");
            return `<div class="section-title sel-title"><span>${esc(nm)}</span>${sub}</div>
              <div class="modes sel-modes" style="margin-top:0">${btns}</div>`;
        })
            .join("");
        // --- Preset ---
        let presets = "";
        const presetList = (a.preset_modes || []).filter((x) => x && x !== "none");
        if (cfg.show_presets && presetList.length) {
            presets = `<div class="section-title">Preset</div><div class="presets">${presetList
                .map((pm) => {
                const sel = a.preset_mode === pm;
                const icon = PRESET_ICONS[String(pm).toLowerCase()];
                return `<button class="chip ${sel ? "sel" : ""}" data-preset="${esc(pm)}" style="--c:${c1}">
              ${icon ? `<ha-icon icon="${icon}"></ha-icon>` : ""}<span>${esc(t.presets[pm] || pm)}</span>
            </button>`;
            })
                .join("")}</div>`;
        }
        // --- Entità di stato ---
        let status = "";
        const extra = this._extraEntities();
        if (extra.length) {
            status = `<div class="status">${extra
                .map((e) => {
                var _a, _b, _c, _d;
                const s = hass.states[e.entity];
                const name = e.name || ((_a = s === null || s === void 0 ? void 0 : s.attributes) === null || _a === void 0 ? void 0 : _a.friendly_name) || e.entity;
                const st = s ? s.state : "unavailable";
                const on = ON_STATES.includes(st);
                const icon = e.icon || ((_b = s === null || s === void 0 ? void 0 : s.attributes) === null || _b === void 0 ? void 0 : _b.icon) || this._defaultIcon(e.entity, st);
                const isOpening = ["window", "door", "opening", "garage_door"].includes((_c = s === null || s === void 0 ? void 0 : s.attributes) === null || _c === void 0 ? void 0 : _c.device_class) || /finestr|window|porta|door/i.test(e.entity);
                const stKey = isOpening && st === "on" ? "open" : isOpening && st === "off" ? "closed" : st;
                const label = ((_d = s === null || s === void 0 ? void 0 : s.attributes) === null || _d === void 0 ? void 0 : _d.unit_of_measurement) ? `${st} ${s.attributes.unit_of_measurement}` : (isOpening ? t.states[stKey] : null) || (s ? fmtState(hass, s) : null) || t.states[stKey] || st;
                return `<div class="stat ${on ? "on" : ""}" data-entity="${esc(e.entity)}" style="--c:${on ? c1 : "var(--secondary-text-color)"};--cs:${on ? rgba(c1, 0.14) : "rgba(128,128,128,.14)"}">
              <div class="stat-icon"><ha-icon icon="${esc(icon)}"></ha-icon></div>
              <div class="stat-txt"><div class="stat-name">${esc(name)}</div><div class="stat-val">${esc(label)}</div></div>
            </div>`;
            })
                .join("")}</div>`;
        }
        const title = cfg.name || a.friendly_name || cfg.entity;
        this.shadowRoot.innerHTML = `
      ${this._styles()}
      <ha-card class="${off ? "is-off" : ""}" style="--c1:${c1};--c2:${c2};--c1s:${rgba(c1, 0.18)}">
        <div class="bg"></div>
        <div class="header">
          <div class="title">${esc(title)}</div>
          <button class="more" data-more="${esc(cfg.entity)}" aria-label="info"><ha-icon icon="mdi:dots-vertical"></ha-icon></button>
        </div>
        ${dial}
        ${steppers}
        ${modes}
        ${selects}
        ${presets}
        ${status}
      </ha-card>`;
        this._bind(min, max, step, isRange);
    }
    _stepper(key, label, value, step) {
        return `<div class="stepper">
        <button class="round small" data-key="${key}" data-dir="-1"><ha-icon icon="mdi:minus"></ha-icon></button>
        <div class="stepper-val"><span>${label}</span>${this._fmt(value, step)}°</div>
        <button class="round small" data-key="${key}" data-dir="1"><ha-icon icon="mdi:plus"></ha-icon></button>
      </div>`;
    }
    _defaultIcon(entity, st) {
        const d = entity.split(".")[0];
        if (/finestr|window/i.test(entity))
            return st === "on" || st === "open" ? "mdi:window-open-variant" : "mdi:window-closed-variant";
        if (/pomp|pump/i.test(entity))
            return "mdi:pump";
        if (/caldai|boiler/i.test(entity))
            return "mdi:water-boiler";
        if (/valv/i.test(entity))
            return "mdi:pipe-valve";
        if (d === "sensor")
            return "mdi:gauge";
        if (d === "binary_sensor")
            return "mdi:checkbox-blank-circle-outline";
        return "mdi:toggle-switch-variant";
    }
    _bind(min, max, step, isRange) {
        const root = this.shadowRoot;
        const so = this._hass.states[this._config.entity];
        const a = so.attributes;
        root.querySelectorAll("button[data-dir]").forEach((b) => b.addEventListener("click", () => {
            var _a, _b;
            const key = b.dataset.key;
            const cur = (_b = (_a = this._pending) === null || _a === void 0 ? void 0 : _a[key]) !== null && _b !== void 0 ? _b : Number(a[key]);
            let v = Math.round((cur + Number(b.dataset.dir) * step) / step) * step;
            v = Math.min(max, Math.max(min, Number(v.toFixed(2))));
            this._setPending(key, v, isRange);
        }));
        root.querySelectorAll("button[data-mode]").forEach((b) => b.addEventListener("click", () => this._call("set_hvac_mode", { hvac_mode: b.dataset.mode })));
        root.querySelectorAll("button[data-select]").forEach((b) => b.addEventListener("click", () => {
            const ent = b.dataset.select;
            const st = this._hass.states[ent];
            if (st && st.state === b.dataset.opt) return;
            this._hass.callService(ent.split(".")[0], "select_option", { entity_id: ent, option: b.dataset.opt });
        }));
        root.querySelectorAll("button[data-preset]").forEach((b) => b.addEventListener("click", () => this._call("set_preset_mode", { preset_mode: b.dataset.preset })));
        root.querySelectorAll("[data-more], .stat[data-entity]").forEach((el) => el.addEventListener("click", () => this._moreInfo(el.dataset.more || el.dataset.entity)));
        // Trascinamento sul quadrante
        const svg = root.querySelector("svg.dial");
        if (!svg || so.state === "off")
            return;
        const angleFromEvent = (ev) => {
            const r = svg.getBoundingClientRect();
            const x = ((ev.clientX - r.left) / r.width) * 200 - CX;
            const y = ((ev.clientY - r.top) / r.height) * 200 - CY;
            let ang = (Math.atan2(y, x) * 180) / Math.PI;
            if (ang < 0)
                ang += 360;
            return ang;
        };
        svg.addEventListener("pointerdown", (ev) => {
            var _a, _b, _c, _d;
            const target = ev.target;
            if (!target.classList.contains("handle") && !target.classList.contains("hit"))
                return;
            let key = target.dataset.key;
            if (!key) {
                if (isRange) {
                    const v = this._angleToValue(angleFromEvent(ev), min, max, step);
                    const lo = (_b = (_a = this._pending) === null || _a === void 0 ? void 0 : _a.target_temp_low) !== null && _b !== void 0 ? _b : Number(a.target_temp_low);
                    const hi = (_d = (_c = this._pending) === null || _c === void 0 ? void 0 : _c.target_temp_high) !== null && _d !== void 0 ? _d : Number(a.target_temp_high);
                    key = Math.abs(v - lo) <= Math.abs(v - hi) ? "target_temp_low" : "target_temp_high";
                }
                else
                    key = "temperature";
            }
            this._dragging = key;
            // Il quadrante viene ridisegnato a ogni movimento: misuriamo sempre l'svg corrente
            const move = (e) => {
                var _a;
                const cur = this.shadowRoot.querySelector("svg.dial") || svg;
                const r = cur.getBoundingClientRect();
                const x = ((e.clientX - r.left) / r.width) * 200 - CX;
                const y = ((e.clientY - r.top) / r.height) * 200 - CY;
                let ang = (Math.atan2(y, x) * 180) / Math.PI;
                if (ang < 0)
                    ang += 360;
                const v = this._angleToValue(ang, min, max, step);
                if (((_a = this._pending) === null || _a === void 0 ? void 0 : _a[key]) === Number(v.toFixed(2)))
                    return;
                this._pending = Object.assign(Object.assign({}, (this._pending || {})), { [key]: Number(v.toFixed(2)) });
                if (isRange)
                    this._fixRange(key, step);
                this._render();
            };
            const docMove = (e) => move(e);
            const docUp = () => {
                document.removeEventListener("pointermove", docMove);
                document.removeEventListener("pointerup", docUp);
                this._dragging = null;
                this._schedule(isRange);
            };
            document.addEventListener("pointermove", docMove);
            document.addEventListener("pointerup", docUp);
            move(ev);
            ev.preventDefault();
        });
    }
    _fixRange(key, step) {
        var _a, _b;
        const p = this._pending;
        const a = this._hass.states[this._config.entity].attributes;
        const lo = (_a = p.target_temp_low) !== null && _a !== void 0 ? _a : Number(a.target_temp_low);
        const hi = (_b = p.target_temp_high) !== null && _b !== void 0 ? _b : Number(a.target_temp_high);
        if (lo > hi - step) {
            if (key === "target_temp_low")
                p.target_temp_low = hi - step;
            else
                p.target_temp_high = lo + step;
        }
    }
    _setPending(key, v, isRange) {
        this._pending = Object.assign(Object.assign({}, (this._pending || {})), { [key]: v });
        if (isRange)
            this._fixRange(key, this._step(this._hass.states[this._config.entity].attributes));
        this._render();
        this._schedule(isRange);
    }
    _schedule(isRange) {
        clearTimeout(this._debounce);
        this._debounce = setTimeout(() => {
            var _a, _b;
            this._debounce = null;
            const so = this._hass.states[this._config.entity];
            const a = so.attributes;
            const p = this._pending || {};
            if (isRange) {
                this._call("set_temperature", {
                    target_temp_low: (_a = p.target_temp_low) !== null && _a !== void 0 ? _a : a.target_temp_low,
                    target_temp_high: (_b = p.target_temp_high) !== null && _b !== void 0 ? _b : a.target_temp_high,
                });
            }
            else if (p.temperature != null) {
                this._call("set_temperature", { temperature: p.temperature });
            }
        }, 1000);
    }
    _call(service, data) {
        this._hass.callService("climate", service, Object.assign({ entity_id: this._config.entity }, data));
    }
    _moreInfo(entityId) {
        this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
    }
    _styles() {
        return `<style>
      :host { display:block; }
      ha-card {
        position: relative; overflow: hidden; padding: 16px 16px 18px;
        --muted: var(--secondary-text-color, #8a8f98);
        --surface: var(--secondary-background-color, rgba(127,127,127,.08));
        --text: var(--primary-text-color, #222);
      }
      .bg {
        position:absolute; top:-40%; left:-20%; right:-20%; height: 90%;
        background: radial-gradient(closest-side, var(--c1), transparent);
        opacity: .10; pointer-events:none; transition: background .6s, opacity .6s;
      }
      ha-card.is-off .bg { opacity: .04; }
      .warning { padding: 16px; color: var(--error-color, #db4437); }
      .header { position:relative; display:flex; align-items:center; justify-content:space-between; min-height:32px; }
      .title { font-size: 1.15rem; font-weight: 600; color: var(--text); letter-spacing:.01em; }
      button { font: inherit; color: inherit; border: none; background: none; cursor: pointer; -webkit-tap-highlight-color: transparent; }
      .more { width:36px; height:36px; border-radius:50%; color: var(--muted); display:flex; align-items:center; justify-content:center; }
      .more:hover { background: var(--surface); }

      .dial-wrap { position:relative; width: 100%; max-width: 280px; margin: 0 auto; }
      .dial-box { position:relative; width:100%; height:0; padding-bottom:100%; }
      .dial-box > svg { position:absolute; top:0; left:0; }
      svg.dial { width:100%; height:100%; display:block; touch-action:none; user-select:none; }
      .track { fill:none; stroke: var(--surface); stroke-width: 14; stroke-linecap: round; }
      .fill { fill:none; stroke-width: 14; stroke-linecap: round; transition: d .25s; }
      .glow { filter: url(#glow); }
      .tick { stroke: var(--muted); stroke-width: 1; opacity: .35; }
      .tick.major { opacity: .7; stroke-width: 1.4; }
      .cur-marker { stroke: var(--text); stroke-width: 3; stroke-linecap: round; }
      .handle { fill: #fff; stroke: var(--c1); stroke-width: 4; cursor: grab; filter: drop-shadow(0 1px 3px rgba(0,0,0,.35)); }
      .handle:active { cursor: grabbing; }
      .hit { fill:none; stroke: transparent; stroke-width: 34; stroke-linecap: round; cursor: pointer; pointer-events: stroke; }
      .scale { fill: var(--muted); font-size: 10px; }

      .center { position:absolute; top:0; left:0; right:0; bottom:0; display:flex; flex-direction:column; align-items:center; justify-content:center; pointer-events:none; padding-top: 4px; }
      .action { display:flex; align-items:center; font-size: .8rem; font-weight:600; text-transform: uppercase; letter-spacing:.08em; color: var(--muted); }
      .action .dot { width:8px; height:8px; border-radius:50%; background: var(--muted); }
      .action.on { color: var(--c); }
      .action.on .dot { background: var(--c); box-shadow: 0 0 0 0 var(--c); animation: pulse 1.8s infinite; }
      @keyframes pulse { 0% { box-shadow: 0 0 0 0 var(--cp); } 100% { box-shadow: 0 0 0 9px transparent; } }
      .big { font-size: 3.6rem; font-weight: 300; line-height: 1.05; color: var(--text); font-variant-numeric: tabular-nums; margin: 2px 0; }
      .big .unit { font-size: 1.6rem; vertical-align: top; margin-left: 2px; position:relative; top: .5rem; color: var(--muted); }
      .big.range { font-size: 2.4rem; }
      .big .sep { color: var(--muted); margin: 0 4px; font-weight:200; }
      .big.off-label { color: var(--muted); margin: 10px 0 8px; }
      .big.off-label ha-icon { --mdc-icon-size: 44px; opacity: .6; }
      .current { display:flex; align-items:center; color: var(--muted); font-size: .95rem; font-variant-numeric: tabular-nums; }
      .current ha-icon { --mdc-icon-size: 18px; }
      .current .hum { display:flex; align-items:center; margin-left: 8px; }
      .current ha-icon { margin-right: 3px; }
      .action .dot { margin-right: 6px; }

      .steppers { display:flex; justify-content:center; margin-top: -26px; position:relative; }
      .steppers.two { margin-top: -8px; }
      .steppers > * + * { margin-left: 72px; }
      .steppers.two > * + * { margin-left: 16px; }
      .round { width:48px; height:48px; border-radius:50%; background: var(--surface); display:flex; align-items:center; justify-content:center; transition: transform .1s, background .2s; }
      .round:hover { background: var(--c1s); }
      .round:active { transform: scale(.92); }
      .round.small { width:38px; height:38px; }
      .stepper { display:flex; align-items:center; background: var(--surface); border-radius: 24px; padding: 4px; }
      .stepper-val { min-width: 54px; text-align:center; font-size: 1.1rem; font-variant-numeric: tabular-nums; }
      .stepper-val span { display:block; font-size: .65rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }

      .modes { display:grid; grid-auto-flow:column; grid-auto-columns:1fr; grid-gap:6px; gap:6px; margin-top: 18px; background: var(--surface); border-radius: 16px; padding: 4px; }
      .mode { display:flex; flex-direction:column; align-items:center; padding: 8px 4px; border-radius: 12px; color: var(--muted); font-size: .72rem; transition: background .2s, color .2s; }
      .mode ha-icon { --mdc-icon-size: 22px; }
      .mode:hover { color: var(--text); }
      .mode.sel { background: var(--cs); color: var(--c); font-weight: 600; }

      .sel-title { display:flex; justify-content:space-between; align-items:baseline; }
      .sel-modes .mode span { white-space:normal; line-height:1.2; }
      .sel-title .upd { text-transform:none; letter-spacing:0; font-weight:400; }
      .mode span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; }
      .mode { min-width:0; }
      button[disabled] { opacity:.4; cursor:default; }
      .section-title { margin: 16px 2px 8px; font-size: .72rem; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); font-weight: 600; }
      .presets { display:flex; flex-wrap:wrap; margin: 0 -8px -8px 0; }
      .presets .chip { margin: 0 8px 8px 0; }
      .chip ha-icon { margin-right: 6px; }
      .stepper-val { margin: 0 8px; }
      .chip { display:flex; align-items:center; padding: 7px 14px; border-radius: 999px; background: var(--surface); color: var(--text); font-size: .85rem; transition: background .2s, color .2s, box-shadow .2s; }
      .chip ha-icon { --mdc-icon-size: 18px; }
      .chip.sel { background: var(--c); color: #fff; box-shadow: 0 4px 14px -4px var(--c); }

      .status { display:grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); grid-gap: 8px; gap: 8px; margin-top: 16px; }
      .stat { display:flex; align-items:center; padding: 8px 10px; border-radius: 14px; background: var(--surface); cursor:pointer; }
      .stat-icon { width:32px; height:32px; border-radius: 10px; display:flex; align-items:center; justify-content:center; color: var(--c); background: var(--cs); flex: none; margin-right: 10px; }
      .stat-icon ha-icon { --mdc-icon-size: 20px; }
      .stat.on .stat-icon { background: var(--c); color:#fff; }
      .stat-txt { min-width:0; }
      .stat-name { font-size: .78rem; color: var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .stat-val { font-size: .9rem; font-weight: 600; color: var(--text); }
    </style>`;
    }
}
/* -------- Editor visuale -------- */
class ClimateManagerCardEditor extends HTMLElement {
    setConfig(config) {
        this._config = Object.assign({ show_modes: true, show_presets: true }, config);
        this._render();
    }
    set hass(hass) {
        this._hass = hass;
        if (this._form)
            this._form.hass = hass;
        else
            this._render();
    }
    _render() {
        var _a;
        if (!this._hass || !this._config)
            return;
        const lang = (((_a = this._hass.locale) === null || _a === void 0 ? void 0 : _a.language) || this._hass.language || "it").slice(0, 2);
        const L = (I18N[lang] || I18N.en).editor;
        if (!this._form) {
            this._form = document.createElement("ha-form");
            this._form.computeLabel = (s) => L[s.name] || s.name;
            this._form.addEventListener("value-changed", (ev) => {
                const cfg = Object.assign({}, ev.detail.value);
                if (Array.isArray(cfg.entities) && !cfg.entities.length)
                    delete cfg.entities;
                if (!cfg.name)
                    delete cfg.name;
                this._config = cfg;
                this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
            });
            this.appendChild(this._form);
        }
        this._form.hass = this._hass;
        this._form.schema = [
            { name: "entity", required: true, selector: { entity: { domain: "climate" } } },
            { name: "name", selector: { text: {} } },
            {
                type: "grid",
                name: "",
                schema: [
                    { name: "show_modes", selector: { boolean: {} } },
                    { name: "show_presets", selector: { boolean: {} } },
                ],
            },
            { name: "entities", selector: { entity: { multiple: true } } },
        ];
        // l'editor visuale gestisce solo liste di stringhe
        const data = Object.assign({}, this._config);
        if (Array.isArray(data.entities))
            data.entities = data.entities.map((e) => (typeof e === "string" ? e : e.entity));
        this._form.data = data;
    }
}
/* -------- Card selettore (select / input_select) nello stesso stile -------- */
// Valori interni della Sorgente di Climate Manager: icona fissa, indipendente dal nome mostrato
const SOURCE_ICONS = {
    heating: "mdi:water-boiler",
    ac: "mdi:sun-snowflake-variant",
    ac_summer: "mdi:snowflake",
    both: "mdi:fire-circle",
};
function optionIcon(opt) {
    if (SOURCE_ICONS[opt]) return SOURCE_ICONS[opt];
    const o = String(opt).toLowerCase();
    const rad = /radiant|pavimento|heating|serpentin/.test(o);
    const clima = /clima|condiz|split|air|pompa di calore|heat pump/.test(o);
    if (rad && clima) return "mdi:sun-snowflake-variant";
    if (rad) return "mdi:heating-coil";
    if (clima) return "mdi:air-conditioner";
    if (/caldai|boiler/.test(o)) return "mdi:water-boiler";
    if (/off|spent|nessun/.test(o)) return "mdi:power";
    if (/auto/.test(o)) return "mdi:autorenew";
    return null;
}
function relTime(iso, lang) {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const s = Math.round((d.getTime() - Date.now()) / 1000);
    const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
    const abs = Math.abs(s);
    if (abs < 60) return rtf.format(s, "second");
    if (abs < 3600) return rtf.format(Math.round(s / 60), "minute");
    if (abs < 86400) return rtf.format(Math.round(s / 3600), "hour");
    return rtf.format(Math.round(s / 86400), "day");
}
class ClimateManagerSelectCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._timer = null;
        this._last = null;
    }
    static getConfigElement() {
        return document.createElement("climate-manager-select-card-editor");
    }
    static getStubConfig(hass) {
        const ent = Object.keys((hass && hass.states) || {}).find((e) => e.startsWith("select.") || e.startsWith("input_select."));
        return { entity: ent || "select.esempio" };
    }
    setConfig(config) {
        if (!config || !config.entity || !/^(input_)?select\./.test(config.entity)) {
            throw new Error("Specifica un'entità select o input_select");
        }
        this._config = Object.assign({ show_last_updated: true, color: "#ff7a2f" }, config);
        this._last = null;
        if (this._hass) this._render();
    }
    set hass(hass) {
        this._hass = hass;
        if (!this._config) return;
        const so = hass.states[this._config.entity];
        if (so === this._last) return;
        this._last = so;
        this._render();
    }
    connectedCallback() {
        // aggiorna "x minuti fa" ogni 30 s
        this._timer = setInterval(() => { if (this._hass) this._render(); }, 30000);
    }
    disconnectedCallback() {
        clearInterval(this._timer);
    }
    getCardSize() {
        return 2;
    }
    getGridOptions() {
        return { columns: 12, min_columns: 4, rows: "auto" };
    }
    _render() {
        const hass = this._hass;
        const cfg = this._config;
        const so = hass.states[cfg.entity];
        const lang = ((hass.locale && hass.locale.language) || hass.language || "it").slice(0, 2);
        const c1 = cfg.color;
        if (!so) {
            this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="warning">Entità non trovata: ${esc(cfg.entity)}</div></ha-card>`;
            return;
        }
        const a = so.attributes;
        const unavailable = so.state === "unavailable" || so.state === "unknown";
        const options = a.options || [];
        const icons = cfg.icons || {};
        const title = cfg.name || a.friendly_name || cfg.entity;
        const icon = cfg.icon || a.icon || optionIcon(so.state) || "mdi:form-dropdown";
        const sub = unavailable
            ? (I18N[lang] || I18N.en).unavailable
            : cfg.show_last_updated
                ? `${esc(fmtState(hass, so))} · ${esc(relTime(so.last_updated, lang))}`
                : esc(fmtState(hass, so));
        const segmented = options.length > 0 && options.length <= 4;
        const optsHtml = options
            .map((o) => {
            const lbl = fmtState(hass, so, o);
            const ic = icons[o] || icons[lbl] || optionIcon(o) || optionIcon(lbl);
            const sel = so.state === o;
            return `<button class="${segmented ? "seg" : "chip"} ${sel ? "sel" : ""}" data-opt="${esc(o)}" ${unavailable ? "disabled" : ""}>
              ${ic ? `<ha-icon icon="${esc(ic)}"></ha-icon>` : ""}<span>${esc(lbl)}</span>
            </button>`;
        })
            .join("");
        this.shadowRoot.innerHTML = `
      ${this._styles()}
      <ha-card style="--c1:${c1};--cs:${rgba(c1, 0.16)};--cg:${rgba(c1, 0.45)}">
        <div class="bg"></div>
        <div class="header">
          <div class="h-icon"><ha-icon icon="${esc(icon)}"></ha-icon></div>
          <div class="h-txt">
            <div class="title">${esc(title)}</div>
            <div class="sub">${sub}</div>
          </div>
          <button class="more" aria-label="info"><ha-icon icon="mdi:dots-vertical"></ha-icon></button>
        </div>
        <div class="${segmented ? "segs" : "chips"}" style="${segmented ? `grid-template-columns: repeat(${options.length}, 1fr)` : ""}">${optsHtml}</div>
      </ha-card>`;
        const domain = cfg.entity.split(".")[0];
        this.shadowRoot.querySelectorAll("button[data-opt]").forEach((b) => b.addEventListener("click", () => {
            if (b.dataset.opt === so.state) return;
            hass.callService(domain, "select_option", { entity_id: cfg.entity, option: b.dataset.opt });
        }));
        this.shadowRoot.querySelector(".more").addEventListener("click", () => this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: cfg.entity }, bubbles: true, composed: true })));
    }
    _styles() {
        return `<style>
      :host { display:block; }
      ha-card { position:relative; overflow:hidden; padding: 14px 16px 16px;
        --muted: var(--secondary-text-color, #8a8f98);
        --surface: var(--secondary-background-color, rgba(127,127,127,.08));
        --text: var(--primary-text-color, #222); }
      .bg { position:absolute; top:-120%; left:-10%; width:60%; height:240%;
        background: radial-gradient(closest-side, var(--c1), transparent); opacity:.08; pointer-events:none; }
      .warning { padding: 16px; color: var(--error-color, #db4437); }
      button { font: inherit; color: inherit; border: none; background: none; cursor: pointer; -webkit-tap-highlight-color: transparent; }
      .header { position:relative; display:flex; align-items:center; }
      .h-icon { width:40px; height:40px; border-radius:12px; flex:none; margin-right:12px;
        display:flex; align-items:center; justify-content:center; background: var(--cs); color: var(--c1); }
      .h-txt { flex:1; min-width:0; }
      .title { font-size: 1.05rem; font-weight:600; color: var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .sub { font-size: .8rem; color: var(--muted); margin-top: 1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .more { width:36px; height:36px; border-radius:50%; color: var(--muted); display:flex; align-items:center; justify-content:center; flex:none; }
      .more:hover { background: var(--surface); }

      .segs { position:relative; display:grid; grid-gap:6px; gap:6px; margin-top: 14px; background: var(--surface); border-radius: 16px; padding: 4px; }
      .seg { display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 9px 4px; border-radius: 12px;
        color: var(--muted); font-size: .78rem; text-align:center; transition: background .2s, color .2s; min-width:0; }
      .seg ha-icon { --mdc-icon-size: 22px; margin-bottom: 3px; }
      .seg span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; }
      .seg:hover { color: var(--text); }
      .seg.sel { background: var(--cs); color: var(--c1); font-weight:600; }

      .chips { position:relative; display:flex; flex-wrap:wrap; margin: 14px -8px -8px 0; }
      .chip { display:flex; align-items:center; padding: 7px 14px; margin: 0 8px 8px 0; border-radius: 999px;
        background: var(--surface); font-size: .85rem; color: var(--text); transition: background .2s, color .2s, box-shadow .2s; }
      .chip ha-icon { --mdc-icon-size: 18px; margin-right: 6px; }
      .chip.sel { background: var(--c1); color:#fff; box-shadow: 0 4px 14px -4px var(--cg); }
      button[disabled] { opacity:.4; cursor: default; }
    </style>`;
    }
}
class ClimateManagerSelectCardEditor extends HTMLElement {
    setConfig(config) {
        this._config = Object.assign({ show_last_updated: true }, config);
        this._render();
    }
    set hass(hass) {
        this._hass = hass;
        if (this._form) this._form.hass = hass;
        else this._render();
    }
    _render() {
        if (!this._hass || !this._config) return;
        if (!this._form) {
            const labels = { entity: "Entità", name: "Nome (opzionale)", icon: "Icona (opzionale)", color: "Colore (es. #ff7a2f)", show_last_updated: "Mostra ultimo aggiornamento" };
            this._form = document.createElement("ha-form");
            this._form.computeLabel = (s) => labels[s.name] || s.name;
            this._form.addEventListener("value-changed", (ev) => {
                const cfg = Object.assign({}, ev.detail.value);
                ["name", "icon", "color"].forEach((k) => { if (!cfg[k]) delete cfg[k]; });
                this._config = cfg;
                this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
            });
            this.appendChild(this._form);
        }
        this._form.hass = this._hass;
        this._form.schema = [
            { name: "entity", required: true, selector: { entity: { domain: ["select", "input_select"] } } },
            { name: "name", selector: { text: {} } },
            { type: "grid", name: "", schema: [
                    { name: "icon", selector: { icon: {} } },
                    { name: "color", selector: { text: {} } },
                ] },
            { name: "show_last_updated", selector: { boolean: {} } },
        ];
        this._form.data = this._config;
    }
}
// Se la card è già stata caricata (es. vecchia risorsa /local/ rimasta), non la registra due volte
if (!customElements.get("climate-manager-card")) {
customElements.define("climate-manager-card", ClimateManagerCard);
customElements.define("climate-manager-card-editor", ClimateManagerCardEditor);
customElements.define("climate-manager-select-card", ClimateManagerSelectCard);
customElements.define("climate-manager-select-card-editor", ClimateManagerSelectCardEditor);
window.customCards = window.customCards || [];
window.customCards.push({
    type: "climate-manager-select-card",
    name: "Climate Manager Select Card",
    description: "Selettore (select / input_select) nello stile di Climate Manager",
    preview: true,
});
window.customCards.push({
    type: "climate-manager-card",
    name: "Climate Manager Card",
    description: "Termostato con quadrante, modalità, preset e stato di caldaia/pompa/finestra",
    preview: true,
    documentationURL: "https://github.com/ichnusa82/climate_manager",
});
console.info(`%c CLIMATE-MANAGER-CARD %c v${CARD_VERSION} `, "color:#fff;background:#ff7a2f;font-weight:700", "color:#ff7a2f;background:#222");
}
