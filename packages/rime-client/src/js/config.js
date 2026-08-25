// Configuration and constants

// ── Known STA servers ──────────────────────────────────────────────────────
// Single source for the quick-pick lists on both the map (endpoint switcher)
// and the query builder. Both pages render from this, so adding a server here
// adds it everywhere.
const STA_KNOWN_SERVERS = [
    { label: 'localhost',           base: 'http://localhost:8080/FROST-Server' },
    { label: 'sta.wbd-rd.nl',       base: 'https://sta.wbd-rd.nl/FROST-Server' },
    { label: 'multicare.tudelft.nl', base: 'https://multicare.bk.tudelft.nl/FROST-Server' },
    { label: 'iosb.fraunhofer.de',  base: 'https://airquality-frost.k8s.ilt-dmz.iosb.fraunhofer.de' },
];

// ── Pagination ─────────────────────────────────────────────────────────────
// FROST defaults to $top=100, forcing one round-trip per 100 entities. On a
// dense network (e.g. iosb ~5600 nodes) that's ~57 sequential requests. We
// request much larger pages instead; servers that enforce a lower maxTop simply
// clamp the page and we follow the version-aware next-link for the remainder.
//
// Measured on iosb (5613 Things):
//   Phase 1 (Locations, light):  $top=100 ≈ 30s over 57 reqs → $top=10000 ≈ 9.4s in 1 req.
//   Phase 2 (health, light):     Datastreams?$select=phenomenonTime,<id> — paginate
//     via next-link so badges stream in without heavy Observations expands.
//     Select whole phenomenonTime (not /end): STA 1.x returns an ISO string /
//     interval; STA 2.0 returns a TM_Period {start,end} object.
const THINGS_PAGE_SIZE = 10000; // Phase 1 — light payload, fetch in as few requests as possible
const HEALTH_PAGE_SIZE = 10000; // Phase 2 — last-observation scan via Datastreams.phenomenonTime
const DOWNLOAD_PAGE_SIZE = 10000;

// ── Health tiers ───────────────────────────────────────────────────────────
// Graded "time since last observation" buckets, ordered freshest → oldest.
// Single source of truth for colours + labels used by markers, roster, legend
// and the inspector. maxMin is the exclusive upper bound (in minutes) of each
// tier; the final tier uses Infinity.
const HEALTH_TIERS = [
    { key: 'fresh',   maxMin: 60,       label: '< 1h',  color: '#34d399' },
    { key: 'recent',  maxMin: 120,      label: '< 2h',  color: '#a3e635' },
    { key: 'stale',   maxMin: 1440,     label: '< 1d',  color: '#facc15' },
    { key: 'old',     maxMin: 43200,    label: '< 1mo', color: '#fb923c' },
    { key: 'ancient', maxMin: 525600,   label: '< 1y',  color: '#f87171' },
    { key: 'dormant', maxMin: Infinity, label: '> 1y',  color: '#e11d48' },
];

// Sensor reported observations but parsing failed, or no observations at all.
const NODATA_TIER = { key: 'nodata', label: 'No data', color: '#64748b' };

// Quick lookup by tier key (includes nodata).
const HEALTH_TIER_MAP = [...HEALTH_TIERS, NODATA_TIER].reduce((m, t) => {
    m[t.key] = t;
    return m;
}, {});

// Resolve a "minutes since last observation" value to a tier object.
function getHealthTier(minutes) {
    if (minutes === null || minutes === undefined || Number.isNaN(minutes)) {
        return NODATA_TIER;
    }
    for (const tier of HEALTH_TIERS) {
        if (minutes < tier.maxMin) return tier;
    }
    return HEALTH_TIERS[HEALTH_TIERS.length - 1];
}

// FROST phenomenonTime shapes:
//   STA 1.x — instant string ("2026-…Z") or interval ("2026-…Z/2026-…Z")
//   STA 2.0 — TM_Period / TM_Object: { start, end? }
// For "time since last observation" we use the END of an interval (or start
// when end is absent). Returns a valid Date or null.
function parsePhenomenonTime(value) {
    if (!value) return null;

    if (typeof value === 'object') {
        const edge = value.end ?? value.start;
        if (!edge) return null;
        const date = new Date(edge);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    if (typeof value !== 'string') return null;
    const part = value.includes('/') ? value.split('/').pop() : value;
    const date = new Date(part);
    return Number.isNaN(date.getTime()) ? null : date;
}

// ── Colour helpers ─────────────────────────────────────────────────────────
function hexToRgba(hex, alpha) {
    const h = hex.replace('#', '');
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Mix a hex colour toward white by `amount` (0..1) — used for readable tag text
// on the dark theme.
function lightenHex(hex, amount) {
    const h = hex.replace('#', '');
    let r = parseInt(h.substring(0, 2), 16);
    let g = parseInt(h.substring(2, 4), 16);
    let b = parseInt(h.substring(4, 6), 16);
    r = Math.round(r + (255 - r) * amount);
    g = Math.round(g + (255 - g) * amount);
    b = Math.round(b + (255 - b) * amount);
    return `rgb(${r}, ${g}, ${b})`;
}

// Mapping of observed property names to display names
const OBSERVED_PROPERTY_DISPLAY_NAMES = {
    'phenomenon_time': 'Phenomenon Time',
    'battery_level': 'Battery Level',
    'humidity': 'Humidity',
    'co2': 'CO₂',
    'temperature_indoor': 'Temperature Indoor',
    'light_level': 'Light Level',
    'passive_infrared': 'Passive Infrared',
    'particulate_matter_10': 'PM₁₀',
    'particulate_matter_2_5': 'PM₂.₅',
    'gauge_pressure': 'Gauge Pressure',
    'absolute_pressure': 'Absolute Pressure',
    'noise': 'Noise',
    'total_volatile_organic_compounds': 'TVOC'
};

// Format datastream name for display
function formatDatastreamName(name) {
    if (!name) return 'Unknown';
    
    // Check if we have a direct mapping
    const lowerName = name.toLowerCase().trim();
    if (OBSERVED_PROPERTY_DISPLAY_NAMES[lowerName]) {
        return OBSERVED_PROPERTY_DISPLAY_NAMES[lowerName];
    }
    
    // Fallback: convert snake_case to Title Case
    return name
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

