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
        desktop_sidebar_offset: "auto",
        content_selector: null,
        debug_layout: false,
        max_width: 720,
        bottom_offset: 16,
        z_index: 10,
      };
      this._selection = null;
      this._menuOpen = false;
      this._resizeObserver = null;
      this._mutationObserver = null;
      this._contentResizeObserver = null;
      this._observedContentElement = null;
      this._pendingPlacementTimers = new Set();
      this._onStorage = this._onStorage.bind(this);
      this._onOutsideClick = this._onOutsideClick.bind(this);
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
        desktop_sidebar_offset: "auto",
        content_selector: null,
        debug_layout: false,
        max_width: 720,
        bottom_offset: 16,
        z_index: 10,
      };
    }

    connectedCallback() {
      window.addEventListener("storage", this._onStorage);
      window.addEventListener("click", this._onOutsideClick, true);
      window.addEventListener("resize", this._onResize);
      this._startLayoutObserver();
      this._startMutationObserver();
      this._selection = this._loadSelection();
      this._applyPlacement();
      this._scheduleInitialPlacementPasses();
      this._render();
    }

    disconnectedCallback() {
      window.removeEventListener("storage", this._onStorage);
      window.removeEventListener("click", this._onOutsideClick, true);
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
      const maxWidth = Math.max(280, Number(config?.max_width) || 720);
      const bottomOffset = Math.max(0, Number(config?.bottom_offset) || 16);
      const zIndex = Math.max(1, Number(config?.z_index) || 10);
      const contentSelector =
        config?.content_selector && String(config.content_selector).trim()
          ? String(config.content_selector).trim()
          : null;
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
        desktop_sidebar_offset: desktopSidebarOffset,
        content_selector: contentSelector,
        debug_layout: config?.debug_layout === true,
        max_width: maxWidth,
        bottom_offset: bottomOffset,
        z_index: zIndex,
      };
      this._selection = this._loadSelection();
      this._applyPlacement();
      this._startMutationObserver();
      this._scheduleInitialPlacementPasses();
      this._render();
    }

    getCardSize() {
      return this._config.placement === "fixed-bottom" ? 1 : 2;
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

    _stopContentObserver() {
      this._contentResizeObserver?.disconnect?.();
      this._contentResizeObserver = null;
      this._observedContentElement = null;
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
        }
      });
      this._contentResizeObserver.observe(element);
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
      return utils.loadSelection(this._config.collection_key, this._config.default_period);
    }

    _applyPlacement() {
      const fixed = this._config.placement === "fixed-bottom";
      this.toggleAttribute("data-fixed-bottom", fixed);
      this.style.position = fixed ? "fixed" : "";
      this.style.transform = fixed ? "translateX(-50%)" : "";
      this.style.pointerEvents = "auto";
      if (!fixed) {
        this.style.left = "";
        this.style.bottom = "";
        this.style.width = "";
        this.style.maxWidth = "";
        this.style.zIndex = "";
        this.style.setProperty("--hagym-date-selector-left", "");
        this.style.setProperty("--hagym-date-selector-width", "");
        return;
      }

      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
      const isDesktop = viewportWidth >= 870;
      const maxWidth = this._config.max_width;
      const horizontalPadding = isDesktop ? 32 : 24;
      let left = viewportWidth / 2;
      let cardWidth = Math.min(maxWidth, Math.max(280, viewportWidth - horizontalPadding));
      let source = "mobile";

      if (isDesktop) {
        const contentTarget = this._findBestContentTarget();
        const contentRect = contentTarget?.rect || null;
        if (
          this._config.desktop_sidebar_offset === "auto" &&
          contentRect &&
          contentRect.width > 300
        ) {
          left = contentRect.left + contentRect.width / 2;
          cardWidth = Math.min(maxWidth, Math.max(280, contentRect.width - horizontalPadding));
          source = contentTarget.source;
          this._observeContentElement(contentTarget.element);
          this._debugLayout("content-rect", {
            source,
            left: Math.round(left),
            width: Math.round(cardWidth),
            rect: this._rectToDebug(contentRect),
          });
        } else {
          const sidebarOffset = this._resolveDesktopSidebarOffset();
          const contentWidth = Math.max(280, viewportWidth - sidebarOffset - horizontalPadding);
          cardWidth = Math.min(maxWidth, contentWidth);
          left = sidebarOffset + Math.max(0, (viewportWidth - sidebarOffset) / 2);
          source = typeof this._config.desktop_sidebar_offset === "number" ? "manual-offset" : "sidebar-offset";
          this._stopContentObserver();
          this._debugLayout("offset-fallback", {
            source,
            sidebarOffset,
            left: Math.round(left),
            width: Math.round(cardWidth),
          });
        }
      } else {
        this._stopContentObserver();
      }

      const bottomOffset = isDesktop
        ? this._config.bottom_offset
        : Math.max(12, this._config.bottom_offset - 4);

      this.style.left = `${Math.round(left)}px`;
      this.style.bottom = `calc(${bottomOffset}px + env(safe-area-inset-bottom, 0px))`;
      this.style.width = `${Math.round(cardWidth)}px`;
      this.style.maxWidth = `${Math.round(cardWidth)}px`;
      this.style.zIndex = String(this._config.z_index);
      this.style.setProperty("--hagym-date-selector-left", `${Math.round(left)}px`);
      this.style.setProperty("--hagym-date-selector-width", `${Math.round(cardWidth)}px`);
    }

    _resolveDesktopSidebarOffset() {
      if (this._config.desktop_sidebar_offset === 0) {
        return 0;
      }
      if (typeof this._config.desktop_sidebar_offset === "number") {
        return this._config.desktop_sidebar_offset;
      }

      const contentLeft = this._detectContentLeftOffset();
      if (contentLeft > 0) {
        return contentLeft;
      }

      const variableOffset = this._detectSidebarWidthFromCssVariables();
      if (variableOffset > 0) {
        return variableOffset;
      }

      return 256;
    }

    _findBestContentTarget() {
      const configuredSelectors = this._config.content_selector
        ? [this._config.content_selector]
        : [];
      const candidateSelectors = [
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
      const seen = new Set();
      const dedupedSelectors = candidateSelectors.filter((selector) => {
        if (!selector || seen.has(selector)) {
          return false;
        }
        seen.add(selector);
        return true;
      });

      const candidates = [];
      for (const element of this._findDeep(dedupedSelectors)) {
        const rect = element.getBoundingClientRect?.();
        if (!rect) {
          continue;
        }
        const expanded = this._expandToLargeParent(element, rect);
        const usedRect = expanded?.rect || rect;
        const usedElement = expanded?.element || element;
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
              // Ignore invalid selectors in custom configs.
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
        if (parentRect.width > bestRect.width * 1.08 && parentRect.width <= window.innerWidth + 24) {
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
      const className =
        typeof element?.className === "string" ? element.className : "";
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

    _rectToDebug(rect) {
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    }

    _debugLayout(message, payload) {
      if (!this._config.debug_layout) {
        return;
      }
      console.debug("[HAGym date selection]", message, payload);
    }

    _detectContentLeftOffset() {
      const root = document.querySelector("home-assistant");
      const searchTargets = [
        document.querySelector("home-assistant-main"),
        document.querySelector("ha-panel-lovelace"),
        document.querySelector("hui-root"),
      ].filter(Boolean);

      if (root?.shadowRoot) {
        const rootTargets = [
          root.shadowRoot.querySelector("home-assistant-main"),
          root.shadowRoot.querySelector("partial-panel-resolver"),
          root.shadowRoot.querySelector("ha-drawer"),
        ].filter(Boolean);
        searchTargets.push(...rootTargets);
      }

      let bestLeft = 0;
      for (const target of searchTargets) {
        const rect = target?.getBoundingClientRect?.();
        if (!rect) continue;
        if (rect.width <= 0) continue;
        if (rect.left > bestLeft && rect.left < window.innerWidth * 0.6) {
          bestLeft = rect.left;
        }
      }
      return Math.max(0, Math.round(bestLeft));
    }

    _detectSidebarWidthFromCssVariables() {
      const variableNames = [
        "--mdc-drawer-width",
        "--sidebar-width",
        "--app-drawer-width",
      ];
      const elements = [
        document.documentElement,
        document.body,
        document.querySelector("home-assistant"),
      ].filter(Boolean);

      for (const element of elements) {
        const styles = window.getComputedStyle(element);
        for (const name of variableNames) {
          const value = styles.getPropertyValue(name);
          const parsed = this._parseCssLength(value);
          if (parsed > 0) {
            return parsed;
          }
        }
      }
      return 0;
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

    _onOutsideClick(event) {
      if (this._config.placement === "fixed-bottom") {
        this._schedulePlacement(100);
        this._schedulePlacement(300);
      }
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
