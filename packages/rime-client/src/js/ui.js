// Shared UI helpers — status bar, loading overlay, mobile sheet, endpoint switcher.

const isMobileView = () => window.matchMedia('(max-width: 640px)').matches;

/**
 * Publish the command bar's measured height as the `--bar-h` custom property.
 *
 * The bar sizes itself from its content and wraps when it runs out of room, so
 * its height is not knowable up front — it depends on viewport width, zoom,
 * font size and how many controls are present. Eleven rules in styles.css
 * offset the roster, chart panel and map stage from `--bar-h`, so publishing
 * the real value keeps all of them correct without a single hard-coded number.
 *
 * `.command-bar` must never derive its own height from `--bar-h`; it uses
 * `--bar-min-h` as a floor instead. Reading the value it writes would make this
 * observer feed its own input.
 */
function observeCommandBarHeight() {
    const bar = document.querySelector('.command-bar');
    if (!bar) return;

    const publish = () => {
        // ceil, not round: this value reserves space below the bar, and rounding
        // down by a fraction of a pixel lets the bar overlap what sits under it.
        const px = Math.ceil(bar.getBoundingClientRect().height);
        if (px > 0) {
            document.documentElement.style.setProperty('--bar-h', `${px}px`);
        }
    };

    // Publish straight away and on resize. Deliberately not relying on
    // ResizeObserver alone: it does not fire in every embedded/automated
    // browser context, and if it silently never runs, every layout offset keeps
    // the stale fallback while the bar is a different height.
    publish();
    requestAnimationFrame(publish);   // again after first layout/fonts settle
    window.addEventListener('resize', publish);

    // ResizeObserver additionally catches height changes that no resize event
    // accompanies — legend chips being built after the Things fetch, the
    // "Exit virtual" button appearing, a control shedding its label.
    if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(publish).observe(bar);
    }
}

function mobileCollapseRoster() {
    if (!isMobileView()) return;
    document.getElementById('roster')?.classList.remove('sheet-expanded');
}

function initMobileBottomSheet() {
    const roster = document.getElementById('roster');
    const handle = document.getElementById('sheetHandle');
    const head = roster?.querySelector('.roster-head');
    const mapEl = document.getElementById('map');
    const searchBox = document.getElementById('searchBox');
    const searchToggle = document.getElementById('mobileSearchToggle');
    const chartTraceToggle = document.getElementById('chartTraceToggle');
    const chartPanel = document.getElementById('chartPanel');

    function sheetToggle(e) {
        if (!isMobileView()) return;
        if (e && e.target.closest('button, a, input, select')) return;
        roster.classList.toggle('sheet-expanded');
        setTimeout(() => state.map?.invalidateSize(), 420);
    }

    if (handle) handle.addEventListener('click', sheetToggle);
    if (head) head.addEventListener('click', sheetToggle);

    if (mapEl) {
        mapEl.addEventListener('click', () => {
            if (!isMobileView()) return;
            roster?.classList.remove('sheet-expanded');
            searchBox?.classList.remove('mobile-open');
            searchToggle?.classList.remove('active');
        });
    }

    if (searchToggle && searchBox) {
        searchToggle.addEventListener('click', () => {
            if (!isMobileView()) return;
            const opening = !searchBox.classList.contains('mobile-open');
            searchBox.classList.toggle('mobile-open', opening);
            searchToggle.classList.toggle('active', opening);
            if (opening) searchBox.querySelector('input')?.focus();
        });

        searchBox.querySelector('input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' || e.key === 'Enter') {
                searchBox.classList.remove('mobile-open');
                searchToggle.classList.remove('active');
            }
        });
    }

    if (chartTraceToggle && chartPanel) {
        chartTraceToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!isMobileView()) return;
            const expanding = !chartPanel.classList.contains('mobile-trace-expanded');
            chartPanel.classList.toggle('mobile-trace-expanded', expanding);
            chartTraceToggle.classList.toggle('trace-active', expanding);
            const label = chartTraceToggle.querySelector('.trace-label');
            if (label) label.textContent = expanding ? 'Stats' : 'Trace';
        });
    }
}

function updateStatus(message, type = '') {
    const statusEl = document.getElementById('statusMessage');
    statusEl.className = `status-message ${type}`;
    statusEl.innerHTML = '<span class="status-dot"></span>';
    statusEl.appendChild(document.createTextNode(message));
}

let _loadingHideTimer = null;

function showLoadingOverlay(title, subtitle, type = 'loading') {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;
    if (_loadingHideTimer) {
        clearTimeout(_loadingHideTimer);
        _loadingHideTimer = null;
    }

    if (type === 'loading') overlay.classList.remove('status-error');

    if (title) document.getElementById('loadingTitle').textContent = title;
    if (subtitle !== undefined) document.getElementById('loadingSubtitle').textContent = subtitle;

    overlay.classList.remove('is-leaving', 'status-error');
    if (type === 'error') overlay.classList.add('status-error');

    overlay.hidden = false;
}

function showErrorOverlay(title, subtitle) {
    showLoadingOverlay(title, subtitle, 'error');
}

function updateLoadingOverlay(subtitle) {
    const sub = document.getElementById('loadingSubtitle');
    if (sub && subtitle !== undefined) sub.textContent = subtitle;
}

function hideLoadingOverlay(force = false) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay || overlay.hidden) return;

    if (!force && overlay.classList.contains('status-error')) return;

    overlay.classList.add('is-leaving');
    _loadingHideTimer = setTimeout(() => {
        overlay.hidden = true;
        overlay.classList.remove('is-leaving', 'status-error');
        _loadingHideTimer = null;
    }, 460);
}

// Assigned by initializeEndpointSwitcher() so callers outside it (app.js on an
// unconfigured or unreachable boot) can open the popover.
let _openEndpointPopover = null;

const ENDPOINT_HINT_DEFAULT = 'Enter connects. Version is appended automatically.';

// Open the endpoint switcher, optionally explaining why. `message` is shown in
// the popover footer until the next time it opens cleanly.
function promptForEndpoint(message) {
    const hint = document.getElementById('endpointHint');
    if (hint) {
        hint.textContent = message || ENDPOINT_HINT_DEFAULT;
        hint.classList.toggle('endpoint-hint-warn', !!message);
    }
    if (_openEndpointPopover) _openEndpointPopover();
}

// Drop a previous failure message once a server responds.
function clearEndpointHint() {
    const hint = document.getElementById('endpointHint');
    if (!hint) return;
    hint.textContent = ENDPOINT_HINT_DEFAULT;
    hint.classList.remove('endpoint-hint-warn');
}

function initializeEndpointSwitcher() {
    const display = document.getElementById('endpointDisplay');
    const popover = document.getElementById('endpointPopover');
    const input = document.getElementById('endpointInput');
    const applyBtn = document.getElementById('endpointApply');
    const label = document.getElementById('endpointLabel');
    const versionGroup = document.getElementById('endpointVersionGroup');
    const authToggle = document.getElementById('endpointAuthToggle');
    const authFields = document.getElementById('endpointAuthFields');
    const authChevron = document.getElementById('endpointAuthChevron');
    const authToggleLabel = document.getElementById('endpointAuthToggleLabel');
    const usernameInput = document.getElementById('endpointUsername');
    const passwordInput = document.getElementById('endpointPassword');

    function syncLabel() {
        if (!state.isConfigured) {
            label.textContent = 'Connect to a server';
            display.classList.add('unconfigured');
            display.classList.remove('has-auth');
            return;
        }
        const host = state.frostBase.replace(/^https?:\/\//, '');
        label.textContent = `${host} @ ${state.frostVersion}`;
        display.classList.remove('unconfigured');
        display.classList.toggle('has-auth', !!state.frostReadAuth);
    }
    syncLabel();

    function syncVersionButtons() {
        versionGroup.querySelectorAll('.endpoint-version-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.version === state.frostVersion);
        });
    }
    syncVersionButtons();

    versionGroup.addEventListener('click', (e) => {
        const btn = e.target.closest('.endpoint-version-btn');
        if (!btn) return;
        state.frostVersion = btn.dataset.version;
        syncVersionButtons();
    });

    // Quick-picks come from STA_KNOWN_SERVERS (config.js) so the map and the
    // query builder always offer the same list.
    const quickpicks = document.getElementById('endpointQuickpicks');
    if (quickpicks && !quickpicks.children.length) {
        STA_KNOWN_SERVERS.forEach(server => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'endpoint-quickpick';
            btn.dataset.base = server.base;
            btn.textContent = server.label;
            btn.title = server.base;
            quickpicks.appendChild(btn);
        });
    }

    popover.querySelectorAll('.endpoint-quickpick').forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.dataset.base;
            input.focus();
        });
    });

    authToggle.addEventListener('click', () => {
        const isOpen = !authFields.hidden;
        authFields.hidden = isOpen;
        authChevron.style.transform = isOpen ? '' : 'rotate(180deg)';
        authToggleLabel.textContent = isOpen ? 'Add credentials' : 'Hide credentials';
        if (!isOpen) usernameInput.focus();
    });

    function openPopover() {
        input.value = state.frostBase;
        syncVersionButtons();

        if (state.frostReadAuth) {
            try {
                const decoded = atob(state.frostReadAuth);
                const colon = decoded.indexOf(':');
                usernameInput.value = decoded.substring(0, colon);
                passwordInput.value = decoded.substring(colon + 1);
            } catch (_) { /* ignore malformed auth */ }
            authFields.hidden = false;
            authChevron.style.transform = 'rotate(180deg)';
            authToggleLabel.textContent = 'Hide credentials';
        }
        popover.hidden = false;
        display.classList.add('active');
        input.focus();
        input.select();
    }

    function closePopover() {
        popover.hidden = true;
        display.classList.remove('active');
    }

    display.addEventListener('click', (e) => {
        e.stopPropagation();
        popover.hidden ? openPopover() : closePopover();
    });

    document.addEventListener('click', (e) => {
        if (!document.getElementById('endpointSwitcher').contains(e.target)) {
            closePopover();
        }
    });

    function applyEndpoint() {
        let raw = input.value.trim().replace(/\/+$/, '');

        const versionMatch = raw.match(/\/(v\d+(?:\.\d+)?)$/i);
        if (versionMatch) {
            let v = versionMatch[1].toLowerCase();
            if (v === 'v1') v = 'v1.0';
            else if (v === 'v2') v = 'v2.0';

            const known = ['v1.0', 'v1.1', 'v2.0'];
            if (known.includes(v)) {
                state.frostVersion = v;
                syncVersionButtons();
            }
            raw = raw.replace(/\/(v\d+(?:\.\d+)?)$/i, '');
        }

        if (!raw) {
            closePopover();
            return;
        }

        const user = usernameInput.value.trim();
        const pass = passwordInput.value;
        state.frostBase = raw;
        state.frostReadAuth = (user || pass) ? btoa(`${user}:${pass}`) : null;

        // Remember the server across reloads. Credentials are deliberately not
        // persisted — they stay in memory for this session only.
        storeEndpoint(state.frostBase, state.frostVersion);

        syncLabel();
        closePopover();
        resetAndReload();
    }

    // Let the rest of the app open the switcher (e.g. on an unconfigured boot).
    _openEndpointPopover = openPopover;

    applyBtn.addEventListener('click', applyEndpoint);
    [input, usernameInput, passwordInput].forEach(el => {
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyEndpoint();
            if (e.key === 'Escape') closePopover();
        });
    });
}

function resetAndReload() {
    // The user picked this endpoint, so report failures against it directly
    // rather than falling back to the connect prompt (see app.js).
    isInitialLoad = false;

    hideThingMetadata();
    document.getElementById('chartPanel')?.classList.remove('expanded');

    if (state.markerCluster) state.markerCluster.clearLayers();

    state.things = {};
    state.thingsByName = {};
    state.markers = {};
    state.currentThingDatastreams = [];
    state.selectedThingId = null;
    state.maxClusterSize = 1;
    state.searchQuery = '';
    state.activeStatusFilter = 'all';
    state.showVirtualThings = false;

    document.getElementById('thingsList').innerHTML = '';
    const locationsListEl = document.getElementById('locationsList');
    if (locationsListEl) locationsListEl.innerHTML = '';
    const virtualCheckbox = document.getElementById('virtualThingsCheckbox');
    if (virtualCheckbox) virtualCheckbox.checked = false;
    document.querySelector('.app-shell')?.classList.remove('virtual-things-mode', 'roster-collapsed');
    clearVirtualLayer();
    syncVirtualModeChrome();
    setRosterView('things');
    resetChartPanel();

    document.getElementById('searchInput').value = '';
    document.querySelectorAll('.legend-chip').forEach(c => c.classList.remove('active'));
    document.querySelector('.legend-chip[data-filter="all"]')?.classList.add('active');
    ['countTotal', ...[...HEALTH_TIERS, NODATA_TIER].map(t => `count-${t.key}`)].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '0';
    });
    setHealthCheckButtonState('disabled');

    fetchThings();
}
