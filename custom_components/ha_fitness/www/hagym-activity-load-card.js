(() => {
  if (!window.HAGymCardUtils) {
    const PERIOD_KEYS = new Set([
      "today",
      "yesterday",
      "this_week",
      "this_month",
      "this_quarter",
      "this_year",
      "last_7_days",
      "last_30_days",
      "last_12_weeks",
      "last_12_months",
    ]);

    const startOfDay = (date) =>
      new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);

    const addDays = (date, days) => {
      const next = new Date(date);
      next.setDate(next.getDate() + days);
      return next;
    };

    const addMonths = (date, months) => {
      const next = new Date(date);
      next.setMonth(next.getMonth() + months);
      return next;
    };

    const startOfWeek = (date) => {
      const next = startOfDay(date);
      const diff = (next.getDay() + 6) % 7;
      next.setDate(next.getDate() - diff);
      return next;
    };

    const startOfMonth = (date) =>
      new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);

    const startOfQuarter = (date) =>
      new Date(date.getFullYear(), Math.floor(date.getMonth() / 3) * 3, 1, 0, 0, 0, 0);

    const startOfYear = (date) => new Date(date.getFullYear(), 0, 1, 0, 0, 0, 0);

    const parseDate = (value) => {
      if (!value) return null;
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? null : parsed;
    };

    const normalizePeriod = (value) => {
      const normalized = String(value || "").trim().toLowerCase();
      return PERIOD_KEYS.has(normalized) ? normalized : "this_week";
    };

    const buildSelection = (periodKey, anchorDate, collectionKey) => {
      const key = normalizePeriod(periodKey);
      const anchor = parseDate(anchorDate) || new Date();
      let start;
      let end;
      let label;

      if (key === "today") {
        start = startOfDay(anchor);
        end = addDays(start, 1);
        label = "Heute";
      } else if (key === "yesterday") {
        end = startOfDay(anchor);
        start = addDays(end, -1);
        label = "Gestern";
      } else if (key === "this_week") {
        start = startOfWeek(anchor);
        end = addDays(start, 7);
        label = "Diese Woche";
      } else if (key === "this_month") {
        start = startOfMonth(anchor);
        end = addMonths(start, 1);
        label = "Dieser Monat";
      } else if (key === "this_quarter") {
        start = startOfQuarter(anchor);
        end = addMonths(start, 3);
        label = "Dieses Quartal";
      } else if (key === "this_year") {
        start = startOfYear(anchor);
        end = new Date(start.getFullYear() + 1, 0, 1, 0, 0, 0, 0);
        label = "Dieses Jahr";
      } else if (key === "last_7_days") {
        const todayStart = startOfDay(anchor);
        start = addDays(todayStart, -6);
        end = addDays(todayStart, 1);
        label = "Letzte 7 Tage";
      } else if (key === "last_30_days") {
        const todayStart = startOfDay(anchor);
        start = addDays(todayStart, -29);
        end = addDays(todayStart, 1);
        label = "Letzte 30 Tage";
      } else if (key === "last_12_weeks") {
        const weekStart = startOfWeek(anchor);
        start = addDays(weekStart, -77);
        end = addDays(weekStart, 7);
        label = "Letzte 12 Wochen";
      } else {
        const monthStart = startOfMonth(anchor);
        start = addMonths(monthStart, -11);
        end = addMonths(monthStart, 1);
        label = "Letzte 12 Monate";
      }

      return {
        period_key: key,
        anchor_date: anchor.toISOString(),
        label,
        start: start.toISOString(),
        end: end.toISOString(),
        collection_key: collectionKey,
      };
    };

    const escapeHtml = (value) =>
      String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const loadSelection = (collectionKey, defaultPeriod) => {
      const fallback = buildSelection(defaultPeriod || "this_week", new Date(), collectionKey);
      try {
        const raw = localStorage.getItem(`hagym-period-selection:${collectionKey}`);
        if (!raw) return fallback;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return fallback;
        return buildSelection(
          parsed.period_key || defaultPeriod || "this_week",
          parsed.anchor_date || new Date(),
          collectionKey
        );
      } catch (_err) {
        return fallback;
      }
    };

    const selectDaysForPeriod = (days, selection) => {
      const rows = Array.isArray(days) ? days : [];
      const start = parseDate(selection?.start);
      const end = parseDate(selection?.end);
      if (!start || !end) return [];
      return rows.filter((row) => {
        const dayStart = parseDate(row?.day_start);
        const dayEnd = parseDate(row?.day_end);
        if (!dayStart || !dayEnd) return false;
        return dayStart < end && dayEnd > start;
      });
    };

    window.HAGymCardUtils = {
      buildSelection,
      escapeHtml,
      loadSelection,
      parseDate,
      selectDaysForPeriod,
      startOfMonth,
      startOfWeek,
    };
  }

  const utils = window.HAGymCardUtils;
  const LOAD_SEGMENTS = [
    ["bodyweight_load_score", "Bodyweight", "#1f8ef1"],
    ["duration_load_score", "Duration", "#00a980"],
    ["hold_load_score", "Hold", "#6d5efc"],
    ["distance_load_score", "Distance", "#ff8a34"],
    ["cardio_load_score", "Cardio", "#db5461"],
    ["custom_load_score", "Custom", "#4a4f57"],
  ];

  class HAGymActivityLoadCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {
        title: "Activity Load",
        daily_metric_entity: null,
        collection_key: "hagym",
        group_by: "day",
        show_legend: true,
      };
      this._selection = null;
      this._onPeriodChanged = this._onPeriodChanged.bind(this);
      this._onStorage = this._onStorage.bind(this);
    }

    static getStubConfig() {
      return {
        type: "custom:hagym-activity-load-card",
        title: "Activity Load Ausdauer",
        daily_metric_entity: "sensor.ha_fitness_personal_daily_metric_statistics",
        collection_key: "hagym",
        group_by: "day",
      };
    }

    connectedCallback() {
      window.addEventListener("hagym-period-changed", this._onPeriodChanged);
      window.addEventListener("hagym-date-selection-changed", this._onPeriodChanged);
      window.addEventListener("storage", this._onStorage);
      this._selection = this._loadSelection();
      this._render();
    }

    disconnectedCallback() {
      window.removeEventListener("hagym-period-changed", this._onPeriodChanged);
      window.removeEventListener("hagym-date-selection-changed", this._onPeriodChanged);
      window.removeEventListener("storage", this._onStorage);
    }

    setConfig(config) {
      if (!config?.daily_metric_entity) {
        throw new Error("hagym-activity-load-card: daily_metric_entity is required");
      }

      const groupBy = ["day", "week", "month"].includes(config.group_by)
        ? config.group_by
        : "day";
      this._config = {
        title: config.title ? String(config.title) : "Activity Load",
        daily_metric_entity: String(config.daily_metric_entity),
        collection_key: config.collection_key ? String(config.collection_key) : "hagym",
        group_by: groupBy,
        show_legend: config.show_legend !== false,
      };
      this._selection = this._loadSelection();
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    getCardSize() {
      return 5;
    }

    _loadSelection() {
      return utils.loadSelection(this._config.collection_key, "this_week");
    }

    _onStorage(event) {
      if (event.key !== `hagym-period-selection:${this._config.collection_key}`) return;
      this._selection = this._loadSelection();
      this._render();
    }

    _onPeriodChanged(event) {
      if (
        event?.detail?.collection_key &&
        event.detail.collection_key !== this._config.collection_key
      ) {
        return;
      }
      this._selection = this._loadSelection();
      this._render();
    }

    _num(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    _keyForRow(row) {
      const date = utils.parseDate(row?.day_start) || utils.parseDate(row?.date);
      if (!date) return "unknown";
      if (this._config.group_by === "month") {
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      }
      if (this._config.group_by === "week") {
        const start = utils.startOfWeek(date);
        return start.toISOString();
      }
      return String(row?.date || date.toISOString().slice(0, 10));
    }

    _labelForGroup(key, row) {
      const date = utils.parseDate(row?.day_start) || utils.parseDate(row?.date);
      if (!date) return key;
      if (this._config.group_by === "month") {
        return `${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getFullYear()).slice(-2)}`;
      }
      if (this._config.group_by === "week") {
        const start = utils.startOfWeek(date);
        const weekNumber = this._weekNumber(start);
        return `KW ${String(weekNumber).padStart(2, "0")}`;
      }
      return String(row?.date || "").slice(5).replace("-", ".");
    }

    _weekNumber(date) {
      const utcDate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
      utcDate.setUTCDate(utcDate.getUTCDate() + 4 - (utcDate.getUTCDay() || 7));
      const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
      return Math.ceil(((utcDate - yearStart) / 86400000 + 1) / 7);
    }

    _groupRows(rows) {
      const grouped = new Map();
      for (const row of rows) {
        const key = this._keyForRow(row);
        const current =
          grouped.get(key) || {
            key,
            label: this._labelForGroup(key, row),
            total_minutes: 0,
            total_distance_km: 0,
            total_calories: 0,
            total_steps: 0,
            total_activity_load_score: 0,
          };
        for (const [metricKey] of LOAD_SEGMENTS) {
          current[metricKey] = this._num(current[metricKey]) + this._num(row?.[metricKey]);
        }
        current.total_minutes += this._num(row?.total_minutes);
        current.total_distance_km += this._num(row?.total_distance_km);
        current.total_calories += this._num(row?.total_calories);
        current.total_steps += this._num(row?.total_steps);
        current.total_activity_load_score += this._num(row?.total_activity_load_score);
        grouped.set(key, current);
      }
      return [...grouped.values()].sort((left, right) => left.key.localeCompare(right.key));
    }

    _summary(rows) {
      return rows.reduce(
        (sum, row) => ({
          total_activity_load_score:
            sum.total_activity_load_score + this._num(row.total_activity_load_score),
          total_minutes: sum.total_minutes + this._num(row.total_minutes),
          total_distance_km: sum.total_distance_km + this._num(row.total_distance_km),
          total_calories: sum.total_calories + this._num(row.total_calories),
          total_steps: sum.total_steps + this._num(row.total_steps),
        }),
        {
          total_activity_load_score: 0,
          total_minutes: 0,
          total_distance_km: 0,
          total_calories: 0,
          total_steps: 0,
        }
      );
    }

    _renderBars(rows) {
      if (!rows.length) {
        return `<div class="empty">Keine Daten im gewaehlten Zeitraum</div>`;
      }

      const max = Math.max(...rows.map((row) => this._num(row.total_activity_load_score)), 1);
      const labelEvery = rows.length > 16 ? Math.ceil(rows.length / 8) : 1;
      return `
        <div class="chart">
          ${rows
            .map((row, index) => {
              const segments = LOAD_SEGMENTS.map(([key, _label, color]) => {
                const total = this._num(row.total_activity_load_score);
                const value = this._num(row[key]);
                if (value <= 0 || total <= 0) return "";
                const height = (value / max) * 100;
                return `<div class="segment" style="height:${height}%; background:${color};" title="${utils.escapeHtml(
                  `${_label}: ${value.toFixed(1)}`
                )}"></div>`;
              }).join("");
              return `
                <div class="column">
                  <div class="stack">${segments}</div>
                  <div class="column-label">${index % labelEvery === 0 ? utils.escapeHtml(row.label) : ""}</div>
                </div>
              `;
            })
            .join("")}
        </div>
      `;
    }

    _renderLegend() {
      if (!this._config.show_legend) return "";
      return `
        <div class="legend">
          ${LOAD_SEGMENTS.map(
            ([, label, color]) =>
              `<span class="legend-chip"><span class="legend-dot" style="background:${color}"></span>${utils.escapeHtml(
                label
              )}</span>`
          ).join("")}
        </div>
      `;
    }

    _render() {
      if (!this.shadowRoot) return;
      const entity = this._hass?.states?.[this._config.daily_metric_entity];
      if (!entity) {
        this.shadowRoot.innerHTML = `
          ${this._style()}
          <ha-card>
            <div class="wrap">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="warning">Daily metric entity not found</div>
              <div class="muted"><code>${utils.escapeHtml(
                this._config.daily_metric_entity || ""
              )}</code></div>
            </div>
          </ha-card>
        `;
        return;
      }

      const days = Array.isArray(entity.attributes?.days) ? entity.attributes.days : null;
      if (!days) {
        this.shadowRoot.innerHTML = `
          ${this._style()}
          <ha-card>
            <div class="wrap">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="warning">Keine Tagesverlaufsdaten vorhanden</div>
            </div>
          </ha-card>
        `;
        return;
      }

      const selection = this._selection || this._loadSelection();
      const selectedRows = utils.selectDaysForPeriod(days, selection);
      const groupedRows = this._groupRows(selectedRows);
      const totals = this._summary(selectedRows);

      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="header">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="subtitle">${utils.escapeHtml(selection.label || "Diese Woche")}</div>
            </div>
            ${this._renderBars(groupedRows)}
            ${this._renderLegend()}
            <div class="tiles">
              <div class="tile"><span>Activity Load</span><strong>${totals.total_activity_load_score.toFixed(
                1
              )}</strong></div>
              <div class="tile"><span>Minuten</span><strong>${totals.total_minutes.toFixed(
                1
              )}</strong></div>
              <div class="tile"><span>Distanz</span><strong>${totals.total_distance_km.toFixed(
                2
              )} km</strong></div>
              <div class="tile"><span>Kalorien</span><strong>${totals.total_calories.toFixed(
                0
              )}</strong></div>
              <div class="tile"><span>Schritte</span><strong>${totals.total_steps.toFixed(
                0
              )}</strong></div>
            </div>
          </div>
        </ha-card>
      `;
    }

    _style() {
      return `
        <style>
          :host {
            display: block;
          }

          ha-card {
            border-radius: 18px;
            background:
              radial-gradient(circle at top left, rgba(0, 169, 128, 0.14), transparent 38%),
              var(--ha-card-background, var(--card-background-color, #fff));
          }

          .wrap {
            padding: 16px;
            color: var(--primary-text-color);
          }

          .header {
            margin-bottom: 14px;
          }

          .title {
            font-size: 1.02rem;
            font-weight: 700;
          }

          .subtitle,
          .muted {
            margin-top: 4px;
            font-size: 0.82rem;
            color: var(--secondary-text-color);
          }

          .chart {
            min-height: 180px;
            display: flex;
            align-items: flex-end;
            gap: 8px;
            padding: 8px 0 6px;
          }

          .column {
            flex: 1 1 0;
            min-width: 0;
            display: grid;
            gap: 8px;
            align-items: end;
          }

          .stack {
            height: 140px;
            display: flex;
            flex-direction: column-reverse;
            gap: 2px;
            border-radius: 12px;
            overflow: hidden;
            background: color-mix(in srgb, var(--primary-color) 8%, transparent);
          }

          .segment {
            width: 100%;
            min-height: 0;
          }

          .column-label {
            text-align: center;
            font-size: 0.72rem;
            color: var(--secondary-text-color);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .legend {
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
          }

          .legend-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            border-radius: 999px;
            background: color-mix(in srgb, var(--primary-color) 8%, transparent);
            font-size: 0.78rem;
          }

          .legend-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
          }

          .tiles {
            margin-top: 14px;
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
          }

          .tile {
            padding: 10px;
            border-radius: 14px;
            background: color-mix(in srgb, var(--secondary-text-color) 8%, transparent);
          }

          .tile span {
            display: block;
            margin-bottom: 4px;
            font-size: 0.72rem;
            color: var(--secondary-text-color);
          }

          .tile strong {
            font-size: 0.96rem;
            line-height: 1.2;
          }

          .warning,
          .empty {
            padding: 12px 14px;
            border-radius: 14px;
            background: color-mix(in srgb, var(--secondary-text-color) 10%, transparent);
            color: var(--secondary-text-color);
          }

          @media (max-width: 720px) {
            .tiles {
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }
          }
        </style>
      `;
    }
  }

  if (!customElements.get("hagym-activity-load-card")) {
    customElements.define("hagym-activity-load-card", HAGymActivityLoadCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "hagym-activity-load-card")) {
    window.customCards.push({
      type: "hagym-activity-load-card",
      name: "HAGym Activity Load Card",
      description: "Selected-period activity load visualization using daily metric statistics",
      preview: true,
    });
  }
})();
