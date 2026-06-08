(() => {
  if (!window.HAGymCardUtils) {
    const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;
    const PERIOD_KEYS = new Set([
      "today",
      "yesterday",
      "this_week",
      "this_month",
      "this_quarter",
      "this_year",
      "last_7_days",
      "last_30_days",
      "last_365_days",
      "last_12_weeks",
      "last_12_months",
      "custom_range",
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
      if (value instanceof Date) {
        return Number.isNaN(value.getTime()) ? null : new Date(value);
      }
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? null : parsed;
    };

    const parseDateOnly = (value) => {
      if (!value || !DATE_ONLY_RE.test(String(value))) return null;
      const [year, month, day] = String(value).split("-").map(Number);
      return new Date(year, month - 1, day, 0, 0, 0, 0);
    };

    const toDateOnly = (value) => {
      const date = parseDate(value);
      if (!date) return null;
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
        date.getDate()
      ).padStart(2, "0")}`;
    };

    const formatCustomRangeLabel = (start, end) => {
      const formatter = new Intl.DateTimeFormat(document.documentElement.lang || navigator.language, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
      const from = formatter.format(start);
      const to = formatter.format(end);
      return from === to ? from : `${from} - ${to}`;
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
      } else if (key === "last_365_days") {
        const todayStart = startOfDay(anchor);
        start = addDays(todayStart, -364);
        end = addDays(todayStart, 1);
        label = "Letzte 365 Tage";
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
        type: key,
        anchor_date: anchor.toISOString(),
        label,
        start: start.toISOString(),
        end: end.toISOString(),
        collection_key: collectionKey,
      };
    };

    const buildCustomRangeSelection = (startValue, endValue, collectionKey) => {
      const start = parseDateOnly(startValue) || startOfDay(parseDate(startValue) || new Date());
      const end = parseDateOnly(endValue) || start;
      const orderedStart = start <= end ? start : end;
      const orderedEnd = start <= end ? end : start;
      return {
        period_key: "custom_range",
        type: "custom_range",
        anchor_date: orderedStart.toISOString(),
        label: formatCustomRangeLabel(orderedStart, orderedEnd),
        start: orderedStart.toISOString(),
        end: addDays(orderedEnd, 1).toISOString(),
        start_date: toDateOnly(orderedStart),
        end_date: toDateOnly(orderedEnd),
        collection_key: collectionKey,
      };
    };

    const escapeHtml = (value) =>
      String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const selectionStartDate = (selection) => {
      const startDate = parseDateOnly(selection?.start_date);
      if (startDate) return startDate;
      if (typeof selection?.start === "string" && DATE_ONLY_RE.test(selection.start)) {
        return parseDateOnly(selection.start);
      }
      return parseDate(selection?.start);
    };

    const selectionEndExclusive = (selection) => {
      const endDate = parseDateOnly(selection?.end_date);
      if (endDate) return addDays(endDate, 1);
      if (typeof selection?.end === "string" && DATE_ONLY_RE.test(selection.end)) {
        return addDays(parseDateOnly(selection.end), 1);
      }
      return parseDate(selection?.end);
    };

    const loadSelection = (collectionKey, defaultPeriod) => {
      const fallback = buildSelection(defaultPeriod || "this_week", new Date(), collectionKey);
      try {
        const raw = localStorage.getItem(`hagym-period-selection:${collectionKey}`);
        if (!raw) return fallback;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return fallback;
        const key = normalizePeriod(parsed.period_key || parsed.type || defaultPeriod || "this_week");
        if (key === "custom_range") {
          const startDate =
            parsed.start_date ||
            (typeof parsed.start === "string" && DATE_ONLY_RE.test(parsed.start)
              ? parsed.start
              : toDateOnly(parsed.start));
          const endDate =
            parsed.end_date ||
            (typeof parsed.end === "string" && DATE_ONLY_RE.test(parsed.end)
              ? parsed.end
              : toDateOnly(addDays(parseDate(parsed.end) || new Date(), -1)));
          if (startDate && endDate) {
            return buildCustomRangeSelection(startDate, endDate, collectionKey);
          }
          return fallback;
        }
        return buildSelection(key, parsed.anchor_date || new Date(), collectionKey);
      } catch (_err) {
        return fallback;
      }
    };

    const selectDaysForPeriod = (days, selection) => {
      const rows = Array.isArray(days) ? days : [];
      const start = selectionStartDate(selection);
      const end = selectionEndExclusive(selection);
      if (!start || !end) return [];
      return rows.filter((row) => {
        const dayStart = parseDate(row?.day_start);
        const dayEnd = parseDate(row?.day_end);
        if (!dayStart || !dayEnd) return false;
        return dayStart < end && dayEnd > start;
      });
    };

    window.HAGymCardUtils = {
      buildCustomRangeSelection,
      buildSelection,
      escapeHtml,
      loadSelection,
      parseDate,
      parseDateOnly,
      selectDaysForPeriod,
      startOfDay,
      startOfMonth,
      startOfWeek,
      toDateOnly,
    };
  }

  const utils = window.HAGymCardUtils;
  const LOAD_SEGMENTS = [
    { id: "bodyweight", metricKey: "bodyweight_load_score", label: "Bodyweight", color: "#1f8ef1" },
    { id: "duration", metricKey: "duration_load_score", label: "Duration", color: "#00a980" },
    { id: "hold", metricKey: "hold_load_score", label: "Hold", color: "#6d5efc" },
    { id: "distance", metricKey: "distance_load_score", label: "Distance", color: "#ff8a34" },
    { id: "cardio", metricKey: "cardio_load_score", label: "Cardio", color: "#db5461" },
    { id: "custom", metricKey: "custom_load_score", label: "Custom", color: "#4a4f57" },
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
        interactive_legend: true,
        persist_legend_state: false,
      };
      this._selection = null;
      this._disabledSeries = new Set();
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
        interactive_legend: true,
        persist_legend_state: false,
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
      const nextCollectionKey = config.collection_key ? String(config.collection_key) : "hagym";
      const nextPersistLegendState = config.persist_legend_state === true;
      const identityChanged =
        this._config.collection_key !== nextCollectionKey || this._config.group_by !== groupBy;
      const persistModeChanged = this._config.persist_legend_state !== nextPersistLegendState;
      this._config = {
        title: config.title ? String(config.title) : "Activity Load",
        daily_metric_entity: String(config.daily_metric_entity),
        collection_key: nextCollectionKey,
        group_by: groupBy,
        show_legend: config.show_legend !== false,
        interactive_legend: config.interactive_legend !== false,
        persist_legend_state: nextPersistLegendState,
      };
      if (identityChanged || persistModeChanged) {
        this._disabledSeries = this._loadDisabledSeries();
      }
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

    _legendStorageKey() {
      return `hagym-activity-load-disabled:${this._config.collection_key}:${this._config.group_by}`;
    }

    _loadDisabledSeries() {
      if (!this._config.persist_legend_state) {
        return new Set();
      }
      try {
        const raw = localStorage.getItem(this._legendStorageKey());
        if (!raw) return new Set();
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return new Set();
        return new Set(parsed.map((value) => String(value)));
      } catch (_err) {
        return new Set();
      }
    }

    _saveDisabledSeries() {
      if (!this._config.persist_legend_state) return;
      try {
        localStorage.setItem(
          this._legendStorageKey(),
          JSON.stringify([...this._disabledSeries].sort())
        );
      } catch (_err) {
        // ignore storage failures
      }
    }

    _toggleSeries(seriesKey) {
      const key = String(seriesKey || "").trim();
      if (!key || !this._config.interactive_legend) return;
      if (this._disabledSeries.has(key)) {
        this._disabledSeries.delete(key);
      } else {
        this._disabledSeries.add(key);
      }
      this._saveDisabledSeries();
      this._render();
    }

    _allSeries() {
      return LOAD_SEGMENTS;
    }

    _activeSeries() {
      return this._allSeries().filter((segment) => !this._disabledSeries.has(segment.id));
    }

    _onStorage(event) {
      if (event.key === `hagym-period-selection:${this._config.collection_key}`) {
        this._selection = this._loadSelection();
        this._render();
        return;
      }
      if (this._config.persist_legend_state && event.key === this._legendStorageKey()) {
        this._disabledSeries = this._loadDisabledSeries();
        this._render();
      }
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

    _groupRows(rows, activeSeries) {
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
        for (const segment of this._allSeries()) {
          const metricKey = segment.metricKey;
          current[metricKey] = this._num(current[metricKey]) + this._num(row?.[metricKey]);
        }
        current.total_minutes += activeSeries.some((segment) => segment.id === "duration")
          ? this._num(row?.total_minutes)
          : 0;
        current.total_distance_km += activeSeries.some((segment) => segment.id === "distance")
          ? this._num(row?.total_distance_km)
          : 0;
        current.total_calories += activeSeries.some((segment) => segment.id === "cardio")
          ? this._num(row?.total_calories)
          : 0;
        current.total_steps += activeSeries.some((segment) => segment.id === "cardio")
          ? this._num(row?.total_steps)
          : 0;
        current.total_activity_load_score += activeSeries.reduce(
          (sum, segment) => sum + this._num(row?.[segment.metricKey]),
          0
        );
        grouped.set(key, current);
      }
      return [...grouped.values()].sort((left, right) => left.key.localeCompare(right.key));
    }

    _summary(rows, activeSeries) {
      const durationActive = activeSeries.some((segment) => segment.id === "duration");
      const distanceActive = activeSeries.some((segment) => segment.id === "distance");
      const cardioActive = activeSeries.some((segment) => segment.id === "cardio");
      return rows.reduce(
        (sum, row) => ({
          total_activity_load_score: sum.total_activity_load_score + activeSeries.reduce(
            (metricSum, segment) => metricSum + this._num(row[segment.metricKey]),
            0
          ),
          total_minutes: sum.total_minutes + (durationActive ? this._num(row.total_minutes) : 0),
          total_distance_km:
            sum.total_distance_km + (distanceActive ? this._num(row.total_distance_km) : 0),
          total_calories: sum.total_calories + (cardioActive ? this._num(row.total_calories) : 0),
          total_steps: sum.total_steps + (cardioActive ? this._num(row.total_steps) : 0),
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

    _renderBars(rows, activeSeries) {
      if (!rows.length) {
        return `<div class="empty">Keine Daten im gewaehlten Zeitraum</div>`;
      }

      if (this._allSeries().length > 0 && activeSeries.length === 0) {
        return `<div class="empty">Alle Reihen ausgeblendet</div>`;
      }

      const max = Math.max(...rows.map((row) => this._num(row.total_activity_load_score)), 1);
      const labelEvery = rows.length > 16 ? Math.ceil(rows.length / 8) : 1;
      return `
        <div class="chart">
          ${rows
            .map((row, index) => {
              const segments = activeSeries.map(({ metricKey, label, color }) => {
                const total = this._num(row.total_activity_load_score);
                const value = this._num(row[metricKey]);
                if (value <= 0 || total <= 0) return "";
                const height = (value / max) * 100;
                return `<div class="segment" style="height:${height}%; background:${color};" title="${utils.escapeHtml(
                  `${label}: ${value.toFixed(1)}`
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
      const interactive = this._config.interactive_legend;
      return `
        <div class="legend">
          ${this._allSeries()
            .map(({ id, label, color }) => {
              const disabled = this._disabledSeries.has(id);
              if (!interactive) {
                return `<span class="legend-chip ${disabled ? "disabled" : ""}"><span class="legend-dot" style="background:${color}"></span><span class="legend-label">${utils.escapeHtml(
                  label
                )}</span></span>`;
              }
              return `<button type="button" class="legend-chip ${disabled ? "disabled" : ""}" data-series-key="${utils.escapeHtml(
                id
              )}" aria-pressed="${disabled ? "false" : "true"}" title="${utils.escapeHtml(
                `${label} ${disabled ? "einblenden" : "ausblenden"}`
              )}"><span class="legend-dot" style="background:${color}"></span><span class="legend-label">${utils.escapeHtml(
                label
              )}</span></button>`;
            })
            .join("")}
        </div>
      `;
    }

    _bindLegendInteractions() {
      if (!this._config.interactive_legend) return;
      this.shadowRoot?.querySelectorAll("[data-series-key]").forEach((node) => {
        node.addEventListener("click", (event) => {
          event.stopPropagation();
          const key = node.getAttribute("data-series-key");
          this._toggleSeries(key);
        });
      });
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
      const activeSeries = this._activeSeries();
      const groupedRows = this._groupRows(selectedRows, activeSeries);
      const totals = this._summary(selectedRows, activeSeries);

      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="header">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="subtitle">${utils.escapeHtml(selection.label || "Diese Woche")}</div>
            </div>
            ${this._renderBars(groupedRows, activeSeries)}
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
      this._bindLegendInteractions();
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
            border: 1px solid transparent;
            color: var(--primary-text-color);
            cursor: pointer;
            user-select: none;
          }

          .legend-chip.disabled {
            opacity: 0.38;
            filter: grayscale(1);
          }

          .legend-chip.disabled .legend-dot {
            opacity: 0.45;
          }

          .legend-chip:focus-visible {
            outline: none;
            border-color: color-mix(in srgb, var(--primary-color) 52%, transparent);
            box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary-color) 18%, transparent);
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
