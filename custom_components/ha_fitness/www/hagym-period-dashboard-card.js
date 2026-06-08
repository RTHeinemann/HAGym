const utils = window.HAGymCardUtils;
let missingUtilsLogged = false;
const missingUtilsMessage =
  "HAGymCardUtils missing. Add /hagym_static/hagym-card-utils.js as a Lovelace resource before HAGym cards.";
const ensureUtils = () => {
  if (utils) return true;
  if (!missingUtilsLogged) {
    console.error(missingUtilsMessage);
    missingUtilsLogged = true;
  }
  return false;
};

class HAGymPeriodDashboardCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {
      daily_metric_entity: null,
      metric_history_entity: "",
      volume_history_entity: null,
      collection_key: "hagym",
      title: "HAGym",
      show_embedded_date_selection: true,
    };
    this._selection = null;
    this._visibleMetrics = new Set();
    this._onPeriodChanged = this._onPeriodChanged.bind(this);
    this._onStorage = this._onStorage.bind(this);
  }

  static getStubConfig(hass) {
    const collectionKey = "hagym";
    const dailyMetricEntity =
      window.HAGymCardUtils?.defaultDailyMetricEntity?.(
        hass,
        collectionKey,
        "sensor.hagym_hagym_personliche_tagesstatistik"
      ) || "sensor.hagym_hagym_personliche_tagesstatistik";
    return {
      type: "custom:hagym-period-dashboard-card",
      daily_metric_entity: dailyMetricEntity,
      metric_history_entity: "sensor.ha_fitness_personal_weekly_metric_history",
      volume_history_entity: "sensor.ha_fitness_personal_weekly_volume_history",
      collection_key: collectionKey,
      show_embedded_date_selection: true,
    };
  }

  connectedCallback() {
    if (!ensureUtils()) {
      this._renderMissingUtils();
      return;
    }
    window.addEventListener("hagym-period-changed", this._onPeriodChanged);
    window.addEventListener("hagym-date-selection-changed", this._onPeriodChanged);
    window.addEventListener("storage", this._onStorage);
    this._selection = this._loadSelection();
    this._visibleMetrics = this._loadVisibleMetrics();
    this._render();
  }

  disconnectedCallback() {
    window.removeEventListener("hagym-period-changed", this._onPeriodChanged);
    window.removeEventListener("hagym-date-selection-changed", this._onPeriodChanged);
    window.removeEventListener("storage", this._onStorage);
  }

  setConfig(config) {
    if (!config || (!config.daily_metric_entity && !config.metric_history_entity)) {
      throw new Error(
        "hagym-period-dashboard-card: daily_metric_entity or metric_history_entity is required"
      );
    }
    this._config = {
      daily_metric_entity: config.daily_metric_entity
        ? String(config.daily_metric_entity)
        : null,
      metric_history_entity: config.metric_history_entity
        ? String(config.metric_history_entity)
        : null,
      volume_history_entity: config.volume_history_entity
        ? String(config.volume_history_entity)
        : null,
      collection_key: config.collection_key ? String(config.collection_key) : "hagym",
      title: config.title ? String(config.title) : "HAGym",
      show_embedded_date_selection:
        config.show_embedded_date_selection !== false,
    };
    this._selection = ensureUtils() ? this._loadSelection() : null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  _renderMissingUtils() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = `
      ${this._style()}
      <ha-card>
        <div class="wrap">
          <div class="title">${this._escape(this._config?.title || "HAGym")}</div>
          <div class="warn">${missingUtilsMessage}</div>
        </div>
      </ha-card>
    `;
  }

  _onStorage(ev) {
    if (!ensureUtils()) {
      this._renderMissingUtils();
      return;
    }
    if (ev.key !== this._storageKey()) return;
    this._selection = this._loadSelection();
    this._render();
  }

  _onPeriodChanged(ev) {
    if (!ensureUtils()) {
      this._renderMissingUtils();
      return;
    }
    const detail = ev?.detail;
    if (
      detail &&
      detail.collection_key &&
      detail.collection_key !== this._config.collection_key
    ) {
      return;
    }
    this._selection = this._loadSelection();
    this._render();
  }

  _storageKey() {
    return ensureUtils()
      ? utils.storageKey(this._config.collection_key)
      : `hagym-period-selection:${this._config.collection_key}`;
  }

  _metricKey() {
    return `hagym-visible-metrics:${this._config.collection_key}`;
  }

  _loadVisibleMetrics() {
    try {
      const raw = localStorage.getItem(this._metricKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return new Set(parsed);
      }
    } catch (_err) {}
    return null;
  }

  _saveVisibleMetrics(set) {
    try {
      localStorage.setItem(this._metricKey(), JSON.stringify([...set]));
    } catch (_err) {}
  }

  _allMetricKeys = ["bodyweight_load_score", "duration_load_score", "hold_load_score", "distance_load_score", "cardio_load_score", "custom_load_score"];

  _toggleMetric(key) {
    if (!this._visibleMetrics.size) {
      this._visibleMetrics = new Set(this._allMetricKeys);
    }
    if (this._visibleMetrics.has(key)) {
      this._visibleMetrics.delete(key);
      if (this._visibleMetrics.size === 0) {
        this._visibleMetrics = new Set(this._allMetricKeys);
      }
    } else {
      this._visibleMetrics.add(key);
    }
    this._saveVisibleMetrics(this._visibleMetrics);
    this._render();
  }

  _areMetricsVisible() {
    return this._visibleMetrics.size > 0;
  }

  _metricName(k) {
    const map = {
      bodyweight_load_score: "Bodyweight",
      duration_load_score: "Duration",
      hold_load_score: "Hold",
      distance_load_score: "Distance",
      cardio_load_score: "Cardio",
      custom_load_score: "Custom",
    };
    return map[k] || k;
  }

  _loadSelection() {
    if (!ensureUtils()) return null;
    return utils.loadSelection(
      this._config.collection_key,
      "this_week",
      document.documentElement.lang || navigator.language
    );
  }

  _render() {
    if (!this.shadowRoot) return;
    if (!ensureUtils()) {
      this._renderMissingUtils();
      return;
    }
    const dailyState = this._config.daily_metric_entity
      ? this._hass?.states?.[this._config.daily_metric_entity]
      : null;
    const metricState = this._config.metric_history_entity
      ? this._hass?.states?.[this._config.metric_history_entity]
      : null;
    const volumeState = this._config.volume_history_entity
      ? this._hass?.states?.[this._config.volume_history_entity]
      : null;

    const dailyDays = Array.isArray(dailyState?.attributes?.days)
      ? dailyState.attributes.days
      : [];
    const metricWeeks = Array.isArray(metricState?.attributes?.weeks)
      ? metricState.attributes.weeks
      : [];

    const hasDaily = !!dailyState && dailyDays.length > 0;
    const hasWeekly = !!metricState && metricWeeks.length > 0;

    if (!hasDaily && !hasWeekly) {
      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="title">${this._escape(this._config.title)}</div>
            ${this._embeddedSelector()}
            <div class="warn">Metric history entity not found</div>
            <div class="muted"><code>${this._escape(
              this._config.daily_metric_entity || this._config.metric_history_entity || ""
            )}</code></div>
          </div>
        </ha-card>
      `;
      return;
    }

    const period = this._selection || this._defaultThisWeekSelection();
    const selectedRows = hasDaily
      ? this._selectDaysForPeriod(dailyDays, period)
      : this._selectWeeksForPeriod(metricWeeks, period);
    const approxNote = hasDaily ? "" : this._approximationNote(period.period_key);
    const noDailyNote = hasDaily ? "" : this._dailyUnavailableNote(period.period_key);
    const activity = this._aggregateActivity(selectedRows);
    const strength = this._aggregateStrength(
      selectedRows,
      Array.isArray(volumeState?.attributes?.weeks) ? volumeState.attributes.weeks : []
    );
    const cardio = this._aggregateCardio(selectedRows);
    const totals = this._aggregateTotals(selectedRows, activity);

    // Sync visible metrics for next render
    if (this._visibleMetrics.size === 0) {
      this._visibleMetrics = new Set(this._allMetricKeys);
    }

    this.shadowRoot.innerHTML = `
      ${this._style()}
      <ha-card>
        <div class="wrap">
          <div class="title">${this._escape(this._config.title)}</div>
          <div class="subline">${this._escape(period.label || "Diese Woche")}</div>
          ${this._embeddedSelector()}
          ${noDailyNote ? `<div class="note">${this._escape(noDailyNote)}</div>` : ""}
          ${approxNote ? `<div class="note">${this._escape(approxNote)}</div>` : ""}

          <div class="section">
            <div class="section-title">Activity Load</div>
            ${this._renderActivityBars(selectedRows)}
            ${this._renderMetricChips(activity)}
          </div>

          <div class="section">
            <div class="section-title">Strength Volume</div>
            <div class="grid two">
              <div class="tile"><span>Strength Volume (kg)</span><strong>${this._fmt(
                strength.strength_volume_kg,
                1
              )}</strong></div>
              <div class="tile"><span>Total Strength (kg)</span><strong>${this._fmt(
                strength.total_strength_volume_kg,
                1
              )}</strong></div>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Cardio Summary</div>
            <div class="grid three">
              <div class="tile"><span>Minuten</span><strong>${this._fmt(
                cardio.cardio_minutes,
                1
              )}</strong></div>
              <div class="tile"><span>km</span><strong>${this._fmt(
                cardio.cardio_km,
                2
              )}</strong></div>
              <div class="tile"><span>Kalorien</span><strong>${this._fmt(
                cardio.cardio_calories,
                0
              )}</strong></div>
              <div class="tile"><span>Schritte</span><strong>${this._fmt(
                cardio.cardio_steps,
                0
              )}</strong></div>
              <div class="tile"><span>Avg HR</span><strong>${this._fmt(
                cardio.cardio_avg_heart_rate,
                0
              )}</strong></div>
              <div class="tile"><span>Max HR</span><strong>${this._fmt(
                cardio.cardio_max_heart_rate,
                0
              )}</strong></div>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Total Summary</div>
            <div class="grid three">
              <div class="tile"><span>Minuten</span><strong>${this._fmt(
                totals.total_minutes,
                1
              )}</strong></div>
              <div class="tile"><span>Distanz (km)</span><strong>${this._fmt(
                totals.total_distance_km,
                2
              )}</strong></div>
              <div class="tile"><span>Activity Load</span><strong>${this._fmt(
                totals.total_activity_load_score,
                1
              )}</strong></div>
              <div class="tile"><span>Aktive Tage</span><strong>${this._fmt(
                totals.active_days,
                0
              )}</strong></div>
              <div class="tile"><span>Workouts</span><strong>${this._fmt(
                totals.workout_count,
                0
              )}</strong></div>
              <div class="tile"><span>Entries</span><strong>${this._fmt(
                totals.entry_count,
                0
              )}</strong></div>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    this._configureEmbeddedSelector();
  }

  _embeddedSelector() {
    if (!this._config.show_embedded_date_selection) return "";
    return `<div class="embedded"><hagym-date-selection></hagym-date-selection></div>`;
  }

  _configureEmbeddedSelector() {
    const selector = this.shadowRoot?.querySelector("hagym-date-selection");
    if (!selector || typeof selector.setConfig !== "function") {
      return;
    }
    selector.setConfig({
      type: "custom:hagym-date-selection",
      collection_key: this._config.collection_key,
      default_period: this._selection?.period_key || "this_week",
      compact: true,
    });
  }

  _selectWeeksForPeriod(weeks, period) {
    const periodKey = String(period?.period_key || "this_week");
    const start = this._parseDate(period?.start);
    const end = this._parseDate(period?.end);
    if (!start || !end) return [];

    if (periodKey === "last_12_weeks") {
      return weeks;
    }
    if (periodKey === "today" || periodKey === "yesterday") {
      return [];
    }
    return weeks.filter((w) => {
      const ws = this._parseDate(w.week_start);
      const we = this._parseDate(w.week_end);
      if (!ws || !we) return false;
      return ws < end && we > start;
    });
  }

  _selectDaysForPeriod(days, period) {
    const rows = Array.isArray(days) ? days : [];
    const start = this._parseDate(period?.start);
    const end = this._parseDate(period?.end);
    if (!start || !end) return [];

    return rows.filter((d) => {
      const ds = this._parseDate(d.day_start);
      const de = this._parseDate(d.day_end);
      if (!ds || !de) return false;
      return ds < end && de > start;
    });
  }

  _approximationNote(periodKey) {
    if (periodKey === "last_7_days" || periodKey === "last_30_days") {
      return "Aus Wochenwerten approximiert";
    }
    return "";
  }

  _dailyUnavailableNote(periodKey) {
    if (periodKey === "today" || periodKey === "yesterday") {
      return "Keine Tagesdaten verfugbar";
    }
    return "";
  }

  _aggregateActivity(weeks) {
    const out = {
      bodyweight_load_score: 0,
      duration_load_score: 0,
      hold_load_score: 0,
      distance_load_score: 0,
      cardio_load_score: 0,
      custom_load_score: 0,
    };
    for (const w of weeks) {
      out.bodyweight_load_score += this._num(w.bodyweight_load_score);
      out.duration_load_score += this._num(w.duration_load_score);
      out.hold_load_score += this._num(w.hold_load_score);
      out.distance_load_score += this._num(w.distance_load_score);
      out.cardio_load_score += this._num(w.cardio_load_score);
      out.custom_load_score += this._num(w.custom_load_score);
    }
    return out;
  }

  _aggregateStrength(weeks, volumeWeeks) {
    let strengthVolume = 0;
    let totalStrength = 0;
    const byStart = new Map(
      (Array.isArray(volumeWeeks) ? volumeWeeks : []).map((w) => [
        String(w.week_start || ""),
        this._num(w.total_volume),
      ])
    );
    for (const w of weeks) {
      const cur = this._num(w.strength_volume_kg);
      const fallback = byStart.get(String(w.week_start || "")) || 0;
      strengthVolume += cur || fallback;
      totalStrength += this._num(w.total_strength_volume_kg) || cur || fallback;
    }
    return {
      strength_volume_kg: strengthVolume,
      total_strength_volume_kg: totalStrength,
    };
  }

  _aggregateCardio(weeks) {
    const out = {
      cardio_minutes: 0,
      cardio_km: 0,
      cardio_calories: 0,
      cardio_steps: 0,
      cardio_avg_heart_rate: 0,
      cardio_max_heart_rate: 0,
    };
    if (!weeks.length) return out;
    let hrSum = 0;
    let hrCount = 0;
    for (const w of weeks) {
      out.cardio_minutes += this._num(w.cardio_minutes);
      out.cardio_km += this._num(w.cardio_km);
      out.cardio_calories += this._num(w.cardio_calories);
      out.cardio_steps += this._num(w.cardio_steps);
      const avg = this._num(w.cardio_avg_heart_rate);
      if (avg > 0) {
        hrSum += avg;
        hrCount += 1;
      }
      out.cardio_max_heart_rate = Math.max(
        out.cardio_max_heart_rate,
        this._num(w.cardio_max_heart_rate)
      );
    }
    out.cardio_avg_heart_rate = hrCount > 0 ? hrSum / hrCount : 0;
    return out;
  }

  _aggregateTotals(weeks, activity) {
    const out = {
      total_minutes: 0,
      total_distance_km: 0,
      total_activity_load_score: 0,
      active_days: 0,
      workout_count: 0,
      entry_count: 0,
    };
    for (const w of weeks) {
      out.total_minutes += this._num(w.total_minutes);
      out.total_distance_km += this._num(w.total_distance_km);
      out.active_days += this._num(w.active_days);
      out.workout_count += this._num(w.workout_count);
      out.entry_count += this._num(w.entry_count);
    }
    out.total_activity_load_score =
      activity.bodyweight_load_score +
      activity.duration_load_score +
      activity.hold_load_score +
      activity.distance_load_score +
      activity.cardio_load_score +
      activity.custom_load_score;
    return out;
  }

  _renderMetricChips(activity) {
    if (!this._areMetricsVisible()) {
      return "";
    }
    const allKeys = ["bodyweight_load_score", "duration_load_score", "hold_load_score", "distance_load_score", "cardio_load_score", "custom_load_score"];
    const colors = {
      bodyweight_load_score: "#1976d2",
      duration_load_score: "#26a69a",
      hold_load_score: "#8e24aa",
      distance_load_score: "#fb8c00",
      cardio_load_score: "#e53935",
      custom_load_score: "#607d8b",
    };
    const anyVisible = this._visibleMetrics.size > 0;
    const chips = allKeys.map((k) => {
      const color = colors[k];
      const name = this._metricName(k);
      const active = anyVisible && this._visibleMetrics.has(k);
      const val = this._num(activity[k]);
      const muted = !active ? "opacity:0.4;" : "";
      return `<span class="chip metric-chip${active ? "" : " dimmed"}" data-metric="${k}" style="${muted}"><span class="dot" style="background:${color}"></span>${name}<span class="metric-val">${val > 0 ? this._fmt(val, 0) : ""}</span></span>`;
    }).join("");
    return `<div class="legend metrics-legend">${chips}</div>`;
  }

  _renderActivityBars(weeks) {
    if (!weeks.length) {
      return `<div class="warn-inline">Keine Daten im gewahlten Zeitraum</div>`;
    }
    const metricDefs = [
      ["bodyweight_load_score", "#1976d2", "Bodyweight"],
      ["duration_load_score", "#26a69a", "Duration"],
      ["hold_load_score", "#8e24aa", "Hold"],
      ["distance_load_score", "#fb8c00", "Distance"],
      ["cardio_load_score", "#e53935", "Cardio"],
      ["custom_load_score", "#607d8b", "Custom"],
    ];
    const activeKeys = this._areMetricsVisible() && this._visibleMetrics.size > 0
      ? [...this._visibleMetrics].filter((k) => {
          const w = weeks[0];
          return w && this._num(w[k]) > 0;
        })
      : metricDefs.map((d) => d[0]);
    const totals = weeks.map((w) =>
      metricDefs.reduce((sum, [k]) => sum + this._num(w[k]), 0)
    );
    const max = Math.max(1, ...totals);
    const bars = weeks
      .map((w) => {
        const weekLabel = this._escape(w.week_label || "");
        const segs = metricDefs
          .map(([k, color, name]) => {
            if (!activeKeys.includes(k)) return "";
            const v = this._num(w[k]);
            if (v <= 0) return "";
            const height = (v / max) * 100;
            return `<div class="seg" style="height:${height}%;background:${color}" title="${name}: ${this._fmt(
              v,
              1
            )}"></div>`;
          })
          .join("");
        return `<div class="bar-wrap"><div class="bar">${segs}</div><div class="bar-label">${weekLabel}</div></div>`;
      })
      .join("");

    return `<div class="bars">${bars}</div>`;
  }

  _startOfWeek(date) {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diff = (d.getDay() + 6) % 7;
    d.setDate(d.getDate() - diff);
    d.setHours(0, 0, 0, 0);
    return d;
  }

  _addDays(date, days) {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    return d;
  }

  _parseDate(v) {
    if (!v) return null;
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  _num(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  _fmt(v, d) {
    return this._num(v).toFixed(d);
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  _style() {
    return `
      <style>
        :host { display:block; }
        ha-card { border-radius:14px; }
        .wrap { padding:16px; color:var(--primary-text-color); }
        .title { font-size:22px; font-weight:700; line-height:1.2; }
        .subline { margin-top:4px; font-size:13px; color:var(--secondary-text-color); }
        .embedded { margin-top:10px; }
        .section { margin-top:14px; }
        .section-title { font-size:14px; font-weight:700; margin-bottom:8px; }
        .grid { display:grid; gap:8px; }
        .grid.two { grid-template-columns: repeat(2,minmax(0,1fr)); }
        .grid.three { grid-template-columns: repeat(3,minmax(0,1fr)); }
        .tile { background:var(--secondary-background-color); border-radius:10px; padding:8px; }
        .tile span { display:block; font-size:11px; color:var(--secondary-text-color); }
        .tile strong { font-size:16px; line-height:1.2; }
        .bars { min-height:110px; display:flex; align-items:flex-end; gap:8px; }
        .bar-wrap { width:30px; display:grid; gap:4px; }
        .bar {
          height:96px; border-radius:8px; overflow:hidden; display:flex; flex-direction:column-reverse;
          background:var(--secondary-background-color);
        }
        .bar-label {
          font-size:10px; color:var(--secondary-text-color);
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:center;
        }
        .legend { margin-top:8px; display:flex; flex-wrap:wrap; gap:6px; }
        .chip {
          font-size:11px; padding:4px 8px; border-radius:12px;
          background:var(--secondary-background-color); display:inline-flex; gap:6px; align-items:center;
        }
        .dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
        .warn, .warn-inline {
          border-radius:10px; padding:10px 12px; background:var(--secondary-background-color);
          color:var(--secondary-text-color);
        }
        .warn { margin-top:10px; }
        .note {
          margin-top:8px; font-size:12px; color:var(--secondary-text-color);
          background:var(--secondary-background-color); border-radius:8px; padding:6px 8px;
        }
        .muted { margin-top:6px; font-size:12px; color:var(--secondary-text-color); }
        @media (max-width: 520px) {
          .grid.three { grid-template-columns: repeat(2,minmax(0,1fr)); }
        }
      </style>
    `;
  }
}

if (!customElements.get("hagym-period-dashboard-card")) {
  customElements.define("hagym-period-dashboard-card", HAGymPeriodDashboardCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "hagym-period-dashboard-card")) {
  window.customCards.push({
    type: "hagym-period-dashboard-card",
    name: "HAGym Period Dashboard Card",
    description: "Legacy all-in-one dashboard card. Prefer modular cards for new dashboards.",
    preview: true,
  });
}
