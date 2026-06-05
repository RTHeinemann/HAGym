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

    const MONTH_LABELS = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "Mai",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Okt",
      "Nov",
      "Dez",
    ];

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

    const escapeHtml = (value) =>
      String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const normalizePeriod = (value) => {
      const normalized = String(value || "").trim().toLowerCase();
      return PERIOD_KEYS.has(normalized) ? normalized : "this_week";
    };

    const isoWeekParts = (date) => {
      const utcDate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
      utcDate.setUTCDate(utcDate.getUTCDate() + 4 - (utcDate.getUTCDay() || 7));
      const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
      const week = Math.ceil(((utcDate - yearStart) / 86400000 + 1) / 7);
      return { year: utcDate.getUTCFullYear(), week };
    };

    const buildLabel = (periodKey, start, anchor) => {
      if (periodKey === "today") return "Heute";
      if (periodKey === "yesterday") return "Gestern";
      if (periodKey === "this_week") {
        const parts = isoWeekParts(anchor);
        return `KW ${String(parts.week).padStart(2, "0")} ${parts.year}`;
      }
      if (periodKey === "this_month") {
        return `${MONTH_LABELS[start.getMonth()]} ${start.getFullYear()}`;
      }
      if (periodKey === "this_quarter") {
        return `Q${Math.floor(start.getMonth() / 3) + 1} ${start.getFullYear()}`;
      }
      if (periodKey === "this_year") return String(start.getFullYear());
      if (periodKey === "last_7_days") return "Letzte 7 Tage";
      if (periodKey === "last_30_days") return "Letzte 30 Tage";
      if (periodKey === "last_12_weeks") return "Letzte 12 Wochen";
      if (periodKey === "last_12_months") return "Letzte 12 Monate";
      return "Diese Woche";
    };

    const buildSelection = (periodKey, anchorDate, collectionKey) => {
      const key = normalizePeriod(periodKey);
      const anchor = parseDate(anchorDate) || new Date();
      let start;
      let end;

      if (key === "today") {
        start = startOfDay(anchor);
        end = addDays(start, 1);
      } else if (key === "yesterday") {
        end = startOfDay(anchor);
        start = addDays(end, -1);
      } else if (key === "this_week") {
        start = startOfWeek(anchor);
        end = addDays(start, 7);
      } else if (key === "this_month") {
        start = startOfMonth(anchor);
        end = addMonths(start, 1);
      } else if (key === "this_quarter") {
        start = startOfQuarter(anchor);
        end = addMonths(start, 3);
      } else if (key === "this_year") {
        start = startOfYear(anchor);
        end = new Date(start.getFullYear() + 1, 0, 1, 0, 0, 0, 0);
      } else if (key === "last_7_days") {
        const todayStart = startOfDay(anchor);
        start = addDays(todayStart, -6);
        end = addDays(todayStart, 1);
      } else if (key === "last_30_days") {
        const todayStart = startOfDay(anchor);
        start = addDays(todayStart, -29);
        end = addDays(todayStart, 1);
      } else if (key === "last_12_weeks") {
        const weekStart = startOfWeek(anchor);
        start = addDays(weekStart, -77);
        end = addDays(weekStart, 7);
      } else {
        const monthStart = startOfMonth(anchor);
        start = addMonths(monthStart, -11);
        end = addMonths(monthStart, 1);
      }

      return {
        period_key: key,
        anchor_date: anchor.toISOString(),
        label: buildLabel(key, start, anchor),
        start: start.toISOString(),
        end: end.toISOString(),
        collection_key: collectionKey,
      };
    };

    const storageKey = (collectionKey) => `hagym-period-selection:${collectionKey}`;

    const loadSelection = (collectionKey, defaultPeriod) => {
      const fallback = buildSelection(defaultPeriod || "this_week", new Date(), collectionKey);
      try {
        const raw = localStorage.getItem(storageKey(collectionKey));
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

    const saveSelection = (collectionKey, selection) => {
      try {
        localStorage.setItem(storageKey(collectionKey), JSON.stringify(selection));
      } catch (_err) {
        // Ignore localStorage issues.
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

    const shiftSelection = (selection, step, collectionKey) => {
      const current = selection || buildSelection("this_week", new Date(), collectionKey);
      const key = normalizePeriod(current.period_key);
      const anchor = parseDate(current.anchor_date) || new Date();
      let nextAnchor = new Date(anchor);

      if (key === "today" || key === "yesterday") {
        nextAnchor = addDays(anchor, step);
      } else if (key === "this_week") {
        nextAnchor = addDays(anchor, step * 7);
      } else if (key === "this_month") {
        nextAnchor = addMonths(anchor, step);
      } else if (key === "this_quarter") {
        nextAnchor = addMonths(anchor, step * 3);
      } else if (key === "this_year") {
        nextAnchor = addMonths(anchor, step * 12);
      } else if (key === "last_7_days") {
        nextAnchor = addDays(anchor, step * 7);
      } else if (key === "last_30_days") {
        nextAnchor = addDays(anchor, step * 30);
      } else if (key === "last_12_weeks") {
        nextAnchor = addDays(anchor, step * 84);
      } else if (key === "last_12_months") {
        nextAnchor = addMonths(anchor, step * 12);
      }

      return buildSelection(key, nextAnchor, collectionKey);
    };

    window.HAGymCardUtils = {
      addDays,
      addMonths,
      buildSelection,
      escapeHtml,
      loadSelection,
      normalizePeriod,
      parseDate,
      saveSelection,
      selectDaysForPeriod,
      shiftSelection,
      startOfWeek,
      storageKey,
    };
  }

  const utils = window.HAGymCardUtils;

  class HAGymDateSelectionCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {
        collection_key: "hagym",
        opening_direction: "right",
        vertical_opening_direction: "up",
        default_period: "this_week",
        placement: "inline",
      };
      this._selection = null;
      this._menuOpen = false;
      this._onStorage = this._onStorage.bind(this);
      this._onOutsideClick = this._onOutsideClick.bind(this);
    }

    static getStubConfig() {
      return {
        type: "custom:hagym-date-selection",
        collection_key: "hagym",
        opening_direction: "right",
        vertical_opening_direction: "up",
        default_period: "this_week",
        placement: "inline",
      };
    }

    connectedCallback() {
      window.addEventListener("storage", this._onStorage);
      window.addEventListener("click", this._onOutsideClick, true);
      this._selection = this._loadSelection();
      this._applyPlacement();
      this._render();
    }

    disconnectedCallback() {
      window.removeEventListener("storage", this._onStorage);
      window.removeEventListener("click", this._onOutsideClick, true);
    }

    setConfig(config) {
      const placement = config?.placement === "fixed-bottom" ? "fixed-bottom" : "inline";
      this._config = {
        collection_key:
          config?.collection_key && String(config.collection_key).trim()
            ? String(config.collection_key).trim()
            : "hagym",
        opening_direction: config?.opening_direction === "left" ? "left" : "right",
        vertical_opening_direction:
          config?.vertical_opening_direction === "down" ? "down" : "up",
        default_period: utils.normalizePeriod(config?.default_period || "this_week"),
        placement,
      };
      this._selection = this._loadSelection();
      this._applyPlacement();
      this._render();
    }

    getCardSize() {
      return this._config.placement === "fixed-bottom" ? 1 : 2;
    }

    _loadSelection() {
      return utils.loadSelection(this._config.collection_key, this._config.default_period);
    }

    _applyPlacement() {
      const fixed = this._config.placement === "fixed-bottom";
      this.toggleAttribute("data-fixed-bottom", fixed);
      this.style.position = fixed ? "fixed" : "";
      this.style.left = fixed ? "50%" : "";
      this.style.bottom = fixed
        ? "max(12px, calc(env(safe-area-inset-bottom, 0px) + 12px))"
        : "";
      this.style.transform = fixed ? "translateX(-50%)" : "";
      this.style.width = fixed ? "min(720px, calc(100vw - 24px))" : "";
      this.style.maxWidth = fixed ? "720px" : "";
      this.style.zIndex = fixed ? "7" : "";
      this.style.pointerEvents = "auto";
    }

    _storageKey() {
      return utils.storageKey(this._config.collection_key);
    }

    _onStorage(event) {
      if (event.key !== this._storageKey()) return;
      this._selection = this._loadSelection();
      this._render();
    }

    _onOutsideClick(event) {
      if (!this._menuOpen) return;
      if (event.composedPath().includes(this)) return;
      this._menuOpen = false;
      this._render();
    }

    _emitSelection(selection) {
      const detail = { ...selection, collection_key: this._config.collection_key };
      this.dispatchEvent(
        new CustomEvent("hagym-period-changed", {
          detail,
          bubbles: true,
          composed: true,
        })
      );
      this.dispatchEvent(
        new CustomEvent("hagym-date-selection-changed", {
          detail,
          bubbles: true,
          composed: true,
        })
      );
      window.dispatchEvent(new CustomEvent("hagym-period-changed", { detail }));
      window.dispatchEvent(new CustomEvent("hagym-date-selection-changed", { detail }));
    }

    _setSelection(periodKey, anchorDate) {
      this._selection = utils.buildSelection(
        periodKey,
        anchorDate,
        this._config.collection_key
      );
      utils.saveSelection(this._config.collection_key, this._selection);
      this._emitSelection(this._selection);
      this._render();
    }

    _shift(step) {
      const selection = utils.shiftSelection(
        this._selection,
        step,
        this._config.collection_key
      );
      utils.saveSelection(this._config.collection_key, selection);
      this._selection = selection;
      this._emitSelection(selection);
      this._render();
    }

    _resetNow() {
      const periodKey = this._selection?.period_key || this._config.default_period;
      this._setSelection(periodKey, new Date());
    }

    _renderMenuButton(key, label) {
      return `<button class="menu-item" data-period="${key}">${utils.escapeHtml(label)}</button>`;
    }

    _render() {
      if (!this.shadowRoot) return;
      const selection = this._selection || this._loadSelection();
      const menuPosX =
        this._config.opening_direction === "left" ? "right: 0;" : "left: 0;";
      const menuPosY =
        this._config.vertical_opening_direction === "down"
          ? "top: calc(100% + 10px);"
          : "bottom: calc(100% + 10px);";

      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="shell">
            <div class="bar">
              <span class="icon" aria-hidden="true">&#128197;</span>
              <button class="label" data-action="toggle-menu">${utils.escapeHtml(
                selection.label || "Diese Woche"
              )}</button>
              <button class="icon-btn" data-action="prev" title="Vorheriger Zeitraum">&#x2039;</button>
              <button class="icon-btn" data-action="next" title="Naechster Zeitraum">&#x203A;</button>
              <button class="now-btn" data-action="now">Jetzt</button>
              <button class="icon-btn" data-action="toggle-menu" title="Zeitraum waehlen">&#9776;</button>
            </div>
            ${
              this._menuOpen
                ? `<div class="menu" style="${menuPosX}${menuPosY}">
                    ${this._renderMenuButton("today", "Heute")}
                    ${this._renderMenuButton("yesterday", "Gestern")}
                    ${this._renderMenuButton("this_week", "Diese Woche")}
                    ${this._renderMenuButton("this_month", "Dieser Monat")}
                    ${this._renderMenuButton("this_quarter", "Dieses Quartal")}
                    ${this._renderMenuButton("this_year", "Dieses Jahr")}
                    ${this._renderMenuButton("last_7_days", "Letzte 7 Tage")}
                    ${this._renderMenuButton("last_30_days", "Letzte 30 Tage")}
                    ${this._renderMenuButton("last_12_weeks", "Letzte 12 Wochen")}
                    ${this._renderMenuButton("last_12_months", "Letzte 12 Monate")}
                  </div>`
                : ""
            }
          </div>
        </ha-card>
      `;

      this.shadowRoot.querySelectorAll('[data-action="toggle-menu"]').forEach((button) => {
        button.addEventListener("click", () => {
          this._menuOpen = !this._menuOpen;
          this._render();
        });
      });
      this.shadowRoot.querySelector('[data-action="prev"]')?.addEventListener("click", () => {
        this._shift(-1);
      });
      this.shadowRoot.querySelector('[data-action="next"]')?.addEventListener("click", () => {
        this._shift(1);
      });
      this.shadowRoot.querySelector('[data-action="now"]')?.addEventListener("click", () => {
        this._resetNow();
      });
      this.shadowRoot.querySelectorAll("[data-period]").forEach((button) => {
        button.addEventListener("click", () => {
          const period = button.getAttribute("data-period") || this._config.default_period;
          this._menuOpen = false;
          this._setSelection(period, new Date());
        });
      });
    }

    _style() {
      return `
        <style>
          :host {
            display: block;
          }

          ha-card {
            overflow: visible;
            border-radius: 18px;
            background:
              linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
              var(--ha-card-background, var(--card-background-color, #fff));
            backdrop-filter: blur(10px);
          }

          .shell {
            position: relative;
            padding: 8px;
          }

          .bar {
            display: grid;
            grid-template-columns: auto minmax(0, 1fr) repeat(4, auto);
            gap: 8px;
            align-items: center;
            padding: 8px;
            border-radius: 999px;
            border: 1px solid var(--divider-color);
            background: color-mix(in srgb, var(--card-background-color, #fff) 76%, transparent);
          }

          .icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            color: var(--primary-color);
            background: color-mix(in srgb, var(--primary-color) 14%, transparent);
            font-size: 16px;
          }

          button {
            font: inherit;
            border: none;
            color: var(--primary-text-color);
            background: transparent;
            cursor: pointer;
          }

          .label {
            min-width: 0;
            padding: 8px 12px;
            border-radius: 14px;
            text-align: left;
            font-size: 0.96rem;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            background: color-mix(in srgb, var(--primary-color) 8%, transparent);
          }

          .icon-btn {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: var(--ha-card-background, var(--card-background-color, #fff));
            border: 1px solid color-mix(in srgb, var(--divider-color) 70%, transparent);
            font-size: 1rem;
            font-weight: 700;
          }

          .now-btn {
            padding: 0 14px;
            height: 34px;
            border-radius: 999px;
            color: var(--text-primary-color, #fff);
            background: var(--primary-color);
            font-size: 0.84rem;
            font-weight: 700;
          }

          .menu {
            position: absolute;
            min-width: 240px;
            display: grid;
            gap: 4px;
            padding: 8px;
            border-radius: 16px;
            border: 1px solid var(--divider-color);
            background: var(--ha-card-background, var(--card-background-color, #fff));
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
            z-index: 30;
          }

          .menu-item {
            padding: 10px 12px;
            border-radius: 12px;
            text-align: left;
          }

          .menu-item:hover {
            background: color-mix(in srgb, var(--primary-color) 10%, transparent);
          }

          @media (max-width: 600px) {
            .bar {
              grid-template-columns: auto minmax(0, 1fr) repeat(3, auto);
            }

            .now-btn {
              padding: 0 12px;
            }
          }
        </style>
      `;
    }
  }

  if (!customElements.get("hagym-date-selection")) {
    customElements.define("hagym-date-selection", HAGymDateSelectionCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "hagym-date-selection")) {
    window.customCards.push({
      type: "hagym-date-selection",
      name: "HAGym Date Selection",
      description: "Reusable Energy-inspired period selector for HAGym cards",
      preview: true,
    });
  }
})();
