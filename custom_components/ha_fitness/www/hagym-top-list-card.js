(() => {
  const HAGYM_CARD_VERSION = "1.0.3.17";
  const HAGYM_CARD_UTILS_URL = `/hagym_static/hagym-card-utils.js?v=${HAGYM_CARD_VERSION}`;
  const HAGYM_CARD_UTILS_FALLBACK_URL = "/hagym_static/hagym-card-utils.js";
  const getUtils = () => window.HAGymCardUtils;
  const utils = new Proxy({}, { get: (_target, prop) => getUtils()?.[prop] });
  const loadingUtilsMessage = "Loading HAGym card utilities...";
  const missingUtilsMessage =
    "HAGymCardUtils missing. Could not load /hagym_static/hagym-card-utils.js.";
  const loadHAGymCardUtils = () => {
    if (getUtils()) return Promise.resolve(getUtils());
    if (window.HAGymCardUtilsLoadingPromise) return window.HAGymCardUtilsLoadingPromise;
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
          if (getUtils()) resolve(getUtils());
          else reject(new Error("hagym-card-utils.js loaded but HAGymCardUtils missing"));
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

  const SCOPE_META = {
    exercises: {
      idField: "exercise_id",
      nameField: "exercise_name",
    },
    equipment: {
      idField: "equipment_id",
      nameField: "equipment_name",
    },
    muscle_groups: {
      idField: "muscle_group_id",
      nameField: "muscle_group_name",
    },
    metric_types: {
      idField: "metric_type",
      nameField: "metric_type_name",
    },
  };

  const METRIC_TYPE_FALLBACKS = [
    ["strength", "strength_volume_kg", "Kraft"],
    ["bodyweight", "bodyweight_load_score", "Bodyweight"],
    ["duration", "duration_load_score", "Dauer"],
    ["hold", "hold_load_score", "Halten"],
    ["distance", "distance_load_score", "Distanz"],
    ["cardio", "cardio_load_score", "Cardio"],
    ["custom", "custom_load_score", "Custom"],
  ];

  const DEFAULT_UNITS = {
    strength_volume_kg: "kg",
    activity_load_score: "load",
    duration_minutes: "min",
    distance_km: "km",
    reps: "reps",
    entries: "Eintraege",
    sets: "Saetze",
  };

  class HAGymTopListCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {
        title: "Top Liste",
        daily_metric_entity: null,
        collection_key: "hagym",
        scope: "muscle_groups",
        metric: "strength_volume_kg",
        limit: 10,
        unit: null,
        empty_text: "Keine Daten im gewaehlten Zeitraum",
      };
      this._selection = null;
      this._utilsLoading = false;
      this._utilsLoadError = null;
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
        type: "custom:hagym-top-list-card",
        title: "Trainingsvolumen pro Muskelgruppe",
        daily_metric_entity: dailyMetricEntity,
        collection_key: collectionKey,
        scope: "muscle_groups",
        metric: "strength_volume_kg",
        unit: "kg",
        limit: 10,
      };
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
        throw new Error("hagym-top-list-card: daily_metric_entity is required");
      }

      const scope = SCOPE_META[config.scope] ? config.scope : "muscle_groups";
      const metric = String(config.metric || "strength_volume_kg");
      this._config = {
        title: config.title ? String(config.title) : "Top Liste",
        daily_metric_entity: String(config.daily_metric_entity),
        collection_key: config.collection_key ? String(config.collection_key) : "hagym",
        scope,
        metric,
        limit: Math.max(1, Number(config.limit) || 10),
        unit: config.unit ? String(config.unit) : DEFAULT_UNITS[metric] || "",
        empty_text: config.empty_text
          ? String(config.empty_text)
          : "Keine Daten im gewaehlten Zeitraum",
      };
      this._selection = this._ensureUtilsAvailable() ? this._loadSelection() : null;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    getCardSize() {
      return 4;
    }

    _renderMissingUtils() {
      if (!this.shadowRoot) return;
      this.shadowRoot.innerHTML = `
          ${this._style()}
          <ha-card>
            <div class="wrap">
            <div class="title">${this._config?.title ? String(this._config.title) : "Top Liste"}</div>
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

    _onStorage(event) {
      if (!this._ensureUtilsAvailable()) {
        this._renderMissingUtils();
        return;
      }
      if (event.key !== `hagym-period-selection:${this._config.collection_key}`) return;
      this._selection = this._loadSelection();
      this._render();
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

    _itemMetricValue(item) {
      const metric = this._config.metric;
      if (!item || typeof item !== "object") return 0;
      if (metric === "entries") {
        return this._num(item.entries ?? item.entry_count);
      }
      if (metric === "sets") {
        return this._num(item.sets ?? item.total_sets);
      }
      if (metric === "reps") {
        return this._num(item.reps ?? item.total_reps);
      }
      return this._num(item[metric]);
    }

    _aggregate(rows) {
      const meta = SCOPE_META[this._config.scope];
      const merged = new Map();
      for (const day of rows) {
        const list =
          this._config.scope === "metric_types"
            ? this._metricTypeItems(day)
            : Array.isArray(day?.[this._config.scope])
              ? day[this._config.scope]
              : [];
        for (const item of list) {
          const id = String(item?.[meta.idField] || "").trim();
          if (!id) continue;
          const name = String(item?.[meta.nameField] || id);
          const current =
            merged.get(id) || {
              id,
              name,
              value: 0,
            };
          current.value += this._itemMetricValue(item);
          merged.set(id, current);
        }
      }

      return [...merged.values()]
        .filter((row) => row.value > 0)
        .sort((left, right) => right.value - left.value || left.name.localeCompare(right.name))
        .slice(0, this._config.limit);
    }

    _metricTypeItems(day) {
      const direct = Array.isArray(day?.metric_types) ? day.metric_types : null;
      if (direct?.length) {
        return direct;
      }
      return METRIC_TYPE_FALLBACKS.map(([id, field, name]) => ({
        metric_type: id,
        metric_type_name: name,
        [this._config.metric]: this._num(day?.[field]),
      })).filter((item) => this._itemMetricValue(item) > 0);
    }

    _renderRows(rows) {
      if (!rows.length) {
        return `<div class="empty">${utils.escapeHtml(this._config.empty_text)}</div>`;
      }
      const maxValue = Math.max(...rows.map((row) => row.value), 1);
      return rows
        .map((row, index) => {
          const percent = Math.max(6, (row.value / maxValue) * 100);
          const value = `${this._format(row.value)}${this._config.unit ? ` ${this._config.unit}` : ""}`;
          return `
            <div class="row">
              <div class="row-head">
                <span class="name">${utils.escapeHtml(row.name)}</span>
                <span class="value">${utils.escapeHtml(value)}</span>
              </div>
              <div class="track">
                <div class="fill fill-${(index % 5) + 1}" style="width:${percent}%"></div>
              </div>
            </div>
          `;
        })
        .join("");
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
      const aggregated = this._aggregate(selectedRows);

      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="header">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="subtitle">${utils.escapeHtml(selection.label || "Diese Woche")}</div>
            </div>
            <div class="rows">${this._renderRows(aggregated)}</div>
          </div>
        </ha-card>
      `;
    }

    _num(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    _format(value) {
      if (Math.abs(value) >= 100 || Number.isInteger(value)) {
        return this._num(value).toFixed(0);
      }
      if (Math.abs(value) >= 10) {
        return this._num(value).toFixed(1);
      }
      return this._num(value).toFixed(2);
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
              radial-gradient(circle at top right, rgba(37, 150, 190, 0.12), transparent 40%),
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
            line-height: 1.25;
          }

          .subtitle,
          .muted {
            margin-top: 4px;
            font-size: 0.82rem;
            color: var(--secondary-text-color);
          }

          .rows {
            display: grid;
            gap: 12px;
          }

          .row {
            display: grid;
            gap: 6px;
          }

          .row-head {
            display: flex;
            gap: 12px;
            align-items: baseline;
            justify-content: space-between;
          }

          .name {
            min-width: 0;
            font-size: 0.92rem;
            font-weight: 600;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .value {
            flex-shrink: 0;
            font-size: 0.84rem;
            color: var(--secondary-text-color);
          }

          .track {
            height: 10px;
            border-radius: 999px;
            background: color-mix(in srgb, var(--primary-color) 10%, var(--divider-color));
            overflow: hidden;
          }

          .fill {
            height: 100%;
            border-radius: 999px;
          }

          .fill-1 { background: #1f8ef1; }
          .fill-2 { background: #00a980; }
          .fill-3 { background: #ff8a34; }
          .fill-4 { background: #db5461; }
          .fill-5 { background: #7067cf; }

          .warning,
          .empty {
            padding: 12px 14px;
            border-radius: 14px;
            background: color-mix(in srgb, var(--secondary-text-color) 10%, transparent);
            color: var(--secondary-text-color);
          }
        </style>
      `;
    }
  }

  if (!customElements.get("hagym-top-list-card")) {
    customElements.define("hagym-top-list-card", HAGymTopListCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "hagym-top-list-card")) {
    window.customCards.push({
      type: "hagym-top-list-card",
      name: "HAGym Top List Card",
      description: "Top list ranking for exercises, equipment, muscle groups or metric types.",
      preview: true,
    });
  }
})();
