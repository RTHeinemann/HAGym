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
      };
    }

    set hass(hass) {
      this._hass = hass;
    }

    connectedCallback() {
      if (!ensureUtils()) {
        this._renderMissingUtils();
        return;
      }
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
      const normalizedDefault = ensureUtils()
        ? defaultPeriod === "custom_range"
          ? "this_week"
          : utils.normalizePeriod(defaultPeriod)
        : "this_week";

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
        desktop_sidebar_offset: desktopSidebarOffset,
        content_selector: contentSelector,
        debug_layout: config?.debug_layout === true,
        full_width_row: config?.full_width_row !== false,
        max_width: Math.max(280, Number(config?.max_width) || 900),
        bottom_offset: Math.max(0, Number(config?.bottom_offset) || 16),
        z_index: Math.max(1, Number(config?.z_index) || 10),
      };
      this._selection = ensureUtils() ? this._loadSelection() : null;
      this._applyPlacement();
      this._startMutationObserver();
      this._scheduleInitialPlacementPasses();
      this._render();
    }

    getCardSize() {
      return this._config.placement === "fixed-bottom" ? 1 : 2;
    }

    _renderMissingUtils() {
      if (!this.shadowRoot) return;
      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="selector-shell">
            <div class="period-bar">
              <div class="period-label">${String(this._config?.collection_key || "hagym")}</div>
            </div>
            <div class="empty-state">${missingUtilsMessage}</div>
          </div>
        </ha-card>
      `;
    }

    _currentLocale() {
      const language =
        this._hass?.locale?.language || document.documentElement.lang || navigator.language;
      return language || "de-DE";
    }

    _language() {
      return this._currentLocale();
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
      if (!ensureUtils()) return null;
      return utils.loadSelection(
        this._config.collection_key,
        this._config.default_period,
        this._currentLocale(),
        "compact"
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
      if (!ensureUtils()) return `hagym-period-selection:${this._config.collection_key}`;
      return utils.storageKey(this._config.collection_key);
    }

    _onStorage(event) {
      if (!ensureUtils()) {
        this._renderMissingUtils();
        return;
      }
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
      if (!ensureUtils()) {
        this._renderMissingUtils();
        return;
      }
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
              this._currentLocale(),
              "compact"
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
        this._currentLocale(),
        "compact"
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
                  ${this._renderMenuButton("last_12_weeks", "Letzte 12 Wochen")}
                  ${this._renderMenuButton("last_12_months", "Letzte 12 Monate")}
                </div>`
              : ""
          }
        </div>
      `;
    }

    _render() {
      if (!this.shadowRoot) return;
      if (!ensureUtils()) {
        this._renderMissingUtils();
        return;
      }
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
      description: "Global HAGym period selector, best used as a sections-view footer card.",
      preview: true,
    });
  }
})();
