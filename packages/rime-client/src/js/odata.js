// Version-aware OData vocabulary for the query builder.
//
// STA 1.1 and STA 2.0 do not expose the same query surface: 2.0 aligns with
// OData 4.01 and supports considerably more than 1.1. Measured against FROST
// 2.6 on a v1.1 endpoint:
//
//     substringof('Room', name)  -> 200
//     contains(name, 'Room')     -> 400
//
// so the operator list must be selected per version rather than hard-coded,
// the same way ``frost-fields.js`` selects annotation field names. Anything
// version-specific belongs here, not in the UI.

const STA_ENTITY_TYPES = [
    'Things',
    'Datastreams',
    'Observations',
    'Sensors',
    'ObservedProperties',
    'Locations',
    'HistoricalLocations',
    'FeaturesOfInterest',
];

// Commonly used properties per entity type, offered as suggestions only — the
// field input stays free-text so it never blocks an unlisted or custom property.
const STA_COMMON_FIELDS = {
    Things: ['name', 'description', 'properties'],
    Datastreams: ['name', 'description', 'observationType', 'phenomenonTime', 'resultTime'],
    Observations: ['result', 'phenomenonTime', 'resultTime', 'resultQuality'],
    Sensors: ['name', 'description', 'encodingType', 'metadata'],
    ObservedProperties: ['name', 'definition', 'description'],
    Locations: ['name', 'description', 'encodingType', 'location'],
    HistoricalLocations: ['time'],
    FeaturesOfInterest: ['name', 'description', 'encodingType', 'feature'],
};

// Navigation properties usable with $expand.
const STA_NAV_PROPERTIES = {
    Things: ['Datastreams', 'Locations', 'HistoricalLocations'],
    Datastreams: ['Thing', 'Sensor', 'ObservedProperty', 'Observations'],
    Observations: ['Datastream', 'FeatureOfInterest'],
    Sensors: ['Datastreams'],
    ObservedProperties: ['Datastreams'],
    Locations: ['Things', 'HistoricalLocations'],
    HistoricalLocations: ['Thing', 'Locations'],
    FeaturesOfInterest: ['Observations'],
};

const ODATA_COMPARISON_OPERATORS = [
    { op: 'eq', label: 'equals' },
    { op: 'ne', label: 'not equals' },
    { op: 'gt', label: 'greater than' },
    { op: 'ge', label: 'greater or equal' },
    { op: 'lt', label: 'less than' },
    { op: 'le', label: 'less or equal' },
];

// String functions, keyed by the STA major version that supports them.
// v2.0 follows OData 4.01: `substringof` is gone, replaced by `contains`.
const ODATA_STRING_FUNCTIONS_V1 = [
    { fn: 'substringof', label: 'contains', template: "substringof('{value}', {field})" },
    { fn: 'startswith', label: 'starts with', template: "startswith({field}, '{value}')" },
    { fn: 'endswith', label: 'ends with', template: "endswith({field}, '{value}')" },
];

const ODATA_STRING_FUNCTIONS_V2 = [
    { fn: 'contains', label: 'contains', template: "contains({field}, '{value}')" },
    { fn: 'startswith', label: 'starts with', template: "startswith({field}, '{value}')" },
    { fn: 'endswith', label: 'ends with', template: "endswith({field}, '{value}')" },
];

/** String functions available for the given version (or endpoint URL). */
function odataStringFunctions(versionOrUrl) {
    return isFrostV2(versionOrUrl)
        ? ODATA_STRING_FUNCTIONS_V2
        : ODATA_STRING_FUNCTIONS_V1;
}

/** Every filter predicate the builder can emit, for the given version. */
function odataFilterOperators(versionOrUrl) {
    return [
        ...ODATA_COMPARISON_OPERATORS.map(o => ({
            kind: 'comparison',
            value: o.op,
            label: `${o.op} — ${o.label}`,
        })),
        ...odataStringFunctions(versionOrUrl).map(f => ({
            kind: 'function',
            value: f.fn,
            label: `${f.fn} — ${f.label}`,
            template: f.template,
        })),
    ];
}

/** Quote a filter value unless it is a number, boolean, null, or already quoted. */
function odataQuoteValue(raw) {
    const value = String(raw).trim();
    if (value === '') return "''";
    if (/^-?\d+(\.\d+)?$/.test(value)) return value;
    if (/^(true|false|null)$/i.test(value)) return value.toLowerCase();
    if (/^'.*'$/.test(value)) return value;
    // OData escapes a single quote by doubling it.
    return `'${value.replace(/'/g, "''")}'`;
}

/**
 * Render one filter row to an OData predicate.
 * Returns '' when the row is incomplete, so callers can skip it.
 */
function odataFilterClause(row, versionOrUrl) {
    const field = (row.field || '').trim();
    if (!field || !row.operator) return '';

    const fn = odataStringFunctions(versionOrUrl).find(f => f.fn === row.operator);
    if (fn) {
        const value = String(row.value ?? '').replace(/'/g, "''");
        return fn.template
            .replace('{field}', field)
            .replace('{value}', value);
    }

    if (row.value === '' || row.value == null) return '';
    return `${field} ${row.operator} ${odataQuoteValue(row.value)}`;
}

/** Join filter rows with a logical operator, skipping incomplete ones. */
function odataCombineFilters(rows, join, versionOrUrl) {
    const clauses = rows
        .map(row => odataFilterClause(row, versionOrUrl))
        .filter(Boolean);
    if (clauses.length === 0) return '';
    if (clauses.length === 1) return clauses[0];
    return clauses.map(c => `(${c})`).join(` ${join} `);
}

/**
 * Build a full STA request URL.
 *
 * `params` values that are empty are omitted entirely — an empty `$filter=`
 * is a 400 on FROST, not an ignored parameter.
 */
function buildODataUrl({ root, entity, params }) {
    const parts = [];
    for (const [key, value] of Object.entries(params || {})) {
        const v = typeof value === 'string' ? value.trim() : value;
        if (v === '' || v == null || v === false) continue;
        parts.push(`${key}=${odataEncodeParam(v === true ? 'true' : String(v))}`);
    }
    return `${root}/${entity}${parts.length ? `?${parts.join('&')}` : ''}`;
}

/**
 * Percent-encode a query value while keeping OData punctuation legible.
 *
 * ``URLSearchParams`` is not used here: it encodes ``(``, ``)``, ``,`` and ``$``
 * and renders spaces as ``+``. That is valid but unreadable, and this URL is
 * meant to be read on screen and pasted into curl. ``encodeURIComponent``
 * already leaves ``'``, ``(`` and ``)`` alone; commas and slashes are safe in a
 * query string, so restore those too. Spaces stay ``%20`` rather than ``+``,
 * which is only space in form-encoded bodies.
 */
function odataEncodeParam(value) {
    return encodeURIComponent(value)
        .replace(/%2C/gi, ',')
        .replace(/%2F/gi, '/');
}
