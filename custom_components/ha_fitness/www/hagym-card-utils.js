(() => {
  if (window.HAGymCardUtils) {
    return;
  }

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

  const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

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

  const buildCompactLabel = (periodKey, start, anchor, end, locale) => {
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

  const buildGenericLabel = (periodKey) => PERIOD_LABELS[periodKey] || "Diese Woche";

  const buildSelection = (periodKey, anchorDate, collectionKey, locale, labelMode = "generic") => {
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
      label = labelMode === "compact" ? buildCompactLabel(key, start, anchor, end, locale) : null;
    } else if (key === "this_month") {
      start = startOfMonth(anchor);
      end = addMonths(start, 1);
      label = labelMode === "compact" ? buildCompactLabel(key, start, anchor, end, locale) : null;
    } else if (key === "this_quarter") {
      start = startOfQuarter(anchor);
      end = addMonths(start, 3);
      label = labelMode === "compact" ? buildCompactLabel(key, start, anchor, end, locale) : null;
    } else if (key === "this_year") {
      start = startOfYear(anchor);
      end = new Date(start.getFullYear() + 1, 0, 1, 0, 0, 0, 0);
      label = labelMode === "compact" ? buildCompactLabel(key, start, anchor, end, locale) : null;
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
        label:
          label ||
          (labelMode === "compact"
            ? buildCompactLabel(key, start, anchor, end, locale)
            : buildGenericLabel(key)),
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

  const loadSelection = (collectionKey, defaultPeriod, locale, labelMode = "generic") => {
    const fallback = buildSelection(
      defaultPeriod || "this_week",
      new Date(),
      collectionKey,
      locale,
      labelMode
    );
    try {
      const raw = localStorage.getItem(storageKey(collectionKey));
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
            : toDateOnly(selectionEndInclusive(parsed)));
        if (startDate && endDate) {
          return buildCustomRangeSelection(startDate, endDate, collectionKey, locale);
        }
        return fallback;
      }
      return buildSelection(
        key,
        parsed.anchor_date || new Date(),
        collectionKey,
        locale,
        labelMode
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

  const shiftSelection = (selection, step, collectionKey, locale, labelMode = "generic") => {
    const current =
      selection || buildSelection("this_week", new Date(), collectionKey, locale, labelMode);
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

      return buildSelection(key, nextAnchor, collectionKey, locale, labelMode);
  };

  const legendStorageKey = (prefix, collectionKey, ...parts) =>
    `${prefix}:${collectionKey}:${parts.map((part) => String(part)).join(":")}`;

  const loadDisabledSet = (key) => {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return new Set();
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? new Set(parsed.map((value) => String(value))) : new Set();
    } catch (_err) {
      return new Set();
    }
  };

  const saveDisabledSet = (key, disabledSet, enabled) => {
    if (!enabled) return;
    try {
      localStorage.setItem(key, JSON.stringify([...disabledSet].sort()));
    } catch (_err) {
      // ignore storage failures
    }
  };

  const hasDailyMetricShape = (attributes, collectionKey) => {
    if (!attributes || typeof attributes !== "object") return false;
    if (Array.isArray(attributes.days) || Array.isArray(attributes.history)) return true;
    if (Array.isArray(attributes.daily_metrics) || Array.isArray(attributes.metric_history)) return true;
    if (attributes[collectionKey] && typeof attributes[collectionKey] === "object") {
      const collection = attributes[collectionKey];
      if (Array.isArray(collection.days) || Array.isArray(collection.history)) return true;
    }
    if (attributes.collections && typeof attributes.collections === "object") {
      const collections = attributes.collections;
      if (collections[collectionKey]) return true;
    }
    if (attributes.hagym && typeof attributes.hagym === "object") return true;
    return false;
  };

  const findDefaultDailyMetricEntity = (hass, collectionKey = "hagym") => {
    const states = hass?.states;
    if (!states || typeof states !== "object") return "";
    const normalizedCollectionKey = String(collectionKey || "hagym").toLowerCase();
    const candidates = [];

    for (const [entityId, stateObj] of Object.entries(states)) {
      if (!entityId.startsWith("sensor.")) continue;
      const normalizedEntityId = entityId.toLowerCase();
      const attributes = stateObj?.attributes || {};
      const hasKeyword =
        normalizedEntityId.includes("tagesstatistik") ||
        normalizedEntityId.includes("daily_metric") ||
        normalizedEntityId.includes("metric_statistics");
      const hasShape = hasDailyMetricShape(attributes, normalizedCollectionKey);
      if (!hasKeyword && !hasShape) continue;

      let score = 0;
      if (normalizedEntityId.includes(normalizedCollectionKey)) score += 40;
      if (normalizedEntityId.includes("personliche") || normalizedEntityId.includes("personal")) score += 30;
      if (
        normalizedEntityId.includes("tagesstatistik") ||
        normalizedEntityId.includes("daily_metric_statistics")
      ) {
        score += 20;
      }
      if (hasShape) score += 15;
      if (attributes.collection_key && String(attributes.collection_key).toLowerCase() === normalizedCollectionKey) {
        score += 20;
      }
      if (attributes.collections && attributes.collections[normalizedCollectionKey]) {
        score += 10;
      }

      candidates.push({ entityId, score });
    }

    candidates.sort((left, right) => right.score - left.score || left.entityId.localeCompare(right.entityId));
    return candidates[0]?.entityId || "";
  };

  const defaultDailyMetricEntity = (
    hass,
    collectionKey = "hagym",
    fallback = "sensor.hagym_hagym_personliche_tagesstatistik"
  ) => findDefaultDailyMetricEntity(hass, collectionKey) || fallback || "";

  window.HAGymCardUtils = {
    DATE_ONLY_RE,
    PERIOD_KEYS,
    addDays,
    addMonths,
    buildCustomRangeSelection,
    buildSelection,
    customRangeLengthDays,
    escapeHtml,
    formatCustomRangeLabel,
    legendStorageKey,
    findDefaultDailyMetricEntity,
    loadDisabledSet,
    loadSelection,
    normalizePeriod,
    parseDate,
    parseDateOnly,
    saveDisabledSet,
    saveSelection,
    defaultDailyMetricEntity,
    selectionEndExclusive,
    selectionEndInclusive,
    selectionStartDate,
    selectDaysForPeriod,
    shiftSelection,
    startOfDay,
    startOfMonth,
    startOfQuarter,
    startOfWeek,
    startOfYear,
    storageKey,
    toDateOnly,
  };
})();
