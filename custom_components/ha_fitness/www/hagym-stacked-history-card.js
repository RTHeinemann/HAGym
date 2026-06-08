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
  const startOfMonthLocal = (date) =>
    new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);

  const SCOPE_META = {
    exercises: {
      arrayKey: "exercises",
      idField: "exercise_id",
      nameField: "exercise_name",
    },
    equipment: {
      arrayKey: "equipment",
      idField: "equipment_id",
      nameField: "equipment_name",
    },
    muscle_groups: {
      arrayKey: "muscle_groups",
      idField: "muscle_group_id",
      nameField: "muscle_group_name",
    },
    metric_types: {
      arrayKey: "metric_types",
      idField: "metric_type",
      nameField: "metric_type_name",
    },
  };

  const DEFAULT_UNITS = {
    strength_volume_kg: "kg",
    activity_load_score: "load",
    duration_minutes: "min",
    distance_km: "km",
    calories: "kcal",
    steps: "steps",
    reps: "reps",
    sets: "Sets",
    entries: "Entries",
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

  const PALETTE = [
    "#1f8ef1",
    "#00a980",
    "#ff8a34",
    "#db5461",
    "#7067cf",
    "#00bcd4",
    "#f06292",
    "#8bc34a",
    "#ffca28",
    "#8d6e63",
    "#42a5f5",
    "#26c6da",
  ];

  class HAGymStackedHistoryCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {
        title: "Verlauf",
        daily_metric_entity: null,
        collection_key: "hagym",
        scope: "muscle_groups",
        metric: "strength_volume_kg",
        unit: null,
        limit: 10,
        chart_mode: "stacked_bar",
        interactive_legend: true,
        persist_legend_state: false,
      };
      this._selection = null;
      this._tooltip = null;
      this._disabledSeries = new Set();
      this._onPeriodChanged = this._onPeriodChanged.bind(this);
      this._onStorage = this._onStorage.bind(this);
      this._onDocumentPointer = this._onDocumentPointer.bind(this);
    }

    static getStubConfig() {
      return {
        type: "custom:hagym-stacked-history-card",
        title: "Trainingsvolumen pro Muskelgruppe",
        daily_metric_entity: "sensor.ha_fitness_personal_daily_metric_statistics",
        collection_key: "hagym",
        scope: "muscle_groups",
        metric: "strength_volume_kg",
        unit: "kg",
        limit: 10,
        chart_mode: "stacked_bar",
        interactive_legend: true,
        persist_legend_state: false,
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
      window.addEventListener("pointerdown", this._onDocumentPointer, true);
      this._selection = this._loadSelection();
      this._render();
    }

    disconnectedCallback() {
      window.removeEventListener("hagym-period-changed", this._onPeriodChanged);
      window.removeEventListener("hagym-date-selection-changed", this._onPeriodChanged);
      window.removeEventListener("storage", this._onStorage);
      window.removeEventListener("pointerdown", this._onDocumentPointer, true);
    }

    setConfig(config) {
      if (!config?.daily_metric_entity) {
        throw new Error("hagym-stacked-history-card: daily_metric_entity is required");
      }
      const nextPersistLegendState = config.persist_legend_state === true;
      const nextCollectionKey = config.collection_key ? String(config.collection_key) : "hagym";
      const nextScope = SCOPE_META[config.scope] ? config.scope : "muscle_groups";
      const nextMetric = String(config.metric || "strength_volume_kg");
      const identityChanged =
        this._config.collection_key !== nextCollectionKey ||
        this._config.scope !== nextScope ||
        this._config.metric !== nextMetric;
      const persistModeChanged = this._config.persist_legend_state !== nextPersistLegendState;
      this._config = {
        title: config.title ? String(config.title) : "Verlauf",
        daily_metric_entity: String(config.daily_metric_entity),
        collection_key: nextCollectionKey,
        scope: nextScope,
        metric: nextMetric,
        unit: config.unit ? String(config.unit) : DEFAULT_UNITS[nextMetric] || "",
        limit: Math.max(1, Number(config.limit) || 10),
        chart_mode: config.chart_mode === "stacked_bar" ? "stacked_bar" : "stacked_bar",
        interactive_legend: config.interactive_legend !== false,
        persist_legend_state: nextPersistLegendState,
      };
      if (identityChanged || persistModeChanged) {
        this._disabledSeries = this._loadDisabledSeries();
      }
      this._selection = ensureUtils() ? this._loadSelection() : null;
      this._tooltip = null;
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
            <div class="title">${this._escape(this._config?.title || "Verlauf")}</div>
            <div class="warning">${missingUtilsMessage}</div>
          </div>
        </ha-card>
      `;
    }

    _loadSelection() {
      if (!ensureUtils()) return null;
      return utils.loadSelection(
        this._config.collection_key,
        "this_week",
        document.documentElement.lang || navigator.language
      );
    }

    _legendStorageKey() {
      return `hagym-stacked-history-disabled:${this._config.collection_key}:${this._config.scope}:${this._config.metric}`;
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

    _clearTooltip() {
      this._tooltip = null;
    }

    _toggleSeries(seriesKey) {
      const key = String(seriesKey || "").trim();
      if (!key || !this._config.interactive_legend) return;
      if (this._disabledSeries.has(key)) {
        this._disabledSeries.delete(key);
      } else {
        this._disabledSeries.add(key);
      }
      this._clearTooltip();
      this._saveDisabledSeries();
      this._render();
    }

    _onStorage(event) {
      if (!ensureUtils()) {
        this._renderMissingUtils();
        return;
      }
      if (event.key === `hagym-period-selection:${this._config.collection_key}`) {
        this._selection = this._loadSelection();
        this._tooltip = null;
        this._render();
        return;
      }
      if (this._config.persist_legend_state && event.key === this._legendStorageKey()) {
        this._disabledSeries = this._loadDisabledSeries();
        this._tooltip = null;
        this._render();
      }
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
      this._tooltip = null;
      this._render();
    }

    _onDocumentPointer(event) {
      if (!this._tooltip?.pinned) return;
      if (event.composedPath().includes(this)) return;
      this._tooltip = null;
      this._render();
    }

    _escape(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    _num(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    _format(value, digits = 1) {
      return this._num(value).toLocaleString(document.documentElement.lang || undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
    }

    _extractDailyRows(attributes) {
      if (!attributes || typeof attributes !== "object") {
        return [];
      }
      const collection = attributes?.[this._config.collection_key];
      const candidates = [
        collection?.days,
        attributes?.days,
        attributes?.history,
        collection?.history,
      ];
      for (const candidate of candidates) {
        if (Array.isArray(candidate)) {
          return candidate
            .map((row) => this._normalizeDayRow(row))
            .filter(Boolean)
            .sort((left, right) => left.day_start.localeCompare(right.day_start));
        }
      }

      const objectCandidates = [collection, attributes];
      for (const candidate of objectCandidates) {
        if (!candidate || Array.isArray(candidate) || typeof candidate !== "object") continue;
        const rows = Object.values(candidate)
          .map((row) => this._normalizeDayRow(row))
          .filter(Boolean);
        if (rows.length) {
          return rows.sort((left, right) => left.day_start.localeCompare(right.day_start));
        }
      }
      return [];
    }

    _normalizeDayRow(row) {
      if (!row || typeof row !== "object") return null;
      const dateOnly =
        typeof row.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(row.date) ? row.date : null;
      const start = utils.parseDate(row.day_start) || (dateOnly ? utils.parseDateOnly(dateOnly) : null);
      if (!start) return null;
      const end = utils.parseDate(row.day_end) || utils.addDays(start, 1);
      return {
        ...row,
        date: dateOnly || utils.toDateOnly(start),
        day_start: start.toISOString(),
        day_end: end.toISOString(),
      };
    }

    _selectionDays(selection) {
      const start = utils.selectionStartDate(selection);
      const end = utils.selectionEndInclusive(selection);
      if (!start || !end) return 0;
      return Math.max(
        1,
        Math.round((utils.startOfDay(end).getTime() - utils.startOfDay(start).getTime()) / 86400000) + 1
      );
    }

    _weekLabel(date) {
      const utcDate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
      utcDate.setUTCDate(utcDate.getUTCDate() + 4 - (utcDate.getUTCDay() || 7));
      const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
      const week = Math.ceil(((utcDate - yearStart) / 86400000 + 1) / 7);
      return `KW ${String(week).padStart(2, "0")}`;
    }

    _bucketPlan(selection) {
      const start = utils.selectionStartDate(selection);
      const endExclusive = utils.selectionEndExclusive(selection);
      const endInclusive = utils.selectionEndInclusive(selection);
      if (!start || !endExclusive || !endInclusive) {
        return { subtitle: selection?.label || "Diese Woche", mode: "day", buckets: [] };
      }
      const key = String(selection?.period_key || "this_week");
      const days = this._selectionDays(selection);
      const locale = document.documentElement.lang || navigator.language;

      const buildDayBuckets = (bucketStart, bucketEndExclusive, labelFormatter) => {
        const buckets = [];
        for (
          let cursor = utils.startOfDay(bucketStart);
          cursor < bucketEndExclusive;
          cursor = utils.addDays(cursor, 1)
        ) {
          buckets.push({
            key: utils.toDateOnly(cursor),
            start: cursor.toISOString(),
            end: utils.addDays(cursor, 1).toISOString(),
            label: labelFormatter(cursor),
            fullLabel: new Intl.DateTimeFormat(locale || undefined, {
              weekday: "short",
              day: "2-digit",
              month: "2-digit",
            }).format(cursor),
          });
        }
        return buckets;
      };

      const buildWeekBuckets = (bucketStart, bucketEndExclusive) => {
        const buckets = [];
        for (
          let cursor = utils.startOfWeek(bucketStart);
          cursor < bucketEndExclusive;
          cursor = utils.addDays(cursor, 7)
        ) {
          buckets.push({
            key: cursor.toISOString(),
            start: cursor.toISOString(),
            end: utils.addDays(cursor, 7).toISOString(),
            label: this._weekLabel(cursor),
            fullLabel: `${this._weekLabel(cursor)} ${cursor.getFullYear()}`,
          });
        }
        return buckets;
      };

      const buildMonthBuckets = (bucketStart, bucketEndExclusive) => {
        const buckets = [];
        for (
          let cursor = startOfMonthLocal(bucketStart);
          cursor < bucketEndExclusive;
          cursor = utils.addMonths(cursor, 1)
        ) {
          buckets.push({
            key: `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`,
            start: cursor.toISOString(),
            end: utils.addMonths(cursor, 1).toISOString(),
            label: new Intl.DateTimeFormat(locale || undefined, { month: "short" }).format(cursor),
            fullLabel: new Intl.DateTimeFormat(locale || undefined, {
              month: "long",
              year: "numeric",
            }).format(cursor),
          });
        }
        return buckets;
      };

      if (key === "today" || key === "yesterday") {
        const weekStart = utils.startOfWeek(start);
        return {
          subtitle: selection.label || "Diese Woche",
          mode: "day",
          buckets: buildDayBuckets(weekStart, utils.addDays(weekStart, 7), (date) =>
            new Intl.DateTimeFormat(locale || undefined, { weekday: "short" }).format(date)
          ),
        };
      }

      if (key === "this_week") {
        return {
          subtitle: selection.label || "Diese Woche",
          mode: "day",
          buckets: buildDayBuckets(start, endExclusive, (date) =>
            new Intl.DateTimeFormat(locale || undefined, { weekday: "short" }).format(date)
          ),
        };
      }

      if (key === "last_12_weeks") {
        return {
          subtitle: selection.label || "Letzte 12 Wochen",
          mode: "week",
          buckets: buildWeekBuckets(start, endExclusive),
        };
      }

      if (
        key === "this_year" ||
        key === "last_365_days" ||
        key === "last_12_months" ||
        (key === "custom_range" && days > 62)
      ) {
        return {
          subtitle: selection.label || "Monatsansicht",
          mode: "month",
          buckets: buildMonthBuckets(start, endExclusive),
        };
      }

      if (
        key === "this_month" ||
        key === "last_30_days" ||
        (key === "custom_range" && days > 14 && days <= 62)
      ) {
        const labelFormatter =
          key === "this_month"
            ? (date) =>
                new Intl.DateTimeFormat(locale || undefined, {
                  day: "numeric",
                }).format(date)
            : (date) =>
                new Intl.DateTimeFormat(locale || undefined, {
                  day: "numeric",
                  month: "short",
                }).format(date);
        return {
          subtitle: selection.label || "Monat",
          mode: "day",
          buckets: buildDayBuckets(start, endExclusive, labelFormatter),
        };
      }

      return {
        subtitle: selection.label || "Zeitraum",
        mode: "day",
        buckets: buildDayBuckets(start, endExclusive, (date) =>
          new Intl.DateTimeFormat(locale || undefined, {
            day: "numeric",
            month: "short",
          }).format(date)
        ),
      };
    }

    _metricValue(item) {
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

    _scopeItemsForRow(row) {
      if (this._config.scope === "metric_types") {
        const direct = Array.isArray(row.metric_types) ? row.metric_types : null;
        if (direct?.length) {
          return direct.map((item) => ({
            id: String(item.metric_type || item.id || "unknown"),
            name: String(item.metric_type_name || item.name || item.metric_type || item.id || "Unknown"),
            value: this._metricValue(item),
          }));
        }
        return METRIC_TYPE_FALLBACKS.map(([id, field, name]) => ({
          id,
          name,
          value:
            this._config.metric === "activity_load_score"
              ? this._num(row[field])
              : id === "strength"
                ? this._num(row[this._config.metric])
                : 0,
        })).filter((item) => item.value > 0);
      }

      const meta = SCOPE_META[this._config.scope];
      const list = Array.isArray(row?.[meta.arrayKey]) ? row[meta.arrayKey] : [];
      return list
        .map((item) => ({
          id: String(item?.[meta.idField] || "").trim(),
          name: String(item?.[meta.nameField] || item?.[meta.idField] || "").trim(),
          value: this._metricValue(item),
        }))
        .filter((item) => item.id && item.value > 0);
    }

    _rowOverlapsBucket(row, bucket) {
      const rowStart = utils.parseDate(row?.day_start);
      const rowEnd = utils.parseDate(row?.day_end);
      const bucketStart = utils.parseDate(bucket?.start);
      const bucketEnd = utils.parseDate(bucket?.end);
      if (!rowStart || !rowEnd || !bucketStart || !bucketEnd) return false;
      return rowStart < bucketEnd && rowEnd > bucketStart;
    }

    _aggregateChart(rows, buckets) {
      const filteredRows = rows.filter((row) =>
        buckets.some((bucket) => this._rowOverlapsBucket(row, bucket))
      );
      const totals = new Map();
      for (const row of filteredRows) {
        for (const item of this._scopeItemsForRow(row)) {
          totals.set(item.id, {
            id: item.id,
            name: item.name,
            total: this._num(totals.get(item.id)?.total) + item.value,
          });
        }
      }

      const ranked = [...totals.values()].sort(
        (left, right) => right.total - left.total || left.name.localeCompare(right.name)
      );
      const topItems = ranked.slice(0, this._config.limit);
      const topIds = new Set(topItems.map((item) => item.id));
      const showOther = ranked.length > topItems.length;

      const series = topItems.map((item) => ({
        id: item.id,
        name: item.name,
        color: this._colorForKey(item.id),
      }));
      if (showOther) {
        series.push({
          id: "__other__",
          name: "Andere",
          color: "#90a4ae",
        });
      }

      const activeSeries = series.filter((entry) => !this._disabledSeries.has(entry.id));
      const activeIds = new Set(activeSeries.map((entry) => entry.id));

      const bucketRows = buckets.map((bucket) => {
        const values = new Map();
        for (const row of filteredRows) {
          if (!this._rowOverlapsBucket(row, bucket)) continue;
          for (const item of this._scopeItemsForRow(row)) {
            const targetId = topIds.has(item.id) ? item.id : "__other__";
            values.set(targetId, this._num(values.get(targetId)) + item.value);
          }
        }
        const allParts = series
          .map((entry) => ({
            id: entry.id,
            name: entry.name,
            color: entry.color,
            value: this._num(values.get(entry.id)),
          }))
          .filter((entry) => entry.value > 0);
        const parts = allParts.filter((entry) => activeIds.has(entry.id));
        const total = parts.reduce((sum, entry) => sum + entry.value, 0);
        return {
          ...bucket,
          allParts,
          parts,
          total,
        };
      });

      return {
        series,
        activeSeries,
        buckets: bucketRows,
        maxTotal: Math.max(0, ...bucketRows.map((bucket) => bucket.total)),
      };
    }

    _colorForKey(key) {
      let hash = 0;
      for (const char of String(key)) {
        hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
      }
      return PALETTE[hash % PALETTE.length];
    }

    _tickValues(maxValue) {
      const roundedMax = maxValue <= 0 ? 1 : maxValue;
      return [0, roundedMax / 3, (roundedMax / 3) * 2, roundedMax];
    }

    _displayLabel(bucketCount, bucket, index) {
      const every = bucketCount > 16 ? Math.ceil(bucketCount / 8) : bucketCount > 10 ? 2 : 1;
      return index % every === 0 ? bucket.label : "";
    }

    _renderTooltip() {
      if (!this._tooltip?.bucket) return "";
      const bucket = this._tooltip.bucket;
      const lines = [...bucket.parts]
        .sort((left, right) => right.value - left.value)
        .map(
          (part) =>
            `<div class="tooltip-row"><span>${this._escape(part.name)}</span><strong>${this._escape(
              `${this._format(part.value, 1)}${this._config.unit ? ` ${this._config.unit}` : ""}`
            )}</strong></div>`
        )
        .join("");
      const left = Math.max(12, Math.min(this._tooltip.x || 12, 420));
      const top = Math.max(12, (this._tooltip.y || 12) - 8);
      return `
        <div class="tooltip ${this._tooltip.pinned ? "pinned" : ""}" style="left:${left}px; top:${top}px;">
          <div class="tooltip-title">${this._escape(bucket.fullLabel || bucket.label)}</div>
          <div class="tooltip-total">Gesamt: ${this._escape(
            `${this._format(bucket.total, 1)}${this._config.unit ? ` ${this._config.unit}` : ""}`
          )}</div>
          <div class="tooltip-lines">${lines}</div>
        </div>
      `;
    }

    _setTooltip(event, bucket, pinned = false) {
      const wrap = this.shadowRoot?.querySelector(".wrap");
      const wrapRect = wrap?.getBoundingClientRect();
      const x = wrapRect ? event.clientX - wrapRect.left + 10 : 12;
      const y = wrapRect ? event.clientY - wrapRect.top + 10 : 12;
      this._tooltip = { bucket, x, y, pinned };
      this._render();
    }

    _bindChartInteractions(chartData) {
      this.shadowRoot?.querySelectorAll("[data-bucket-index]").forEach((node) => {
        const index = Number(node.getAttribute("data-bucket-index"));
        const bucket = chartData.buckets[index];
        if (!bucket) return;
        node.addEventListener("mouseenter", (event) => this._setTooltip(event, bucket, false));
        node.addEventListener("mousemove", (event) => {
          if (this._tooltip?.pinned) return;
          this._setTooltip(event, bucket, false);
        });
        node.addEventListener("mouseleave", () => {
          if (this._tooltip?.pinned) return;
          this._tooltip = null;
          this._render();
        });
        node.addEventListener("click", (event) => {
          event.stopPropagation();
          this._setTooltip(event, bucket, true);
        });
        node.addEventListener("focus", (event) => this._setTooltip(event, bucket, true));
        node.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            this._tooltip = null;
            this._render();
          }
        });
      });

      if (this._config.interactive_legend) {
        this.shadowRoot?.querySelectorAll("[data-series-key]").forEach((node) => {
          node.addEventListener("click", (event) => {
            event.stopPropagation();
            const key = node.getAttribute("data-series-key");
            this._toggleSeries(key);
          });
        });
      }
    }

    _renderChart(chartData, mode) {
      if (!chartData.buckets.length) {
        return `<div class="empty">Keine Daten im gewaehlten Zeitraum</div>`;
      }

      const width = 760;
      const height = 260;
      const chartTop = 16;
      const chartBottom = 34;
      const chartLeft = 42;
      const chartRight = 12;
      const plotWidth = width - chartLeft - chartRight;
      const plotHeight = height - chartTop - chartBottom;
      const barWidth = plotWidth / Math.max(chartData.buckets.length, 1);
      const stackWidth = Math.max(10, Math.min(34, barWidth - 6));
      const maxTotal = chartData.maxTotal > 0 ? chartData.maxTotal : 1;
      const ticks = this._tickValues(maxTotal);

      const gridLines = ticks
        .map((tick) => {
          const y = chartTop + plotHeight - (tick / maxTotal) * plotHeight;
          return `
            <line x1="${chartLeft}" y1="${y}" x2="${width - chartRight}" y2="${y}" class="grid-line"></line>
            <text x="${chartLeft - 8}" y="${y + 4}" class="axis-label axis-y">${this._escape(
              this._format(tick, tick >= 100 ? 0 : 1)
            )}</text>
          `;
        })
        .join("");

      const bars = chartData.buckets
        .map((bucket, index) => {
          let currentBottom = chartTop + plotHeight;
          const x = chartLeft + index * barWidth + (barWidth - stackWidth) / 2;
          const segments = bucket.parts
            .map((part, partIndex) => {
              const segmentHeight = (part.value / maxTotal) * plotHeight;
              const y = currentBottom - segmentHeight;
              currentBottom = y;
              const radius = partIndex === bucket.parts.length - 1 ? 4 : 0;
              return `<rect x="${x}" y="${y}" width="${stackWidth}" height="${Math.max(
                segmentHeight,
                0
              )}" rx="${radius}" ry="${radius}" fill="${part.color}"></rect>`;
            })
            .join("");
          const labelX = chartLeft + index * barWidth + barWidth / 2;
          return `
            <g class="bar-group">
              ${segments}
              <rect
                class="bar-hit"
                x="${x - 3}"
                y="${chartTop}"
                width="${stackWidth + 6}"
                height="${plotHeight}"
                tabindex="0"
                data-bucket-index="${index}"
              ></rect>
              <text x="${labelX}" y="${height - 12}" class="axis-label axis-x">${this._escape(
                this._displayLabel(chartData.buckets.length, bucket, index)
              )}</text>
            </g>
          `;
        })
        .join("");

      const legend = chartData.series
        .map((series) => {
          const disabled = this._disabledSeries.has(series.id);
          if (!this._config.interactive_legend) {
            return `
              <span class="legend-chip ${disabled ? "disabled" : ""}">
                <span class="legend-dot" style="background:${series.color}"></span>
                <span class="legend-label">${this._escape(series.name)}</span>
              </span>
            `;
          }
          return `
            <button
              type="button"
              class="legend-chip ${disabled ? "disabled" : ""}"
              data-series-key="${this._escape(series.id)}"
              aria-pressed="${disabled ? "false" : "true"}"
              title="${this._escape(`${series.name} ${disabled ? "einblenden" : "ausblenden"}`)}"
            >
              <span class="legend-dot" style="background:${series.color}"></span>
              <span class="legend-label">${this._escape(series.name)}</span>
            </button>
          `;
        })
        .join("");

      const allSeriesDisabled = chartData.series.length > 0 && chartData.activeSeries.length === 0;
      const chartBody = allSeriesDisabled
        ? `<div class="empty">Alle Reihen ausgeblendet</div>`
        : `
          <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${this._escape(
            this._config.title
          )}">
            ${gridLines}
            ${bars}
          </svg>
        `;

      return `
        <div class="chart-shell ${this._tooltip ? "has-tooltip" : ""}">
          <div class="chart-caption">${this._escape(mode === "month" ? "Monatsbuckets" : mode === "week" ? "Wochenbuckets" : "Tagesbuckets")}</div>
          ${chartBody}
          <div class="legend">${legend}</div>
          ${this._renderTooltip()}
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
              <div class="title">${this._escape(this._config.title)}</div>
              <div class="warning">Daily metric entity not found</div>
              <div class="muted"><code>${this._escape(this._config.daily_metric_entity || "")}</code></div>
            </div>
          </ha-card>
        `;
        return;
      }

      const rows = this._extractDailyRows(entity.attributes);
      const selection = this._selection || this._loadSelection();
      const visibleRows = utils.selectDaysForPeriod(rows, selection);
      const plan = this._bucketPlan(selection);
      const chartData = this._aggregateChart(visibleRows, plan.buckets);

      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="wrap">
            <div class="header">
              <div class="title">${this._escape(this._config.title)}</div>
              <div class="subtitle">${this._escape(plan.subtitle || selection.label || "Diese Woche")}</div>
            </div>
            ${this._renderChart(chartData, plan.mode)}
          </div>
        </ha-card>
      `;

      this._bindChartInteractions(chartData);
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
              radial-gradient(circle at top right, rgba(31, 142, 241, 0.12), transparent 38%),
              var(--ha-card-background, var(--card-background-color, #fff));
            border: 1px solid color-mix(in srgb, var(--divider-color) 55%, transparent);
          }

          .wrap {
            position: relative;
            padding: 16px;
            color: var(--primary-text-color);
          }

          .header {
            margin-bottom: 12px;
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

          .chart-shell {
            position: relative;
          }

          .chart-caption {
            margin-bottom: 6px;
            font-size: 0.78rem;
            color: var(--secondary-text-color);
          }

          .chart {
            width: 100%;
            height: 220px;
            overflow: visible;
          }

          .grid-line {
            stroke: color-mix(in srgb, var(--divider-color) 75%, transparent);
            stroke-width: 1;
          }

          .axis-label {
            fill: var(--secondary-text-color);
            font-size: 11px;
          }

          .axis-y {
            text-anchor: end;
          }

          .axis-x {
            text-anchor: middle;
          }

          .bar-hit {
            fill: transparent;
            cursor: pointer;
            outline: none;
          }

          .bar-hit:focus {
            fill: rgba(31, 142, 241, 0.08);
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

          .tooltip {
            position: absolute;
            max-width: min(320px, calc(100% - 16px));
            padding: 10px 12px;
            border-radius: 14px;
            border: 1px solid color-mix(in srgb, var(--divider-color) 70%, transparent);
            background: var(--ha-card-background, var(--card-background-color, #fff));
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
            z-index: 12;
            pointer-events: none;
          }

          .tooltip.pinned {
            pointer-events: auto;
          }

          .tooltip-title {
            font-size: 0.82rem;
            font-weight: 700;
          }

          .tooltip-total {
            margin-top: 4px;
            font-size: 0.8rem;
            color: var(--secondary-text-color);
          }

          .tooltip-lines {
            margin-top: 8px;
            display: grid;
            gap: 4px;
          }

          .tooltip-row {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            font-size: 0.78rem;
          }

          .warning,
          .empty {
            padding: 12px 14px;
            border-radius: 14px;
            background: color-mix(in srgb, var(--secondary-text-color) 10%, transparent);
            color: var(--secondary-text-color);
          }

          @media (max-width: 720px) {
            .chart {
              height: 180px;
            }

            .legend {
              gap: 6px;
            }

            .legend-chip {
              font-size: 0.74rem;
              padding: 5px 8px;
            }
          }
        </style>
      `;
    }
  }

  if (!customElements.get("hagym-stacked-history-card")) {
    customElements.define("hagym-stacked-history-card", HAGymStackedHistoryCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "hagym-stacked-history-card")) {
    window.customCards.push({
      type: "hagym-stacked-history-card",
      name: "HAGym Stacked History Card",
      description: "Energy-style stacked bar history for HAGym metrics",
      preview: true,
    });
  }
})();
