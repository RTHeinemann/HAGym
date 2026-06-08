(() => {
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
  const CATEGORY_GROUPS = {
    push: new Set(["chest", "shoulders", "triceps"]),
    pull: new Set(["back", "biceps", "erector_spinae", "forearms", "lats", "rhomboids", "traps"]),
    legs: new Set(["abductors", "adductors", "calves", "glutes", "hamstrings", "quadriceps"]),
    core: new Set(["abs", "core", "obliques"]),
  };

  class HAGymBalanceCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {
        title: "Trainingsbalance",
        daily_metric_entity: null,
        collection_key: "hagym",
        mode: "push_pull",
      };
      this._selection = null;
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
        type: "custom:hagym-balance-card",
        title: "Balance Push/Pull",
        daily_metric_entity: dailyMetricEntity,
        collection_key: collectionKey,
        mode: "push_pull",
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
      this._render();
    }

    disconnectedCallback() {
      window.removeEventListener("hagym-period-changed", this._onPeriodChanged);
      window.removeEventListener("hagym-date-selection-changed", this._onPeriodChanged);
      window.removeEventListener("storage", this._onStorage);
    }

    setConfig(config) {
      if (!config?.daily_metric_entity) {
        throw new Error("hagym-balance-card: daily_metric_entity is required");
      }

      const mode = ["push_pull", "push_pull_legs", "upper_lower"].includes(config.mode)
        ? config.mode
        : "push_pull";
      this._config = {
        title: config.title ? String(config.title) : "Trainingsbalance",
        daily_metric_entity: String(config.daily_metric_entity),
        collection_key: config.collection_key ? String(config.collection_key) : "hagym",
        mode,
      };
      this._selection = ensureUtils() ? this._loadSelection() : null;
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
            <div class="title">${String(this._config?.title || "Trainingsbalance")}</div>
            <div class="warning">${missingUtilsMessage}</div>
          </div>
        </ha-card>
      `;
    }

    _loadSelection() {
      if (!ensureUtils()) return null;
      return utils.loadSelection(this._config.collection_key, "this_week");
    }

    _onStorage(event) {
      if (!ensureUtils()) {
        this._renderMissingUtils();
        return;
      }
      if (event.key !== `hagym-period-selection:${this._config.collection_key}`) return;
      this._selection = this._loadSelection();
      this._render();
    }

    _onPeriodChanged(event) {
      if (!ensureUtils()) {
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

    _aggregateCategories(rows) {
      const totals = {
        push: 0,
        pull: 0,
        legs: 0,
        core: 0,
      };
      for (const day of rows) {
        const groups = Array.isArray(day?.muscle_groups) ? day.muscle_groups : [];
        for (const group of groups) {
          const muscleGroupId = String(group?.muscle_group_id || "").trim();
          if (!muscleGroupId) continue;
          const value = this._num(group?.strength_volume_kg);
          const fallback = value > 0 ? value : this._num(group?.activity_load_score);
          if (CATEGORY_GROUPS.push.has(muscleGroupId)) totals.push += fallback;
          if (CATEGORY_GROUPS.pull.has(muscleGroupId)) totals.pull += fallback;
          if (CATEGORY_GROUPS.legs.has(muscleGroupId)) totals.legs += fallback;
          if (CATEGORY_GROUPS.core.has(muscleGroupId)) totals.core += fallback;
        }
      }
      totals.upper_body = totals.push + totals.pull;
      totals.lower_body = totals.legs;
      totals.total = totals.push + totals.pull + totals.legs + totals.core;
      return totals;
    }

    _percent(value, total) {
      if (total <= 0) return 0;
      return (value / total) * 100;
    }

    _recommendation(totals) {
      if (totals.total <= 0) return "Keine Daten im gewaehlten Zeitraum";
      const push = this._percent(totals.push, totals.push + totals.pull || 1);
      const pull = this._percent(totals.pull, totals.push + totals.pull || 1);
      const legsPercent = this._percent(totals.legs, totals.total);
      if (legsPercent < 20) return "Beintraining unterrepraesentiert";
      if (push >= 45 && push <= 55 && pull >= 45 && pull <= 55) {
        return "Push/Pull ausgewogen";
      }
      if (push - pull > 10) return "Mehr Pull-Volumen einplanen";
      if (pull - push > 10) return "Mehr Push-Volumen einplanen";
      return "Push/Pull leicht verschoben";
    }

    _segment(label, value, total, color) {
      const percent = this._percent(value, total);
      return `
        <div class="segment" style="width:${Math.max(percent, total > 0 ? 8 : 0)}%; background:${color};">
          <span>${utils.escapeHtml(label)} ${percent.toFixed(0)}%</span>
        </div>
      `;
    }

    _renderBar(totals) {
      if (totals.total <= 0) {
        return `<div class="empty">Keine Daten im gewaehlten Zeitraum</div>`;
      }

      if (this._config.mode === "upper_lower") {
        const total = totals.upper_body + totals.lower_body;
        return `
          <div class="bar">
            ${this._segment("Upper", totals.upper_body, total, "#1f8ef1")}
            ${this._segment("Lower", totals.lower_body, total, "#00a980")}
          </div>
        `;
      }

      if (this._config.mode === "push_pull_legs") {
        const total = totals.push + totals.pull + totals.legs;
        return `
          <div class="bar">
            ${this._segment("Push", totals.push, total, "#ff8a34")}
            ${this._segment("Pull", totals.pull, total, "#1f8ef1")}
            ${this._segment("Legs", totals.legs, total, "#00a980")}
          </div>
        `;
      }

      const total = totals.push + totals.pull;
      const pushPercent = this._percent(totals.push, total);
      const pullPercent = this._percent(totals.pull, total);
      return `
        <div class="bar push-pull">
          <div class="marker"></div>
          ${this._segment("Push", totals.push, total, "#ff8a34")}
          ${this._segment("Pull", totals.pull, total, "#1f8ef1")}
        </div>
        <div class="split-values">
          <span>Push ${pushPercent.toFixed(0)}%</span>
          <span>Pull ${pullPercent.toFixed(0)}%</span>
        </div>
      `;
    }

    _render() {
      if (!this.shadowRoot) return;
      if (!ensureUtils()) {
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
      const totals = this._aggregateCategories(selectedRows);
      const recommendation = this._recommendation(totals);

      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="header">
              <div class="title">${utils.escapeHtml(this._config.title)}</div>
              <div class="subtitle">${utils.escapeHtml(selection.label || "Diese Woche")}</div>
            </div>
            ${this._renderBar(totals)}
            <div class="tiles">
              <div class="tile"><span>Push</span><strong>${totals.push.toFixed(1)}</strong></div>
              <div class="tile"><span>Pull</span><strong>${totals.pull.toFixed(1)}</strong></div>
              <div class="tile"><span>Legs</span><strong>${totals.legs.toFixed(1)}</strong></div>
              <div class="tile"><span>Core</span><strong>${totals.core.toFixed(1)}</strong></div>
            </div>
            <div class="note">${utils.escapeHtml(recommendation)}</div>
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
              radial-gradient(circle at top right, rgba(255, 138, 52, 0.14), transparent 38%),
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

          .bar {
            position: relative;
            display: flex;
            width: 100%;
            min-height: 54px;
            overflow: hidden;
            border-radius: 16px;
            background: color-mix(in srgb, var(--secondary-text-color) 8%, transparent);
          }

          .segment {
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 0;
            padding: 0 10px;
            color: #fff;
            font-size: 0.82rem;
            font-weight: 700;
            white-space: nowrap;
          }

          .segment span {
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .push-pull .marker {
            position: absolute;
            left: 50%;
            top: 0;
            bottom: 0;
            width: 2px;
            transform: translateX(-50%);
            background: rgba(255, 255, 255, 0.65);
          }

          .split-values {
            margin-top: 8px;
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--secondary-text-color);
          }

          .tiles {
            margin-top: 12px;
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
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
          }

          .note,
          .warning,
          .empty {
            margin-top: 12px;
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

  if (!customElements.get("hagym-balance-card")) {
    customElements.define("hagym-balance-card", HAGymBalanceCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "hagym-balance-card")) {
    window.customCards.push({
      type: "hagym-balance-card",
      name: "HAGym Balance Card",
      description: "Push/Pull and Push/Pull/Legs balance analysis.",
      preview: true,
    });
  }
})();
