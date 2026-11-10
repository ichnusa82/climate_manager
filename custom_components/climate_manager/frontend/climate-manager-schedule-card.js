/*
 * Climate Manager – Cronotermostato a cavalieri
 * Card per Home Assistant: ogni cavaliere è un intervallo (15/30/60 min).
 * Cavaliere ALTO = comfort (dentro fascia), BASSO = ridotta (fuori fascia).
 * Salva con il servizio climate_manager.set_schedule.
 */
const CM_VERSION = "1.2.0";
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

const I18N = {
  it: {
    days: { mon: "Lun", tue: "Mar", wed: "Mer", thu: "Gio", fri: "Ven", sat: "Sab", sun: "Dom" },
    daysLong: { mon: "Lunedì", tue: "Martedì", wed: "Mercoledì", thu: "Giovedì", fri: "Venerdì", sat: "Sabato", sun: "Domenica" },
    comfort: "Comfort", eco: "Ridotta", inSlot: "In fascia", outSlot: "Fuori fascia",
    save: "Salva", undo: "Annulla", saved: "Programma salvato", unsaved: "Modifiche non salvate",
    copy: "Copia su…", copyTo: "Copia {day} su:", apply: "Applica", weekdays: "Lun–Ven", all: "Tutti",
    allOn: "Tutto alto", allOff: "Tutto basso", week: "Settimana",
    notAuto: "Il termostato non è in Auto: il programma vale solo in modalità Auto.", toAuto: "Passa ad Auto",
    blocked: "Programma bloccato da calendario", missing: "Entità non trovata", noSchedule: "Questa entità non è un termostato Climate Manager",
    error: "Errore nel salvataggio", hint: "Tocca o trascina sui cavalieri",
  },
  en: {
    days: { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" },
    daysLong: { mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" },
    comfort: "Comfort", eco: "Eco", inSlot: "In slot", outSlot: "Outside slot",
    save: "Save", undo: "Undo", saved: "Schedule saved", unsaved: "Unsaved changes",
    copy: "Copy to…", copyTo: "Copy {day} to:", apply: "Apply", weekdays: "Mon–Fri", all: "All",
    allOn: "All up", allOff: "All down", week: "Week",
    notAuto: "The thermostat is not in Auto: the schedule only applies in Auto mode.", toAuto: "Switch to Auto",
    blocked: "Schedule blocked by calendar", missing: "Entity not found", noSchedule: "This entity is not a Climate Manager thermostat",
    error: "Save failed", hint: "Tap or drag over the pegs",
  },
};

/* ---------- conversione fasce <-> cavalieri (stessa logica dell'integrazione) ---------- */
const toMin = (v) => {
  const [h, m] = String(v).split(":").map(Number);
  return h * 60 + (m || 0);
};
const fmt = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

function slotActive(slots, wd, minutes) {
  for (const s of slots) {
    if (s.start < s.end) {
      if (s.days.has(wd) && minutes >= s.start && minutes < s.end) return true;
    } else {
      if (s.days.has(wd) && minutes >= s.start) return true;
      if (s.days.has((wd + 6) % 7) && minutes < s.end) return true;
    }
  }
  return false;
}

function slotsToGrid(raw, step) {
  const n = 1440 / step;
  const slots = (raw || [])
    .map((s) => ({
      days: new Set((s.days || []).map((d) => DAYS.indexOf(d)).filter((i) => i >= 0)),
      start: toMin(s.start),
      end: toMin(s.end),
    }))
    .filter((s) => s.days.size);
  return DAYS.map((_, wd) => Array.from({ length: n }, (_, i) => slotActive(slots, wd, i * step)));
}

function gridToSlots(grid, step) {
  const map = new Map(); // "start-end" -> giorni
  grid.forEach((pegs, wd) => {
    let i = 0;
    while (i < pegs.length) {
      if (!pegs[i]) { i++; continue; }
      let j = i;
      while (j < pegs.length && pegs[j]) j++;
      const key = `${fmt(i * step)}-${fmt((j * step) % 1440)}`; // fine a mezzanotte = 00:00
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(DAYS[wd]);
      i = j;
    }
  });
  return [...map.entries()]
    .map(([k, days]) => {
      const [start, end] = k.split("-");
      return { days, start, end };
    })
    .sort((a, b) => DAYS.indexOf(a.days[0]) - DAYS.indexOf(b.days[0]) || a.start.localeCompare(b.start));
}

/* ---------- card ---------- */
class ClimateManagerScheduleCard extends HTMLElement {
  static getStubConfig(hass) {
    const id = Object.keys(hass.states).find(
      (e) => e.startsWith("climate.") && Array.isArray(hass.states[e].attributes.schedule)
    );
    return { entity: id || "", step: 30 };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Specifica 'entity' (climate.xxx)");
    const step = Number(config.step || 30);
    if (![15, 30, 60].includes(step)) throw new Error("'step' deve essere 15, 30 o 60");
    this._config = { show_week: true, ...config, step };
    this._grid = null;
    this._saved = null;
    this._sig = null;
    this._dirty = false;
    this._copyOpen = false;
    this._copyTargets = new Set();
    this._msg = "";
    const jsDay = new Date().getDay();
    this._day = this._day ?? (jsDay + 6) % 7;
    this._built = false;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const st = hass.states[this._config?.entity];
    const sched = st?.attributes?.schedule;
    if (Array.isArray(sched)) {
      const sig = JSON.stringify(sched);
      if (sig !== this._sig && !this._dirty && !this._saving) {
        this._sig = sig;
        this._grid = slotsToGrid(sched, this._config.step);
        this._saved = this._grid.map((d) => d.slice());
      }
    }
    this._render();
  }

  getCardSize() { return this._config?.show_week ? 7 : 4; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: "auto" }; }

  get _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").toLowerCase();
    return lang.startsWith("it") ? I18N.it : I18N.en;
  }

  /* ---------- rendering ---------- */
  _render() {
    if (!this._config || !this._hass) return;
    if (!this._built) this._build();
    const t = this._t;
    const st = this._hass.states[this._config.entity];
    const body = this.shadowRoot.getElementById("body");
    const err = this.shadowRoot.getElementById("err");
    if (!st || !Array.isArray(st.attributes.schedule)) {
      body.hidden = true;
      err.hidden = false;
      err.textContent = !st ? `${t.missing}: ${this._config.entity}` : t.noSchedule;
      return;
    }
    body.hidden = false;
    err.hidden = true;
    this._renderHeader(st);
    this._renderTabs();
    this._renderPegs();
    this._renderWeek();
    this._renderFooter(st);
  }

  _build() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="err" id="err" hidden></div>
        <div id="body">
          <div class="head">
            <div class="title"><ha-icon icon="mdi:calendar-clock"></ha-icon><span id="name"></span></div>
            <div class="info" id="info"></div>
          </div>
          <div class="warn" id="warn" hidden></div>
          <div class="tabs" id="tabs"></div>
          <div class="dayname" id="dayname"></div>
          <div class="board">
            <div class="scale"><span class="up"></span><span class="down"></span></div>
            <div class="pegwrap">
              <div class="pegs" id="pegs"></div>
              <div class="now" id="now" hidden></div>
              <div class="hours" id="hours"></div>
            </div>
          </div>
          <div class="legend" id="legend"></div>
          <div class="tools">
            <button class="btn ghost" id="copy"><ha-icon icon="mdi:content-copy"></ha-icon><span></span></button>
            <button class="btn ghost" id="allon"><ha-icon icon="mdi:arrow-up-bold"></ha-icon><span></span></button>
            <button class="btn ghost" id="alloff"><ha-icon icon="mdi:arrow-down-bold"></ha-icon><span></span></button>
          </div>
          <div class="copypanel" id="copypanel" hidden></div>
          <div class="week" id="week"></div>
          <div class="foot">
            <span class="msg" id="msg"></span>
            <button class="btn ghost" id="undo"></button>
            <button class="btn primary" id="save"></button>
          </div>
        </div>
      </ha-card>`;
    const $ = (id) => this.shadowRoot.getElementById(id);

    // cavalieri: tocco singolo o trascinamento (mouse e touch)
    const pegs = $("pegs");
    const pegAt = (e) => {
      const el = this.shadowRoot.elementFromPoint(e.clientX, e.clientY);
      const p = el?.closest?.(".peg");
      return p && pegs.contains(p) ? Number(p.dataset.i) : null;
    };
    pegs.addEventListener("pointerdown", (e) => {
      const i = pegAt(e);
      if (i === null) return;
      e.preventDefault();
      pegs.setPointerCapture(e.pointerId);
      this._paint = !this._grid[this._day][i];
      this._last = i;
      this._setPeg(i, this._paint);
    });
    pegs.addEventListener("pointermove", (e) => {
      if (this._paint === undefined) return;
      const i = pegAt(e);
      if (i === null || i === this._last) return;
      const [a, b] = this._last < i ? [this._last, i] : [i, this._last];
      for (let k = a; k <= b; k++) this._setPeg(k, this._paint, false);
      this._last = i;
      this._afterEdit();
    });
    const stop = () => { this._paint = undefined; this._last = undefined; };
    pegs.addEventListener("pointerup", stop);
    pegs.addEventListener("pointercancel", stop);

    $("copy").addEventListener("click", () => {
      this._copyOpen = !this._copyOpen;
      this._copyTargets = new Set();
      this._render();
    });
    $("allon").addEventListener("click", () => this._fillDay(true));
    $("alloff").addEventListener("click", () => this._fillDay(false));
    $("undo").addEventListener("click", () => {
      this._grid = this._saved.map((d) => d.slice());
      this._dirty = false;
      this._msg = "";
      this._render();
    });
    $("save").addEventListener("click", () => this._save());
    this._built = true;
  }

  _renderHeader(st) {
    const t = this._t;
    const $ = (id) => this.shadowRoot.getElementById(id);
    const a = st.attributes;
    $("name").textContent = this._config.title || a.friendly_name || this._config.entity;
    const unit = this._hass.config?.unit_system?.temperature || "°C";
    const num = (v) => (v === undefined || v === null ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 }));
    const contact = a.comfort_temperature === undefined;
    let badge = "";
    if (a.schedule_state) {
      const on = a.schedule_state === "comfort" || a.schedule_state === "in_slot";
      const lbl = contact ? (on ? t.inSlot : t.outSlot) : on ? t.comfort : t.eco;
      badge = `<span class="badge ${on ? "on" : "off"}">${lbl}</span>`;
    }
    const cur = a.current_temperature !== undefined && a.current_temperature !== null
      ? `<span class="cur">${num(a.current_temperature)} ${unit}</span>` : "";
    const tgt = a.temperature !== undefined && a.temperature !== null
      ? `<span class="tgt"><ha-icon icon="mdi:target"></ha-icon>${num(a.temperature)}</span>` : "";
    const mode = this._hass.formatEntityState ? this._hass.formatEntityState(st) : st.state;
    $("info").innerHTML = `${cur}${tgt}${badge}<span class="mode">${mode}</span>`;

    const warn = $("warn");
    const hasSlots = this._saved?.some((d) => d.some(Boolean));
    if (a.blocked) {
      warn.hidden = false;
      warn.innerHTML = `<ha-icon icon="mdi:calendar-lock"></ha-icon><span>${t.blocked}</span>`;
    } else if (st.state !== "auto" && hasSlots && (a.hvac_modes || []).includes("auto")) {
      warn.hidden = false;
      warn.innerHTML = `<ha-icon icon="mdi:information-outline"></ha-icon><span>${t.notAuto}</span><button class="btn small">${t.toAuto}</button>`;
      warn.querySelector("button").onclick = () =>
        this._hass.callService("climate", "set_hvac_mode", { entity_id: this._config.entity, hvac_mode: "auto" });
    } else {
      warn.hidden = true;
    }

    const legend = $("legend");
    const c = contact ? t.inSlot : `${t.comfort} ${num(a.comfort_temperature)} ${unit}`;
    const e = contact ? t.outSlot : `${t.eco} ${num(a.eco_temperature)} ${unit}`;
    legend.innerHTML = `<span><i class="sw on"></i>${c}</span><span><i class="sw off"></i>${e}</span><span class="hint">${t.hint}</span>`;
  }

  _renderTabs() {
    const t = this._t;
    const tabs = this.shadowRoot.getElementById("tabs");
    const today = (new Date().getDay() + 6) % 7;
    tabs.innerHTML = DAYS.map((d, i) => {
      const changed = this._saved && this._grid[i].some((v, k) => v !== this._saved[i][k]);
      return `<button class="tab ${i === this._day ? "sel" : ""} ${i === today ? "today" : ""}" data-d="${i}">${t.days[d]}${changed ? '<i class="dot"></i>' : ""}</button>`;
    }).join("");
    tabs.querySelectorAll(".tab").forEach((b) =>
      b.addEventListener("click", () => {
        this._day = Number(b.dataset.d);
        this._copyOpen = false;
        this._render();
      })
    );
    this.shadowRoot.getElementById("dayname").textContent = t.daysLong[DAYS[this._day]];
  }

  _renderPegs() {
    const step = this._config.step;
    const n = 1440 / step;
    const pegs = this.shadowRoot.getElementById("pegs");
    if (pegs.childElementCount !== n) {
      pegs.style.gridTemplateColumns = `repeat(${n}, 1fr)`;
      pegs.innerHTML = Array.from({ length: n }, (_, i) => {
        const m = i * step;
        const cls = m % 60 === 0 ? (m % 360 === 0 ? "h6" : "h") : "";
        return `<div class="peg ${cls}" data-i="${i}" title="${fmt(m)}–${fmt((m + step) % 1440)}"><span class="knob"></span></div>`;
      }).join("");
      const hours = this.shadowRoot.getElementById("hours");
      hours.innerHTML = [0, 3, 6, 9, 12, 15, 18, 21, 24]
        .map((h) => `<span style="left:${(h / 24) * 100}%">${h}</span>`)
        .join("");
    }
    const day = this._grid[this._day];
    [...pegs.children].forEach((p, i) => p.classList.toggle("on", day[i]));
    // linea dell'ora attuale sul giorno di oggi
    const now = new Date();
    const nowEl = this.shadowRoot.getElementById("now");
    const today = (now.getDay() + 6) % 7;
    nowEl.hidden = today !== this._day;
    nowEl.style.left = `${((now.getHours() * 60 + now.getMinutes()) / 1440) * 100}%`;
  }

  _renderWeek() {
    const t = this._t;
    const week = this.shadowRoot.getElementById("week");
    if (!this._config.show_week) { week.hidden = true; return; }
    week.hidden = false;
    const step = this._config.step;
    const now = new Date();
    const today = (now.getDay() + 6) % 7;
    const pct = ((now.getHours() * 60 + now.getMinutes()) / 1440) * 100;
    week.innerHTML = `<div class="wtitle">${t.week}</div>` + DAYS.map((d, wd) => {
      // segmenti continui invece di un div per cavaliere
      const segs = [];
      const pegs = this._grid[wd];
      let i = 0;
      while (i < pegs.length) {
        if (!pegs[i]) { i++; continue; }
        let j = i;
        while (j < pegs.length && pegs[j]) j++;
        segs.push(`<i style="left:${(i * step / 1440) * 100}%;width:${((j - i) * step / 1440) * 100}%" title="${fmt(i * step)}–${fmt((j * step) % 1440)}"></i>`);
        i = j;
      }
      const mark = wd === today ? `<b style="left:${pct}%"></b>` : "";
      return `<div class="wrow ${wd === this._day ? "sel" : ""}" data-d="${wd}"><span>${t.days[d]}</span><div class="bar">${segs.join("")}${mark}</div></div>`;
    }).join("");
    week.querySelectorAll(".wrow").forEach((r) =>
      r.addEventListener("click", () => {
        this._day = Number(r.dataset.d);
        this._render();
      })
    );
  }

  _renderFooter() {
    const t = this._t;
    const $ = (id) => this.shadowRoot.getElementById(id);
    $("copy").querySelector("span").textContent = t.copy;
    $("allon").querySelector("span").textContent = t.allOn;
    $("alloff").querySelector("span").textContent = t.allOff;
    $("copy").classList.toggle("active", this._copyOpen);
    $("undo").textContent = t.undo;
    $("save").textContent = this._saving ? "…" : t.save;
    $("undo").disabled = !this._dirty || this._saving;
    $("save").disabled = !this._dirty || this._saving;
    $("msg").textContent = this._dirty ? t.unsaved : this._msg;
    $("msg").className = `msg ${this._dirty ? "dirty" : ""} ${this._msgErr ? "bad" : ""}`;

    const panel = $("copypanel");
    panel.hidden = !this._copyOpen;
    if (this._copyOpen) {
      const chips = DAYS.map((d, i) =>
        i === this._day ? "" :
        `<button class="chip ${this._copyTargets.has(i) ? "sel" : ""}" data-d="${i}">${t.days[d]}</button>`
      ).join("");
      panel.innerHTML = `<span class="ct">${t.copyTo.replace("{day}", t.days[DAYS[this._day]])}</span>
        <div class="chips">${chips}
          <button class="chip alt" data-set="wd">${t.weekdays}</button>
          <button class="chip alt" data-set="all">${t.all}</button></div>
        <button class="btn primary small" id="applycopy">${t.apply}</button>`;
      panel.querySelectorAll(".chip[data-d]").forEach((c) =>
        c.addEventListener("click", () => {
          const i = Number(c.dataset.d);
          this._copyTargets.has(i) ? this._copyTargets.delete(i) : this._copyTargets.add(i);
          this._render();
        })
      );
      panel.querySelectorAll(".chip[data-set]").forEach((c) =>
        c.addEventListener("click", () => {
          const set = c.dataset.set === "wd" ? [0, 1, 2, 3, 4] : [0, 1, 2, 3, 4, 5, 6];
          this._copyTargets = new Set(set.filter((i) => i !== this._day));
          this._render();
        })
      );
      panel.querySelector("#applycopy").addEventListener("click", () => {
        this._copyTargets.forEach((i) => (this._grid[i] = this._grid[this._day].slice()));
        this._copyOpen = false;
        this._afterEdit();
      });
    }
  }

  /* ---------- modifiche ---------- */
  _setPeg(i, value, refresh = true) {
    this._grid[this._day][i] = value;
    if (refresh) this._afterEdit();
  }

  _fillDay(value) {
    this._grid[this._day] = this._grid[this._day].map(() => value);
    this._afterEdit();
  }

  _afterEdit() {
    this._dirty = JSON.stringify(this._grid) !== JSON.stringify(this._saved);
    this._msg = "";
    this._msgErr = false;
    this._render();
  }

  async _save() {
    const t = this._t;
    this._saving = true;
    this._render();
    try {
      await this._hass.callService("climate_manager", "set_schedule", {
        slots: gridToSlots(this._grid, this._config.step),
      }, { entity_id: this._config.entity });
      this._saved = this._grid.map((d) => d.slice());
      this._dirty = false;
      this._sig = null; // ricarica dallo stato appena arriva l'aggiornamento
      this._msg = t.saved;
      this._msgErr = false;
    } catch (e) {
      this._msg = `${t.error}: ${e.message || e}`;
      this._msgErr = true;
    }
    this._saving = false;
    this._render();
  }
}

const STYLE = `
  :host { --cm-on: var(--state-climate-heat-color, #ff8a00); --cm-off: var(--state-climate-cool-color, #2b9af3); }
  ha-card { padding: 16px; }
  .err { color: var(--error-color); }
  .head { display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; }
  .title { display:flex; align-items:center; gap:8px; font-size:1.15em; font-weight:500; }
  .title ha-icon { color: var(--cm-on); }
  .info { display:flex; align-items:center; gap:8px; flex-wrap:wrap; font-size:.9em; color: var(--secondary-text-color); }
  .info .cur { font-size:1.25em; color: var(--primary-text-color); font-weight:500; }
  .info .tgt { display:inline-flex; align-items:center; gap:2px; }
  .info .tgt ha-icon { --mdc-icon-size:16px; }
  .badge { padding:2px 8px; border-radius:10px; font-weight:500; color:#fff; }
  .badge.on { background: var(--cm-on); } .badge.off { background: var(--cm-off); }
  .mode { text-transform: capitalize; }
  .warn { margin-top:10px; display:flex; align-items:center; gap:8px; padding:8px 10px; border-radius:8px;
          background: rgba(var(--rgb-warning-color, 255,166,0), .15); font-size:.88em; flex-wrap:wrap; }
  .warn span { flex:1; min-width:150px; }
  .tabs { display:grid; grid-template-columns: repeat(7,1fr); gap:4px; margin-top:14px; }
  .tab { position:relative; border:1px solid var(--divider-color); background:none; color: var(--primary-text-color);
         border-radius:8px; padding:6px 0; cursor:pointer; font: inherit; font-size:.9em; }
  .tab.today { font-weight:700; }
  .tab.sel { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  .tab .dot { position:absolute; top:3px; right:4px; width:6px; height:6px; border-radius:50%; background: var(--warning-color, orange); }
  .dayname { margin:10px 0 6px; font-size:.85em; color: var(--secondary-text-color); }
  .board { display:flex; gap:6px; }
  .scale { display:flex; flex-direction:column; justify-content:space-between; height:72px; }
  .scale span { width:6px; flex:1; border-radius:3px; } .scale .up { background: var(--cm-on); margin-bottom:2px; } .scale .down { background: var(--cm-off); margin-top:2px; }
  .pegwrap { position:relative; flex:1; padding-bottom:18px; }
  .pegs { display:grid; gap:2px; height:72px; touch-action:none; user-select:none; -webkit-user-select:none; cursor:pointer; }
  .peg { position:relative; background: var(--secondary-background-color, rgba(127,127,127,.12)); border-radius:3px; }
  .peg.h { box-shadow: -1px 0 0 0 var(--divider-color); }
  .peg.h6 { box-shadow: -2px 0 0 0 var(--secondary-text-color); }
  .knob { position:absolute; left:0; right:0; height:46%; bottom:0; border-radius:3px; background: var(--cm-off);
          opacity:.55; transition: bottom .12s ease, background .12s ease, opacity .12s; }
  .peg.on .knob { bottom:54%; background: var(--cm-on); opacity:1; }
  .peg:hover .knob { filter: brightness(1.15); }
  .now { position:absolute; top:-4px; height:80px; width:2px; background: var(--error-color, red); pointer-events:none; border-radius:1px; }
  .hours { position:absolute; left:0; right:0; bottom:0; height:16px; font-size:.72em; color: var(--secondary-text-color); }
  .hours span { position:absolute; transform: translateX(-50%); }
  .hours span:first-child { transform:none; } .hours span:last-child { transform: translateX(-100%); }
  .legend { display:flex; gap:14px; flex-wrap:wrap; font-size:.85em; margin-top:6px; align-items:center; }
  .legend span { display:inline-flex; align-items:center; gap:6px; }
  .legend .hint { margin-left:auto; color: var(--secondary-text-color); font-size:.92em; }
  .sw { width:12px; height:12px; border-radius:3px; display:inline-block; } .sw.on { background: var(--cm-on); } .sw.off { background: var(--cm-off); opacity:.7; }
  .tools { display:flex; gap:6px; margin-top:12px; flex-wrap:wrap; }
  .btn { font: inherit; font-size:.88em; border-radius:8px; padding:6px 12px; cursor:pointer; border:1px solid var(--divider-color);
         background:none; color: var(--primary-text-color); display:inline-flex; align-items:center; gap:6px; }
  .btn ha-icon { --mdc-icon-size:18px; }
  .btn.small { padding:4px 10px; }
  .btn.active { border-color: var(--primary-color); color: var(--primary-color); }
  .btn.primary { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .btn:disabled { opacity:.4; cursor:default; }
  .copypanel { margin-top:8px; padding:10px; border-radius:8px; border:1px dashed var(--divider-color); display:flex; flex-direction:column; gap:8px; }
  .copypanel .ct { font-size:.88em; }
  .chips { display:flex; gap:6px; flex-wrap:wrap; }
  .chip { font: inherit; font-size:.85em; padding:4px 10px; border-radius:14px; border:1px solid var(--divider-color); background:none; color: var(--primary-text-color); cursor:pointer; }
  .chip.sel { background: var(--primary-color); color: var(--text-primary-color,#fff); border-color: var(--primary-color); }
  .chip.alt { border-style:dashed; }
  .copypanel .btn { align-self:flex-end; }
  .week { margin-top:14px; display:flex; flex-direction:column; gap:4px; }
  .wtitle { font-size:.85em; color: var(--secondary-text-color); margin-bottom:2px; }
  .wrow { display:flex; align-items:center; gap:8px; cursor:pointer; border-radius:4px; padding:1px 2px; }
  .wrow.sel { background: rgba(var(--rgb-primary-color, 3,169,244), .12); }
  .wrow span { width:32px; font-size:.8em; color: var(--secondary-text-color); }
  .wrow .bar { position:relative; flex:1; height:10px; border-radius:5px; background: rgba(var(--rgb-primary-text-color, 127,127,127), .08); overflow:hidden; }
  .wrow .bar i { position:absolute; top:0; bottom:0; background: var(--cm-on); }
  .wrow .bar b { position:absolute; top:0; bottom:0; width:2px; background: var(--error-color, red); }
  .foot { display:flex; align-items:center; gap:8px; margin-top:14px; }
  .msg { flex:1; font-size:.85em; color: var(--secondary-text-color); }
  .msg.dirty { color: var(--warning-color, orange); } .msg.bad { color: var(--error-color); }
`;

if (!customElements.get("climate-manager-schedule-card")) {
  customElements.define("climate-manager-schedule-card", ClimateManagerScheduleCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "climate-manager-schedule-card",
    name: "Climate Manager – Cronotermostato",
    description: "Programma settimanale a cavalieri per i termostati Climate Manager",
    preview: false,
    documentationURL: "https://github.com/ichnusa82/climate_manager",
  });
  console.info(`%c CLIMATE-MANAGER-SCHEDULE-CARD %c ${CM_VERSION} `, "background:#ff8a00;color:#fff", "background:#333;color:#fff");
}
