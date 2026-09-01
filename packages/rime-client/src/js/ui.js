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
    observeMeasuredHeight('.command-bar', '--bar-h');
}

/**
 * Publish the chart dock header's measured height as `--chart-hdr-h`.
 *
 * Same reasoning as the command bar: the header wraps its controls onto a
 * second row when they no longer fit, so the collapsed panel's height is not a
 * constant. Clipping it to a fixed `--dock-h` cut the wrapped row off and let
 * the header's contents paint over each other.
 */
function observeChartHeaderHeight() {
    observeMeasuredHeight('.chart-panel-header', '--chart-hdr-h');
}

/**
 * Publish the mobile sheet's peek height — the strip of the roster left visible
 * when it is collapsed, which should be exactly the drag handle plus the
 * Things/Locations tab row.
 *
 * It was a flat 60px while that content measures ~73px, so the tabs hung below
 * the peek and, with nothing clipping them, over the floating chart dock.
 *
 * Measured as the distance from the roster's top to the bottom of the tab row.
 * Both move together under the sheet's translateY, so the difference does not
 * depend on --sheet-peek and this cannot feed its own input.
 */
function observeSheetPeek() {
    const roster = document.getElementById('roster');
    const headRow = roster?.querySelector('.roster-head-row');
    if (!roster || !headRow) return;

    const publish = () => {
        const px = Math.ceil(
            headRow.getBoundingClientRect().bottom - roster.getBoundingClientRect().top,
        );
        if (px > 0) document.documentElement.style.setProperty('--sheet-peek', `${px}px`);
    };

    publish();
    requestAnimationFrame(publish);
    window.addEventListener('resize', publish);
    if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(publish).observe(headRow);
    }
}

/** Publish an element's measured height into a custom property on :root. */
function observeMeasuredHeight(selector, property) {
    const bar = document.querySelector(selector);
    if (!bar) return;

    const publish = () => {
        // ceil, not round: this value reserves space below the bar, and rounding
        // down by a fraction of a pixel lets the bar overlap what sits under it.
        const px = Math.ceil(bar.getBoundingClientRect().height);
        if (px > 0) {
            document.documentElement.style.setProperty(property, `${px}px`);
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

// The connection control (server, version, credentials) lives in
// js/connection.js and is shared by every page. promptForEndpoint(),
// clearEndpointHint() and mountConnectionControl() come from there.

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
