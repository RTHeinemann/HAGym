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

    const PERIOD_LABELS = {
      today: "Heute",
      yesterday: "Gestern",
      this_week: "Diese Woche",
      this_month: "Dieser Monat",
      this_quarter: "Dieses Quartal",
      this_year: "Dieses Jahr",
      last_7_days: "Letzte 7 Tage",
      last_30_days: "Letzte 30 Tage",
      last_365_days: "Letzte 365 Tage",
      last_12_weeks: "Letzte 12 Wochen",
      last_12_months: "Letzte 12 Monate",
      custom_range: "Benutzerdefinierter Zeitraum",
    };

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

    const formatCustomRangeLabel = (start, end, locale) => {
      const formatter = new Intl.DateTimeFormat(locale || undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
      const from = formatter.format(start);
      const to = formatter.format(end);
      return from === to ? from : `${from} - ${to}`;
    };

    const buildLabel = (periodKey, start, anchor, locale) => {
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
      if (periodKey === "last_365_days") return "Letzte 365 Tage";
      if (periodKey === "last_12_weeks") return "Letzte 12 Wochen";
      if (periodKey === "last_12_months") return "Letzte 12 Monate";
      if (periodKey === "custom_range") {
        return formatCustomRangeLabel(start, addDays(end, -1), locale);
      }
      return PERIOD_LABELS[periodKey] || "Diese Woche";
    };

    const buildSelection = (periodKey, anchorDate, collectionKey, locale) => {
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
      } else if (key === "last_365_days") {
        const todayStart = startOfDay(anchor);
        start = addDays(todayStart, -364);
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
        type: key,
        anchor_date: anchor.toISOString(),
        label: buildLabel(key, start, anchor, locale),
        start: start.toISOString(),
        end: end.toISOString(),
        collection_key: collectionKey,
      };
    };

    const buildCustomRangeSelection = (startValue, endValue, collectionKey, locale) => {
      const startDay = parseDateOnly(startValue) || startOfDay(parseDate(startValue) || new Date());
      const endDay = parseDateOnly(endValue) || startOfDay(parseDate(endValue) || startDay);
      const orderedStart = startDay <= endDay ? startDay : endDay;
      const orderedEnd = startDay <= endDay ? endDay : startDay;
      const endExclusive = addDays(orderedEnd, 1);
      return {
        period_key: "custom_range",
        type: "custom_range",
        anchor_date: orderedStart.toISOString(),
        label: formatCustomRangeLabel(orderedStart, orderedEnd, locale),
        start: orderedStart.toISOString(),
        end: endExclusive.toISOString(),
        start_date: toDateOnly(orderedStart),
        end_date: toDateOnly(orderedEnd),
        collection_key: collectionKey,
      };
    };

    const storageKey = (collectionKey) => `hagym-period-selection:${collectionKey}`;

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

    const selectionEndInclusive = (selection) => {
      const customEnd = parseDateOnly(selection?.end_date);
      if (customEnd) return customEnd;
      const endExclusive = selectionEndExclusive(selection);
      return endExclusive ? addDays(startOfDay(endExclusive), -1) : null;
    };

    const customRangeLengthDays = (selection) => {
      const start = selectionStartDate(selection);
      const end = selectionEndInclusive(selection);
      if (!start || !end) return 1;
      const diff = startOfDay(end).getTime() - startOfDay(start).getTime();
      return Math.max(1, Math.round(diff / 86400000) + 1);
    };

    const loadSelection = (collectionKey, defaultPeriod, locale) => {
      const fallback = buildSelection(defaultPeriod || "this_week", new Date(), collectionKey, locale);
      try {
        const raw = localStorage.getItem(storageKey(collectionKey));
        if (!raw) return fallback;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return fallback;
        const key = normalizePeriod(parsed.period_key || parsed.type || defaultPeriod || "this_week");
        if (key === "custom_range") {
          const startDate =
            parsed.start_date || (typeof parsed.start === "string" && DATE_ONLY_RE.test(parsed.start) ? parsed.start : toDateOnly(parsed.start));
          const endDate =
            parsed.end_date || (typeof parsed.end === "string" && DATE_ONLY_RE.test(parsed.end) ? parsed.end : toDateOnly(selectionEndInclusive(parsed)));
          if (startDate && endDate) {
            return buildCustomRangeSelection(startDate, endDate, collectionKey, locale);
          }
          return fallback;
        }
        return buildSelection(key, parsed.anchor_date || new Date(), collectionKey, locale);
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

    const shiftSelection = (selection, step, collectionKey, locale) => {
      const current =
        selection || buildSelection("this_week", new Date(), collectionKey, locale);
      const key = normalizePeriod(current.period_key || current.type);
      const anchor = parseDate(current.anchor_date) || new Date();
      let nextAnchor = new Date(anchor);

      if (key === "custom_range") {
        const start = selectionStartDate(current);
        const end = selectionEndInclusive(current);
        const length = customRangeLengthDays(current);
        if (start && end) {
          return buildCustomRangeSelection(
            toDateOnly(addDays(start, step * length)),
            toDateOnly(addDays(end, step * length)),
            collectionKey,
            locale
          );
        }
        return buildCustomRangeSelection(
          toDateOnly(addDays(startOfDay(new Date()), step)),
          toDateOnly(addDays(startOfDay(new Date()), step)),
          collectionKey,
          locale
        );
      }

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
      } else if (key === "last_365_days") {
        nextAnchor = addDays(anchor, step * 365);
      } else if (key === "last_12_weeks") {
        nextAnchor = addDays(anchor, step * 84);
      } else if (key === "last_12_months") {
        nextAnchor = addMonths(anchor, step * 12);
      }

      return buildSelection(key, nextAnchor, collectionKey, locale);
    };

    window.HAGymCardUtils = {
      addDays,
      addMonths,
      buildCustomRangeSelection,
      buildSelection,
      customRangeLengthDays,
      escapeHtml,
      formatCustomRangeLabel,
      loadSelection,
      normalizePeriod,
      parseDate,
      parseDateOnly,
      saveSelection,
      selectionEndExclusive,
      selectionEndInclusive,
      selectionStartDate,
      selectDaysForPeriod,
      shiftSelection,
      startOfDay,
      startOfWeek,
      storageKey,
      toDateOnly,
    };
  }

  const utils = window.HAGymCardUtils;

  class HAGymDateSelectionCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {
        collection_key: "hagym",
        opening_direction: "right",
        vertical_opening_direction: "up",
        default_period: "this_week",
        placement: "inline",
        compact: false,
        use_native_date_picker: true,
        desktop_sidebar_offset: "auto",
        content_selector: null,
        debug_layout: false,
        full_width_row: true,
        max_width: 900,
        bottom_offset: 16,
        z_index: 10,
      };
      this._selection = null;
      this._menuOpen = false;
      this._nativePickerReady = false;
      this._resizeObserver = null;
      this._mutationObserver = null;
      this._contentResizeObserver = null;
      this._observedContentElement = null;
      this._pendingPlacementTimers = new Set();
      this._lastLayoutDebug = "";
      this._lastLayoutSource = "unknown";
      this._onStorage = this._onStorage.bind(this);
      this._onDocumentClick = this._onDocumentClick.bind(this);
      this._onPointerUp = this._onPointerUp.bind(this);
      this._onResize = this._onResize.bind(this);
    }

    static getStubConfig() {
      return {
        type: "custom:hagym-date-selection",
        collection_key: "hagym",
        opening_direction: "right",
        vertical_opening_direction: "up",
        default_period: "this_week",
        placement: "inline",
        compact: true,
        use_native_date_picker: true,
      };
    }

    set hass(hass) {
      this._hass = hass;
      this._syncNativePicker();
    }

    connectedCallback() {
      window.addEventListener("storage", this._onStorage);
      window.addEventListener("click", this._onDocumentClick, true);
      window.addEventListener("pointerup", this._onPointerUp, true);
      window.addEventListener("resize", this._onResize);
      this._startLayoutObserver();
      this._startMutationObserver();
      this._selection = this._loadSelection();
      this._applyPlacement();
      this._scheduleInitialPlacementPasses();
      this._render();
      this._waitForNativePickerDefinition();
    }

    disconnectedCallback() {
      window.removeEventListener("storage", this._onStorage);
      window.removeEventListener("click", this._onDocumentClick, true);
      window.removeEventListener("pointerup", this._onPointerUp, true);
      window.removeEventListener("resize", this._onResize);
      this._stopLayoutObserver();
      this._stopMutationObserver();
      this._stopContentObserver();
      this._clearPlacementTimers();
    }

    setConfig(config) {
      const placement = config?.placement === "fixed-bottom" ? "fixed-bottom" : "inline";
      const rawDesktopOffset = config?.desktop_sidebar_offset;
      let desktopSidebarOffset = "auto";
      if (rawDesktopOffset === 0 || rawDesktopOffset === "0") {
        desktopSidebarOffset = 0;
      } else if (typeof rawDesktopOffset === "number") {
        desktopSidebarOffset = Math.max(0, rawDesktopOffset);
      } else if (
        rawDesktopOffset !== "auto" &&
        rawDesktopOffset !== undefined &&
        Number.isFinite(Number(rawDesktopOffset))
      ) {
        desktopSidebarOffset = Math.max(0, Number(rawDesktopOffset));
      }

      const contentSelector =
        config?.content_selector && String(config.content_selector).trim()
          ? String(config.content_selector).trim()
          : null;

      const defaultPeriod = String(config?.default_period || "this_week").trim().toLowerCase();
      const normalizedDefault =
        defaultPeriod === "custom_range" ? "this_week" : utils.normalizePeriod(defaultPeriod);

      this._config = {
        collection_key:
          config?.collection_key && String(config.collection_key).trim()
            ? String(config.collection_key).trim()
            : "hagym",
        opening_direction: config?.opening_direction === "left" ? "left" : "right",
        vertical_opening_direction:
          config?.vertical_opening_direction === "down" ? "down" : "up",
        default_period: normalizedDefault,
        placement,
        compact: config?.compact === true,
        use_native_date_picker: config?.use_native_date_picker !== false,
        desktop_sidebar_offset: desktopSidebarOffset,
        content_selector: contentSelector,
        debug_layout: config?.debug_layout === true,
        full_width_row: config?.full_width_row !== false,
        max_width: Math.max(280, Number(config?.max_width) || 900),
        bottom_offset: Math.max(0, Number(config?.bottom_offset) || 16),
        z_index: Math.max(1, Number(config?.z_index) || 10),
      };
      this._selection = this._loadSelection();
      this._applyPlacement();
      this._startMutationObserver();
      this._scheduleInitialPlacementPasses();
      this._render();
      this._waitForNativePickerDefinition();
    }

    getCardSize() {
      return this._config.placement === "fixed-bottom" ? 1 : 2;
    }

    _currentLocale() {
      const language =
        this._hass?.locale?.language || document.documentElement.lang || navigator.language;
      return language || "de-DE";
    }

    _nativePickerAvailable() {
      return this._config.use_native_date_picker && !!customElements.get("ha-date-range-picker");
    }

    _waitForNativePickerDefinition() {
      if (!this._config.use_native_date_picker) {
        return;
      }
      if (customElements.get("ha-date-range-picker")) {
        this._nativePickerReady = true;
        this._syncNativePicker();
        return;
      }
      customElements.whenDefined("ha-date-range-picker").then(() => {
        this._nativePickerReady = true;
        this._render();
      });
    }

    _onResize() {
      if (this._config.placement !== "fixed-bottom") return;
      this._applyPlacement();
    }

    _schedulePlacement(delay = 50) {
      const timer = window.setTimeout(() => {
        this._pendingPlacementTimers.delete(timer);
        if (this._config.placement === "fixed-bottom") {
          this._applyPlacement();
          this._render();
        }
      }, delay);
      this._pendingPlacementTimers.add(timer);
    }

    _scheduleInitialPlacementPasses() {
      this._clearPlacementTimers();
      for (const delay of [0, 100, 300, 700, 1200]) {
        this._schedulePlacement(delay);
      }
    }

    _clearPlacementTimers() {
      for (const timer of this._pendingPlacementTimers) {
        window.clearTimeout(timer);
      }
      this._pendingPlacementTimers.clear();
    }

    _startLayoutObserver() {
      this._stopLayoutObserver();
      if (typeof ResizeObserver !== "function") {
        return;
      }
      const targets = this._layoutTargets();
      if (!targets.length) {
        return;
      }
      this._resizeObserver = new ResizeObserver(() => {
        if (this._config.placement === "fixed-bottom") {
          this._applyPlacement();
          this._render();
        }
      });
      for (const target of targets) {
        this._resizeObserver.observe(target);
      }
    }

    _stopLayoutObserver() {
      this._resizeObserver?.disconnect?.();
      this._resizeObserver = null;
    }

    _startMutationObserver() {
      this._stopMutationObserver();
      if (typeof MutationObserver !== "function") {
        return;
      }
      this._mutationObserver = new MutationObserver((mutations) => {
        if (this._config.placement !== "fixed-bottom") {
          return;
        }
        let shouldReposition = false;
        for (const mutation of mutations) {
          if (mutation.type === "childList") {
            shouldReposition = true;
            break;
          }
          if (mutation.type === "attributes") {
            const attr = mutation.attributeName || "";
            if (attr === "class" || attr === "style" || attr === "aria-expanded") {
              shouldReposition = true;
              break;
            }
          }
        }
        if (shouldReposition) {
          this._schedulePlacement(50);
        }
      });

      for (const target of this._mutationTargets()) {
        this._mutationObserver.observe(target, {
          attributes: true,
          childList: true,
          subtree: true,
          attributeFilter: ["class", "style", "aria-expanded"],
        });
      }
    }

    _stopMutationObserver() {
      this._mutationObserver?.disconnect?.();
      this._mutationObserver = null;
    }

    _observeContentElement(element) {
      if (!element || typeof ResizeObserver !== "function") {
        return;
      }
      if (this._observedContentElement === element && this._contentResizeObserver) {
        return;
      }
      this._stopContentObserver();
      this._observedContentElement = element;
      this._contentResizeObserver = new ResizeObserver(() => {
        if (this._config.placement === "fixed-bottom") {
          this._applyPlacement();
          this._render();
        }
      });
      this._contentResizeObserver.observe(element);
    }

    _stopContentObserver() {
      this._contentResizeObserver?.disconnect?.();
      this._contentResizeObserver = null;
      this._observedContentElement = null;
    }

    _layoutTargets() {
      const targets = [
        document.body,
        document.documentElement,
        document.querySelector("home-assistant-main"),
        document.querySelector("ha-panel-lovelace"),
      ];
      const root = document.querySelector("home-assistant");
      if (root?.shadowRoot) {
        targets.push(root.shadowRoot.querySelector("home-assistant-main"));
        targets.push(root.shadowRoot.querySelector("partial-panel-resolver"));
      }
      return targets.filter(Boolean);
    }

    _mutationTargets() {
      const targets = [document.body, document.documentElement];
      const root = document.querySelector("home-assistant");
      if (root) {
        targets.push(root);
      }
      if (root?.shadowRoot) {
        targets.push(root.shadowRoot);
      }
      return targets.filter(Boolean);
    }

    _loadSelection() {
      return utils.loadSelection(
        this._config.collection_key,
        this._config.default_period,
        this._currentLocale()
      );
    }

    _applyPlacement() {
      const fixed = this._config.placement === "fixed-bottom";
      this.toggleAttribute("data-fixed-bottom", fixed);
      this.style.pointerEvents = fixed ? "none" : "auto";
      if (!fixed) {
        this.style.setProperty("--hagym-content-left", "");
        this.style.setProperty("--hagym-content-width", "");
        this.style.setProperty("--hagym-max-width", "");
        this.style.setProperty("--hagym-bottom-offset", "");
        this.style.setProperty("--hagym-z-index", "");
        this._lastLayoutSource = "inline";
        this._lastLayoutDebug = "";
        return;
      }

      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
      const isDesktop = viewportWidth >= 870;
      let layout;
      if (isDesktop) {
        layout = this._resolveDesktopContentLayout(viewportWidth);
      } else {
        this._stopContentObserver();
        layout = {
          left: 0,
          width: viewportWidth,
          source: "mobile",
          element: null,
        };
      }

      if (layout.element) {
        this._observeContentElement(layout.element);
      }

      this.style.setProperty("--hagym-content-left", `${Math.round(layout.left)}px`);
      this.style.setProperty("--hagym-content-width", `${Math.round(layout.width)}px`);
      this.style.setProperty("--hagym-max-width", `${Math.round(this._config.max_width)}px`);
      this.style.setProperty(
        "--hagym-bottom-offset",
        `${Math.round(isDesktop ? this._config.bottom_offset : 12)}px`
      );
      this.style.setProperty("--hagym-z-index", String(this._config.z_index));

      this._lastLayoutSource = layout.source;
      this._lastLayoutDebug =
        `layout: ${layout.source} left=${Math.round(layout.left)} width=${Math.round(layout.width)}`;
      this._debugLayout("fixed-row-layout", {
        source: layout.source,
        contentLeft: Math.round(layout.left),
        contentWidth: Math.round(layout.width),
      });
    }

    _resolveDesktopContentLayout(viewportWidth) {
      if (this._config.desktop_sidebar_offset === 0) {
        return { left: 0, width: viewportWidth, source: "viewport", element: null };
      }

      if (this._config.desktop_sidebar_offset === "auto") {
        const topBarWidth = this._detectContentWidthFromCssVariables();
        if (topBarWidth > 300 && topBarWidth <= viewportWidth) {
          return {
            left: Math.max(0, viewportWidth - topBarWidth),
            width: topBarWidth,
            source: "ha-top-app-bar-width",
            element: null,
          };
        }
      }

      const contentTarget = this._findBestContentTarget();
      if (
        this._config.desktop_sidebar_offset === "auto" &&
        contentTarget?.rect &&
        contentTarget.rect.width > 300
      ) {
        return {
          left: Math.max(0, contentTarget.rect.left),
          width: Math.min(viewportWidth, contentTarget.rect.width),
          source: contentTarget.source || "content-rect",
          element: contentTarget.element || null,
        };
      }

      if (typeof this._config.desktop_sidebar_offset === "number") {
        return {
          left: this._config.desktop_sidebar_offset,
          width: Math.max(280, viewportWidth - this._config.desktop_sidebar_offset),
          source: "manual-offset",
          element: null,
        };
      }

      const fallbackOffset = 256;
      return {
        left: fallbackOffset,
        width: Math.max(280, viewportWidth - fallbackOffset),
        source: "fallback-sidebar",
        element: null,
      };
    }

    _detectContentWidthFromCssVariables() {
      const variableNames = [
        "--ha-top-app-bar-width",
        "--mdc-drawer-width",
        "--sidebar-width",
        "--app-drawer-width",
      ];
      const elements = [
        document.documentElement,
        document.body,
        document.querySelector("home-assistant"),
        document.querySelector("home-assistant-main"),
      ].filter(Boolean);

      for (const element of elements) {
        const styles = window.getComputedStyle(element);
        for (const name of variableNames) {
          const value = styles.getPropertyValue(name);
          const parsed = this._parseCssLength(value);
          if (name === "--ha-top-app-bar-width") {
            if (parsed > 300 && parsed <= window.innerWidth) {
              return parsed;
            }
          }
        }
      }
      return 0;
    }

    _findBestContentTarget() {
      const configuredSelectors = this._config.content_selector
        ? [this._config.content_selector]
        : [];
      const selectors = [
        ...configuredSelectors,
        "hui-sections-view",
        "hui-view",
        "ha-panel-lovelace",
        "hui-root",
        "home-assistant-main",
        "partial-panel-resolver",
        "#view",
        ".view",
        ".container",
        "main",
        "app-drawer-layout",
        "ha-drawer",
      ];
      const uniqueSelectors = [...new Set(selectors.filter(Boolean))];
      const candidates = [];

      for (const element of this._findDeep(uniqueSelectors)) {
        const rect = element.getBoundingClientRect?.();
        if (!rect) {
          continue;
        }
        const expanded = this._expandToLargeParent(element, rect);
        const usedElement = expanded.element;
        const usedRect = expanded.rect;
        const score = this._scoreContentCandidate(usedElement, usedRect);
        if (score <= 0) {
          continue;
        }
        candidates.push({
          element: usedElement,
          rect: usedRect,
          score,
          source: this._selectorLabelForElement(usedElement),
        });
      }

      candidates.sort((left, right) => right.score - left.score);
      return candidates[0] || null;
    }

    _findDeep(selectorList) {
      const results = new Set();
      const queue = [document];
      const visitedRoots = new Set();

      while (queue.length) {
        const root = queue.shift();
        if (!root || visitedRoots.has(root)) {
          continue;
        }
        visitedRoots.add(root);

        if (typeof root.querySelectorAll === "function") {
          for (const selector of selectorList) {
            try {
              for (const element of root.querySelectorAll(selector)) {
                results.add(element);
              }
            } catch (_err) {
              // Ignore invalid selectors from custom configs.
            }
          }

          for (const element of root.querySelectorAll("*")) {
            if (element.shadowRoot) {
              queue.push(element.shadowRoot);
            }
          }
        }
      }

      return [...results];
    }

    _expandToLargeParent(element, rect) {
      let bestElement = element;
      let bestRect = rect;
      let current = element;
      while (current) {
        const parent = current.parentElement || current.getRootNode?.().host;
        if (!parent || typeof parent.getBoundingClientRect !== "function") {
          break;
        }
        const parentRect = parent.getBoundingClientRect();
        if (
          parentRect.width > bestRect.width * 1.08 &&
          parentRect.width <= window.innerWidth + 24 &&
          parentRect.height > 160
        ) {
          bestElement = parent;
          bestRect = parentRect;
        }
        current = parent;
      }
      return { element: bestElement, rect: bestRect };
    }

    _scoreContentCandidate(element, rect) {
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
      if (rect.width < 300 || rect.height < 160) {
        return 0;
      }
      if (rect.left < -16 || rect.right > viewportWidth + 16) {
        return 0;
      }

      const tagName = String(element?.tagName || "").toLowerCase();
      const id = String(element?.id || "");
      const className = typeof element?.className === "string" ? element.className : "";

      let score = rect.width;
      score += Math.min(rect.height, viewportHeight) * 0.15;
      if (tagName === "hui-sections-view") score += 240;
      if (tagName === "hui-view") score += 180;
      if (tagName === "ha-panel-lovelace") score += 220;
      if (tagName === "hui-root") score += 160;
      if (tagName === "home-assistant-main") score += 120;
      if (id === "view") score += 120;
      if (className.includes("view")) score += 80;
      if (className.includes("container")) score += 50;
      if (rect.width > viewportWidth * 0.92) score -= 220;
      if (tagName === "body" || tagName === "html") score -= 400;
      if (rect.left > viewportWidth * 0.45) score -= 200;
      return score;
    }

    _selectorLabelForElement(element) {
      const tagName = String(element?.tagName || "").toLowerCase();
      const id = element?.id ? `#${element.id}` : "";
      const className =
        typeof element?.className === "string" && element.className.trim()
          ? `.${element.className.trim().split(/\s+/).join(".")}`
          : "";
      return `${tagName}${id}${className}`;
    }

    _parseCssLength(value) {
      if (!value) return 0;
      const match = String(value).trim().match(/^([0-9.]+)px$/i);
      if (!match) return 0;
      const parsed = Number(match[1]);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    _storageKey() {
      return utils.storageKey(this._config.collection_key);
    }

    _onStorage(event) {
      if (event.key !== this._storageKey()) return;
      this._selection = this._loadSelection();
      this._render();
    }

    _onDocumentClick(event) {
      this._handleGlobalInteraction(event);
      if (!this._menuOpen) return;
      if (event.composedPath().includes(this)) return;
      this._menuOpen = false;
      this._render();
    }

    _onPointerUp(event) {
      this._handleGlobalInteraction(event);
    }

    _handleGlobalInteraction(event) {
      if (this._config.placement !== "fixed-bottom") {
        return;
      }
      const point = this._eventPoint(event);
      if (!point) {
        return;
      }
      const nearSidebar =
        point.x <= Math.max(320, (window.innerWidth || 0) * 0.28) && point.y <= 160;
      const delays = nearSidebar ? [50, 200, 500] : [100, 300];
      for (const delay of delays) {
        this._schedulePlacement(delay);
      }
    }

    _eventPoint(event) {
      if (typeof event?.clientX === "number" && typeof event?.clientY === "number") {
        return { x: event.clientX, y: event.clientY };
      }
      return null;
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

    _saveAndEmit(selection) {
      utils.saveSelection(this._config.collection_key, selection);
      this._selection = selection;
      this._emitSelection(selection);
      this._render();
    }

    _setSelection(periodKey, anchorDate) {
      const selection =
        periodKey === "custom_range"
          ? utils.buildCustomRangeSelection(
              utils.toDateOnly(anchorDate),
              utils.toDateOnly(anchorDate),
              this._config.collection_key,
              this._currentLocale()
            )
          : utils.buildSelection(
              periodKey,
              anchorDate,
              this._config.collection_key,
              this._currentLocale()
            );
      this._saveAndEmit(selection);
    }

    _setCustomRangeSelection(startDate, endDate) {
      const selection = utils.buildCustomRangeSelection(
        utils.toDateOnly(startDate),
        utils.toDateOnly(endDate),
        this._config.collection_key,
        this._currentLocale()
      );
      this._saveAndEmit(selection);
    }

    _shift(step) {
      const selection = utils.shiftSelection(
        this._selection,
        step,
        this._config.collection_key,
        this._currentLocale()
      );
      this._saveAndEmit(selection);
    }

    _resetNow() {
      const periodKey = this._selection?.period_key || this._config.default_period;
      if (periodKey === "custom_range") {
        const length = utils.customRangeLengthDays(this._selection);
        const endDay = utils.startOfDay(new Date());
        const startDay = utils.addDays(endDay, -(length - 1));
        this._setCustomRangeSelection(startDay, endDay);
        return;
      }
      this._setSelection(periodKey, new Date());
    }

    _syncNativePicker() {
      const picker = this.shadowRoot?.querySelector("ha-date-range-picker");
      if (!picker) return;
      const selection = this._selection || this._loadSelection();
      const startDate = utils.selectionStartDate(selection) || utils.startOfDay(new Date());
      const endDate = utils.selectionEndInclusive(selection) || startDate;
      if (this._hass) {
        picker.hass = this._hass;
      }
      picker.startDate = startDate;
      picker.endDate = endDate;
      picker.minimal = true;
      picker.backdrop = true;
      picker.setAttribute("minimal", "");
      picker.setAttribute("backdrop", "");
    }

    _handleNativeRangeChange(event) {
      this._debugLayout("native-date-range-event", {
        type: event?.type || "unknown",
        detail: event?.detail || null,
      });
      const detailValue = event?.detail?.value;
      const detailRange = event?.detail?.range;
      const detailStart =
        event?.detail?.startDate || event?.detail?.start || detailRange?.startDate;
      const detailEnd =
        event?.detail?.endDate || event?.detail?.end || detailRange?.endDate;
      const target = event?.target;
      const startDate =
        utils.parseDate(detailStart) ||
        utils.parseDate(detailValue?.startDate) ||
        utils.parseDate(detailValue?.start) ||
        utils.parseDate(target?.value?.startDate) ||
        utils.parseDate(target?.value?.start) ||
        utils.parseDate(target?.startDate);
      const endDate =
        utils.parseDate(detailEnd) ||
        utils.parseDate(detailValue?.endDate) ||
        utils.parseDate(detailValue?.end) ||
        utils.parseDate(target?.value?.endDate) ||
        utils.parseDate(target?.value?.end) ||
        utils.parseDate(target?.endDate);
      if (!startDate || !endDate) {
        this._debugLayout("native-date-range-event-ignored", {
          reason: "missing-start-or-end",
          detail: event?.detail || null,
        });
        return;
      }
      this._menuOpen = false;
      this._setCustomRangeSelection(startDate, endDate);
    }

    _debugLayout(message, payload) {
      if (!this._config.debug_layout) {
        return;
      }
      console.debug("[HAGym date selection]", message, payload);
    }

    _renderMenuButton(action, label, extra = "") {
      return `<button class="menu-item" ${extra} data-menu-action="${action}">${utils.escapeHtml(
        label
      )}</button>`;
    }

    _renderDatePickerControl() {
      if (this._nativePickerAvailable()) {
        return `
          <section class="date-picker-icon" aria-label="Zeitraum waehlen">
            <span class="date-picker-visual" aria-hidden="true">&#128197;</span>
            <ha-date-range-picker class="native-picker" minimal backdrop></ha-date-range-picker>
          </section>
        `;
      }
      if (this._config.use_native_date_picker && this._config.debug_layout) {
        console.warn("[HAGym date selection] ha-date-range-picker not available, using fallback");
      }
      return `
        <button class="icon-btn calendar-btn" data-action="toggle-menu" title="Zeitraum waehlen" aria-label="Zeitraum waehlen">
          &#128197;
        </button>
      `;
    }

    _renderBody(selection, menuPosX, menuPosY) {
      return `
        <div class="shell ${this._config.compact ? "compact" : ""}">
          <div class="bar">
            ${this._renderDatePickerControl()}
            <div class="label" title="${utils.escapeHtml(selection.label || "Diese Woche")}">${utils.escapeHtml(
              selection.label || "Diese Woche"
            )}</div>
            <button class="icon-btn" data-action="prev" title="Vorheriger Zeitraum" aria-label="Vorheriger Zeitraum">&#x2039;</button>
            <button class="icon-btn" data-action="next" title="Naechster Zeitraum" aria-label="Naechster Zeitraum">&#x203A;</button>
            <button class="icon-btn menu-trigger" data-action="toggle-menu" title="Zeitraum-Menue" aria-label="Zeitraum-Menue">&#8942;</button>
          </div>
          ${
            this._config.debug_layout
              ? `<div class="debug-line">${utils.escapeHtml(
                  this._lastLayoutDebug || "layout: unknown"
                )}</div>`
              : ""
          }
          ${
            this._menuOpen
              ? `<div class="menu" style="${menuPosX}${menuPosY}">
                  ${this._renderMenuButton("now", "Jetzt")}
                  ${this._renderMenuButton("today", "Heute")}
                  ${this._renderMenuButton("yesterday", "Gestern")}
                  ${this._renderMenuButton("this_week", "Diese Woche")}
                  ${this._renderMenuButton("this_month", "Dieser Monat")}
                  ${this._renderMenuButton("this_quarter", "Dieses Quartal")}
                  ${this._renderMenuButton("this_year", "Dieses Jahr")}
                  ${this._renderMenuButton("last_7_days", "Letzte 7 Tage")}
                  ${this._renderMenuButton("last_30_days", "Letzte 30 Tage")}
                  ${this._renderMenuButton("last_365_days", "Letzte 365 Tage")}
                  ${this._renderMenuButton("last_12_months", "Letzte 12 Monate")}
                </div>`
              : ""
          }
        </div>
      `;
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

      const body = this._renderBody(selection, menuPosX, menuPosY);
      this.shadowRoot.innerHTML = `
        ${this._style()}
        ${
          this._config.placement === "fixed-bottom"
            ? `<div class="hagym-fixed-row ${this._config.full_width_row ? "full-row" : ""}">
                 <div class="hagym-fixed-backdrop"></div>
                 <ha-card class="hagym-date-content">${body}</ha-card>
               </div>`
            : `<ha-card class="inline-date-content">${body}</ha-card>`
        }
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
      this.shadowRoot.querySelectorAll("[data-menu-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const action = button.getAttribute("data-menu-action") || this._config.default_period;
          this._menuOpen = false;
          if (action === "now") {
            this._resetNow();
            return;
          }
          this._setSelection(action, new Date());
        });
      });

      const picker = this.shadowRoot.querySelector("ha-date-range-picker");
      if (picker) {
        for (const eventName of [
          "value-changed",
          "date-range-picked",
          "change",
          "selected",
        ]) {
          picker.addEventListener(eventName, (event) => this._handleNativeRangeChange(event));
        }
      }
      this._syncNativePicker();
    }

    _style() {
      return `
        <style>
          :host {
            display: block;
          }

          :host([data-fixed-bottom]) {
            display: block;
            height: 0;
            overflow: visible;
          }

          .inline-date-content,
          .hagym-date-content {
            overflow: visible;
            border-radius: 18px;
            background:
              linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
              var(--ha-card-background, var(--card-background-color, #fff));
            backdrop-filter: blur(10px);
          }

          .hagym-fixed-row {
            position: fixed;
            left: var(--hagym-content-left, 0px);
            width: var(--hagym-content-width, 100vw);
            right: auto;
            bottom: calc(var(--hagym-bottom-offset, 16px) + env(safe-area-inset-bottom, 0px));
            display: flex;
            justify-content: center;
            align-items: center;
            box-sizing: border-box;
            padding: 0 16px;
            pointer-events: none;
            z-index: var(--hagym-z-index, 10);
          }

          .hagym-fixed-backdrop {
            position: absolute;
            inset: 0;
            pointer-events: none;
          }

          .hagym-date-content {
            pointer-events: auto;
            width: min(var(--hagym-max-width, 900px), 100%);
            border-radius: 22px;
          }

          .shell {
            position: relative;
            padding: 8px;
          }

          .shell.compact {
            padding: 6px;
          }

          .debug-line {
            margin-top: 6px;
            font-size: 0.7rem;
            color: var(--secondary-text-color);
            opacity: 0.85;
          }

          .bar {
            display: grid;
            grid-template-columns: auto minmax(0, 1fr) repeat(3, auto);
            gap: 8px;
            align-items: center;
            padding: 8px;
            border-radius: 999px;
            border: 1px solid var(--divider-color);
            background: color-mix(in srgb, var(--card-background-color, #fff) 76%, transparent);
            min-width: 0;
          }

          .compact .bar {
            gap: 6px;
            padding: 6px;
          }

          .date-picker-icon {
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 34px;
            min-width: 34px;
            height: 34px;
            border-radius: 50%;
            background: color-mix(in srgb, var(--primary-color) 10%, transparent);
            overflow: hidden;
          }

          .compact .date-picker-icon {
            width: 32px;
            min-width: 32px;
            height: 32px;
          }

          .date-picker-visual {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
            font-size: 16px;
            line-height: 1;
            color: var(--primary-color);
            pointer-events: none;
          }

          ha-date-range-picker.native-picker {
            position: absolute;
            inset: 0;
            display: block;
            opacity: 0.02;
            min-width: 0;
            z-index: 1;
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

          .compact .label {
            padding: 7px 10px;
            font-size: 0.9rem;
          }

          .icon-btn {
            width: 34px;
            min-width: 34px;
            height: 34px;
            border-radius: 50%;
            background: var(--ha-card-background, var(--card-background-color, #fff));
            border: 1px solid color-mix(in srgb, var(--divider-color) 70%, transparent);
            font-size: 1rem;
            font-weight: 700;
          }

          .compact .icon-btn {
            width: 32px;
            min-width: 32px;
            height: 32px;
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

          @media (max-width: 870px) {
            .hagym-fixed-row {
              left: 0px;
              width: 100vw;
              padding: 0 12px;
              bottom: calc(12px + env(safe-area-inset-bottom, 0px));
            }
          }

          @media (max-width: 600px) {
            .bar {
              gap: 6px;
            }

            .label {
              font-size: 0.86rem;
              padding-left: 10px;
              padding-right: 10px;
            }

            .menu {
              min-width: min(240px, calc(100vw - 32px));
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
