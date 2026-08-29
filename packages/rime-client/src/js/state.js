// Resolve the STA endpoint to connect to on load, in precedence order:
//   1. ?sta= / ?version= query params  — shareable deep links
//   2. localStorage                    — the server the user last chose here
//   3. window.RIME_CONFIG              — deployment default (see runtime-config.js)
//   4. none                            — start blank and ask for a server
//
// Deliberately no fallback to window.location.origin: rime-client is a
// standalone SensorThings client and may be deployed with no STA server of its
// own. See STA_ENDPOINT in packages/rime-client/docker-entrypoint.d/.
const STA_ENDPOINT_STORAGE_KEY = 'rime.staEndpoint';
const STA_VERSION_STORAGE_KEY = 'rime.staVersion';
const KNOWN_STA_VERSIONS = ['v1.0', 'v1.1', 'v2.0'];

function readStoredEndpoint(key) {
    try {
        return localStorage.getItem(key) || '';
    } catch (_) {
        return '';  // private browsing / storage disabled
    }
}

function storeEndpoint(base, version) {
    try {
        if (base) localStorage.setItem(STA_ENDPOINT_STORAGE_KEY, base);
        else localStorage.removeItem(STA_ENDPOINT_STORAGE_KEY);
        localStorage.setItem(STA_VERSION_STORAGE_KEY, version);
    } catch (_) { /* non-fatal — the choice just won't survive a reload */ }
}

function resolveInitialEndpoint() {
    const runtime = window.RIME_CONFIG || {};
    const params = new URLSearchParams(window.location.search);

    const base = (
        params.get('sta') ||
        readStoredEndpoint(STA_ENDPOINT_STORAGE_KEY) ||
        runtime.staEndpoint ||
        ''
    ).trim().replace(/\/+$/, '');

    const version = (
        params.get('version') ||
        readStoredEndpoint(STA_VERSION_STORAGE_KEY) ||
        runtime.staVersion ||
        ''
    ).trim().toLowerCase();

    return {
        base,
        version: KNOWN_STA_VERSIONS.includes(version) ? version : 'v1.1',
    };
}

const initialEndpoint = resolveInitialEndpoint();

// Global application state
const state = {
    things: {},
    thingsByName: {},
    markers: {},
    currentDatastream: null,
    currentChart: null,
    currentLimit: 1000,
    // Time window the chart requests, applied server-side as an OData $filter on
    // phenomenonTime. preset is one of 'all' | '24h' | '7d' | '30d' | 'custom';
    // from/to are Date objects and only used when preset is 'custom'.
    chartRange: { preset: 'all', from: null, to: null },
    chartPointCache: null,       // { datastreamId, rangeKey, points, observationTotal, ... }
    map: null,
    markerCluster: null,
    maxClusterSize: 1,
    currentThingDatastreams: [],
    currentDatastreamIndex: -1,
    selectedThingId: null,
    searchQuery: '',
    activeStatusFilter: 'all',
    rosterView: 'things',  // 'things' | 'locations' — which list the roster shows
    showVirtualThings: false, // roster toggle: include Things without a Location
    // STA endpoint: base URL (no version) + version string. Empty frostBase
    // means "not configured yet" — the app starts blank and prompts for a
    // server rather than fetching. See resolveInitialEndpoint() above.
    // frostRoot is always kept in sync as frostBase + '/' + frostVersion.
    frostBase: initialEndpoint.base,
    frostVersion: initialEndpoint.version,
    get frostRoot() { return `${this.frostBase}/${this.frostVersion}`; },
    get isConfigured() { return !!this.frostBase; },
    frostReadAuth: null,   // Base64-encoded "user:pass" for read access, or null for anonymous
    fetchGeneration: 0,    // Incremented on every new fetch; stale generations discard their results
};

