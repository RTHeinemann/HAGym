(() => {
  const HAGYM_CARD_VERSION = "1.0.3.17";
  const HAGYM_CARD_UTILS_URL = `/hagym_static/hagym-card-utils.js?v=${HAGYM_CARD_VERSION}`;
  const HAGYM_CARD_UTILS_FALLBACK_URL = "/hagym_static/hagym-card-utils.js";
  const getUtils = () => window.HAGymCardUtils;
  const utils = new Proxy(
    {},
    {
      get: (_target, prop) => getUtils()?.[prop],
    }
  );
  const loadingUtilsMessage = "Loading HAGym card utilities...";
  const missingUtilsMessage =
    "HAGymCardUtils missing. Could not load /hagym_static/hagym-card-utils.js.";
  const loadHAGymCardUtils = () => {
    if (getUtils()) {
      return Promise.resolve(getUtils());
    }
    if (window.HAGymCardUtilsLoadingPromise) {
      return window.HAGymCardUtilsLoadingPromise;
    }

    const waitForUtils = (resolve, reject) => {
      const startedAt = Date.now();
      const interval = window.setInterval(() => {
        if (getUtils()) {
          window.clearInterval(interval);
          resolve(getUtils());
        } else if (Date.now() - startedAt > 5000) {
          window.clearInterval(interval);
          reject(new Error("Timed out waiting for HAGymCardUtils"));
        }
      }, 50);
    };

    window.HAGymCardUtilsLoadingPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-hagym-card-utils="true"]');
      if (existing) {
        waitForUtils(resolve, reject);
        return;
      }

      const tryLoad = (src) => {
        const script = document.createElement("script");
        script.type = "module";
        script.src = src;
        script.dataset.hagymCardUtils = "true";
        script.onload = () => {
          if (getUtils()) {
            resolve(getUtils());
          } else {
            reject(new Error("hagym-card-utils.js loaded but HAGymCardUtils missing"));
          }
        };
        script.onerror = () => {
          script.remove();
          if (src !== HAGYM_CARD_UTILS_FALLBACK_URL) {
            tryLoad(HAGYM_CARD_UTILS_FALLBACK_URL);
            return;
          }
          reject(new Error("Failed to load hagym-card-utils.js"));
        };
        document.head.appendChild(script);
      };

      tryLoad(HAGYM_CARD_UTILS_URL);
    })
      .catch((error) => {
        window.HAGymCardUtilsLoadingPromise = null;
        throw error;
      })
      .then((loadedUtils) => {
        window.HAGymCardUtilsLoadingPromise = Promise.resolve(loadedUtils);
        return loadedUtils;
      });

    return window.HAGymCardUtilsLoadingPromise;
  };
  const LOAD_SEGMENTS = [
    { id: "bodyweight", metricKey: "bodyweight_load_score", label: "Bodyweight", color: "#1f8ef1" },
    { id: "duration", metricKey: "duration_load_score", label: "Duration", color: "#00a980" },
    { id: "hold", metricKey: "hold_load_score", label: "Hold", color: "#6d5efc" },
    { id: "distance", metricKey: "distance_load_score", label: "Distance", color: "#ff8a34" },
    { id: "cardio", metricKey: "cardio_load_score", label: "Cardio", color: "#db5461" },
    { id: "custom", metricKey: "custom_load_score", label: "Custom", color: "#4a4f57" },
  ];

  const detectDailyMetricEntity = (hass, collectionKey = "hagym") =>
    window.HAGymCardUtils?.defaultDailyMetricEntity?.(
      hass,
      collectionKey,
      "sensor.hagym_hagym_personliche_tagesstatistik"
    ) || "sensor.hagym_hagym_personliche_tagesstatistik";

  const activityLoadPresetConfig = (hass, preset = {}) => ({
    type: "custom:hagym-activity-load-card",
    title: "Activity Load",
    daily_metric_entity: detectDailyMetricEntity(hass, "hagym"),
    collection_key: "hagym",
    group_by: "day",
    interactive_legend: true,
    persist_legend_state: false,
    ...preset,
  });

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
      this._utilsLoading = false;
      this._utilsLoadError = null;
      this._onPeriodChanged = this._onPeriodChanged.bind(this);
      this._onStorage = this._onStorage.bind(this);
    }

    static getStubConfig(hass) {
      return activityLoadPresetConfig(hass);
    }

    connectedCallback() {
      if (!this._ensureUtilsAvailable()) {
        this._renderMissingUtils();
        return;
      }
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
      this._selection = this._ensureUtilsAvailable() ? this._loadSelection() : null;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    getCardSize() {
      return 5;
    }

    _renderMissingUtils() {
      if (!this.shadowRoot) return;
      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="title">${this._config?.title ? utils?.escapeHtml?.(this._config.title) || this._config.title : "Activity Load"}</div>
            <div class="warning">${this._utilsLoading ? loadingUtilsMessage : missingUtilsMessage}</div>
          </div>
        </ha-card>
      `;
    }

    _ensureUtilsAvailable() {
      if (getUtils()) {
        this._utilsLoading = false;
        this._utilsLoadError = null;
        return true;
      }
      if (!this._utilsLoading) {
        this._utilsLoading = true;
        loadHAGymCardUtils()
          .then(() => {
            this._utilsLoading = false;
            this._utilsLoadError = null;
            this._selection = this._selection || this._loadSelection();
            this._render();
          })
          .catch((error) => {
            this._utilsLoading = false;
            this._utilsLoadError = error;
            console.error(missingUtilsMessage, error);
            this._render();
          });
      }
      return false;
    }

    _loadSelection() {
      if (!this._ensureUtilsAvailable()) return null;
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
      if (!this._ensureUtilsAvailable()) {
        this._renderMissingUtils();
        return;
      }
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
      if (!this._ensureUtilsAvailable()) {
        this._renderMissingUtils();
        return;
      }
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
      if (!this._ensureUtilsAvailable()) {
        this._renderMissingUtils();
        return;
      }
      const entity = this._hass?.states?.[this._config.daily_metric_entity];
      if (!entity) {
        this.shadowRoot.innerHTML = `
          ${this._style()}
          <ha-card>
            <div class="wrap">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="warning">Daily metric entity not found. Configure daily_metric_entity.</div>
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

  class HAGymActivityLoadReadyCard extends HAGymActivityLoadCard {
    static getStubConfig(hass) {
      return {
        ...activityLoadPresetConfig(hass),
        type: "custom:hagym-activity-load-ready-card",
      };
    }

    setConfig(config) {
      super.setConfig({
        ...activityLoadPresetConfig(this._hass),
        ...config,
      });
    }
  }

  if (!customElements.get("hagym-activity-load-card")) {
    customElements.define("hagym-activity-load-card", HAGymActivityLoadCard);
  }
  if (!customElements.get("hagym-activity-load-ready-card")) {
    customElements.define("hagym-activity-load-ready-card", HAGymActivityLoadReadyCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "hagym-activity-load-card")) {
    window.customCards.push({
      type: "hagym-activity-load-card",
      name: "HAGym Activity Load Card (advanced)",
      description: "Advanced activity load card with configurable grouping and legend behavior.",
      preview: true,
    });
  }
  if (!window.customCards.some((card) => card.type === "hagym-activity-load-ready-card")) {
    window.customCards.push({
      type: "hagym-activity-load-ready-card",
      name: "HAGym Activity Load",
      description: "Prepared activity load chart with interactive legend.",
      preview: true,
    });
  }
})();
