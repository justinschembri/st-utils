// Oscilloscope chart panel — time-series trace rendering and navigation.

const CHART_TRACE_COLOR = '#22d3ee';

// Palette for comparison series, drawn from the theme accents so a multi-series
// chart still looks like the rest of the app. First entry matches the
// single-series colour, so turning comparison on does not recolour what is
// already on screen.
const CHART_SERIES_COLORS = [
    '#22d3ee',  // accent (cyan)
    '#f472b6',  // accent-3 (magenta)
    '#34d399',  // ok (green)
    '#fbbf24',  // warn (amber)
    '#818cf8',  // accent-2 (indigo)
    '#fb7185',  // bad (rose)
];

/**
 * Group series by unit of measure.
 *
 * Plotting °C against ppm on one axis is meaningless — CO2 in the hundreds
 * flattens temperature into a line along the bottom. Series sharing a unit
 * share an axis; a second unit gets the right-hand axis. A third would need a
 * third scale, which is unreadable, so it is refused rather than drawn wrong.
 */
const CHART_MAX_UNIT_AXES = 2;

function groupSeriesByUnit(series) {
    const groups = [];
    for (const s of series) {
        const unit = s.unitSymbol || '';
        let group = groups.find(g => g.unit === unit);
        if (!group) {
            group = { unit, axisId: groups.length === 0 ? 'y' : 'y2', series: [] };
            groups.push(group);
        }
        group.series.push(s);
    }
    return groups;
}
// Break the trace when an interval exceeds this multiple of the estimated cadence.
const GAP_CADENCE_FACTOR = 2.5;
const CHART_ANIMATION_MS = 420;

const CHART_IDLE_HTML = `
    <div class="no-data-message">
        <div class="no-data-icon" aria-hidden="true">
            <svg viewBox="0 0 48 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M1 12h7l3-9 5 18 4-13 3 7h6l3-4 4 4h8" />
            </svg>
        </div>
        <h3>No signal locked</h3>
        <p>Select a datastream from a Thing to trace its time series</p>
    </div>`;

function initChartPanel() {
    const chartPanelTitle = document.querySelector('.chart-panel-title > div:not(.chart-panel-nav)');
    if (chartPanelTitle) {
        chartPanelTitle.addEventListener('click', (e) => {
            if (!e.target.closest('button') && !e.target.closest('.chart-panel-nav')) {
                toggleChartPanel();
            }
        });
    }

    const chartPanelToggle = document.getElementById('chartPanelToggle');
    if (chartPanelToggle) {
        chartPanelToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleChartPanel();
        });
    }

    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const limit = parseInt(e.target.dataset.limit || e.target.closest('button').dataset.limit, 10);
            setChartLimit(limit);
        });
    });

    document.querySelectorAll('.chart-panel-btn[data-range]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            setChartRange(btn.dataset.range);
        });
    });

    const customBtn = document.getElementById('chartRangeCustomBtn');
    const popover = document.getElementById('chartRangePopover');
    if (customBtn && popover) {
        customBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            setChartRangePopover(popover.hidden);
        });

        popover.addEventListener('click', e => e.stopPropagation());

        document.getElementById('chartRangeApply')?.addEventListener('click', (e) => {
            e.stopPropagation();
            if (applyCustomChartRange()) setChartRangePopover(false);
        });

        document.getElementById('chartRangeClear')?.addEventListener('click', (e) => {
            e.stopPropagation();
            document.getElementById('chartRangeFrom').value = '';
            document.getElementById('chartRangeTo').value = '';
            setChartRange('all');
            setChartRangePopover(false);
        });

        ['chartRangeFrom', 'chartRangeTo'].forEach(id => {
            document.getElementById(id)?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && applyCustomChartRange()) setChartRangePopover(false);
                if (e.key === 'Escape') setChartRangePopover(false);
            });
        });

        // Click anywhere else closes it, matching the endpoint switcher.
        document.addEventListener('click', (e) => {
            if (!popover.hidden && !e.target.closest('#chartRangeGroup')) {
                setChartRangePopover(false);
            }
        });
    }

    document.getElementById('chartCompareBtn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
        setCompareMode(!state.compareMode);
    });

    const chartNextDatastreamBtn = document.getElementById('chartNextDatastreamBtn');
    if (chartNextDatastreamBtn) {
        chartNextDatastreamBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            navigateToDatastream(1);
        });
    }
}

function resetChartPanel() {
    destroyChartInstance();

    state.currentDatastream = null;
    state.currentDatastreamIndex = -1;

    const dsPills = document.getElementById('chartDatastreamPills');
    if (dsPills) {
        dsPills.hidden = true;
        dsPills.innerHTML = '';
    }

    const content = document.getElementById('chartPanelContent');
    if (content) content.innerHTML = CHART_IDLE_HTML;

    document.getElementById('chartTitle').textContent = 'No signal locked';
    document.getElementById('chartSubtitle').textContent = 'Select a datastream from a Thing to trace it';
    document.getElementById('chartNextDatastreamBtn').style.display = 'none';
}

async function selectDatastream(datastreamId, datastreamName) {
    state.currentDatastream = datastreamId;
    state.currentDatastreamIndex = state.currentThingDatastreams.findIndex(
        ds => frostEntityId(ds) === datastreamId
    );

    document.querySelectorAll('.metadata-datastream-item').forEach(item => {
        item.classList.remove('active');
    });

    document.getElementById('chartTitle').textContent = datastreamName;
    document.getElementById('chartSubtitle').textContent = `Datastream ID: ${datastreamId}`;

    const chartPanel = document.getElementById('chartPanel');
    if (!chartPanel.classList.contains('expanded')) {
        chartPanel.classList.add('expanded');
    }

    mobileCollapseRoster();
    hideThingMetadata();
    updateDatastreamNavigation();
    renderDatastreamPills(datastreamId);

    await loadChartData(datastreamId);
}

function renderDatastreamPills(activeId) {
    const container = document.getElementById('chartDatastreamPills');
    if (!container) return;

    const datastreams = state.currentThingDatastreams || [];
    if (datastreams.length < 2) {
        container.hidden = true;
        container.innerHTML = '';
        return;
    }

    container.innerHTML = '';
    const fragment = document.createDocumentFragment();
    const active = activeDatastreamIds();

    datastreams.forEach(ds => {
        const id = frostEntityId(ds);
        const displayName = formatDatastreamName(ds.name);
        const selected = active.includes(id);
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'chart-ds-pill' + (selected ? ' active' : '');

        if (state.compareMode && selected) {
            // Colour the pill to match its trace so the legend, the stats rows
            // and the pills all agree on which series is which.
            const color = CHART_SERIES_COLORS[active.indexOf(id) % CHART_SERIES_COLORS.length];
            pill.style.borderColor = color;
            pill.style.color = color;
        }

        pill.dataset.datastreamId = id;
        pill.textContent = displayName;
        pill.title = displayName;
        pill.addEventListener('click', (e) => {
            e.stopPropagation();
            if (state.compareMode) {
                toggleComparedDatastream(id, displayName);
            } else if (id !== state.currentDatastream) {
                selectDatastream(id, displayName);
            }
        });
        fragment.appendChild(pill);
    });

    container.appendChild(fragment);
    container.hidden = false;
}

/** Add or remove a series from the comparison. */
function toggleComparedDatastream(datastreamId, displayName) {
    const active = activeDatastreamIds();

    if (!active.includes(datastreamId)) {
        state.comparedIds = [...state.comparedIds, datastreamId];
    } else if (datastreamId === state.currentDatastream) {
        // Removing the primary: promote the first comparison series so the
        // panel title and the prev/next navigation still refer to something.
        const [next, ...rest] = state.comparedIds;
        if (next === undefined) return;      // never leave the chart empty
        state.currentDatastream = next;
        state.comparedIds = rest;
    } else {
        state.comparedIds = state.comparedIds.filter(id => id !== datastreamId);
    }

    renderDatastreamPills(state.currentDatastream);
    loadChartData(state.currentDatastream);
}

/** Panel heading reflects one series or a comparison. */
function syncChartTitle() {
    const count = activeDatastreamIds().length;
    const title = document.getElementById('chartTitle');
    const subtitle = document.getElementById('chartSubtitle');
    if (!title || !subtitle) return;

    if (count > 1) {
        title.textContent = `${count} datastreams`;
        subtitle.textContent = 'Comparing';
        return;
    }
    const primary = (state.chartSeries || [])[0];
    if (primary) {
        title.textContent = primary.name;
        subtitle.textContent = `Datastream ID: ${primary.datastreamId}`;
    }
}

/** Turn comparison on or off; leaving it drops the extra series. */
function setCompareMode(on) {
    state.compareMode = on;
    document.getElementById('chartCompareBtn')?.classList.toggle('active', on);
    document.getElementById('chartDatastreamPills')?.classList.toggle('is-comparing', on);

    if (!on && state.comparedIds.length) {
        state.comparedIds = [];
        renderDatastreamPills(state.currentDatastream);
        loadChartData(state.currentDatastream);
        return;
    }
    renderDatastreamPills(state.currentDatastream);
}

function ensureChartShell() {
    const content = document.getElementById('chartPanelContent');
    if (!content || content.querySelector('#chartTrace')) return;

    content.innerHTML = `
        <div class="chart-trace" id="chartTrace">
            <div class="chart-stats" id="chartStats"></div>
            <div class="chart-container">
                <canvas id="timeSeriesChart"></canvas>
            </div>
        </div>
        <div class="chart-overlay" id="chartOverlay" hidden></div>`;
}

function showChartOverlay(html) {
    ensureChartShell();
    const overlay = document.getElementById('chartOverlay');
    const trace = document.getElementById('chartTrace');
    if (!overlay || !trace) return;

    overlay.innerHTML = html;
    overlay.hidden = false;
    trace.classList.add('is-dimmed');
}

function hideChartOverlay() {
    const overlay = document.getElementById('chartOverlay');
    const trace = document.getElementById('chartTrace');
    if (overlay) {
        overlay.hidden = true;
        overlay.innerHTML = '';
    }
    trace?.classList.remove('is-dimmed');
}

function destroyChartInstance() {
    if (state.currentChart) {
        state.currentChart.destroy();
        state.currentChart = null;
    }
}

// Maximum points to fetch and cache (matches the highest UI limit button).
//
// Sized against wire cost, not screen resolution. An STA observation is ~392
// bytes on the dev stack, so 10k ≈ 3.7MB per datastream selection — noticeable
// but tolerable, including cross-origin to a remote server. 25k would be ~9.4MB
// for every click, which is not.
//
// Raising this does *not* make the trace more detailed: there is no chart zoom,
// and Chart.js decimates to 600 LTTB samples for rendering anyway. What it buys
// is a longer window (10k at a 5-minute cadence is ~35 days, against ~9 days at
// 2.5k) and statistics computed over more of the series. Explicit date-range
// selection is the real answer and supersedes this knob.
const CHART_MAX_POINTS = 10000;

// Array-result observations unpack into many points each and are paged one
// entity at a time, so the same ceiling would mean thousands of round trips.
const CHART_MAX_POINTS_ARRAY = 2500;

/** Ids currently on the chart: the primary plus any comparison series. */
function activeDatastreamIds() {
    const ids = [];
    if (state.currentDatastream != null) ids.push(state.currentDatastream);
    for (const id of state.comparedIds) {
        if (!ids.includes(id)) ids.push(id);
    }
    return ids;
}

/** Fetch one datastream's metadata and points. */
async function loadSeries(datastreamId) {
    const dsResponse = await frostFetch(`${state.frostRoot}/Datastreams(${datastreamId})`);
    if (!dsResponse.ok) throw new Error(`HTTP error! Status: ${dsResponse.status}`);
    const dsData = await dsResponse.json();

    const { points, observationTotal } = await fetchChartPoints(datastreamId, CHART_MAX_POINTS);
    return {
        datastreamId,
        name: formatDatastreamName(dsData.name || 'Unknown'),
        unitSymbol: frostUnitSymbol(dsData),
        points,
        observationTotal,
    };
}

async function loadChartData(datastreamId) {
    updateStatus('Loading chart data...', '');
    showChartOverlay('<div class="no-data-message"><div class="loading"></div> Loading trace…</div>');

    try {
        const ids = activeDatastreamIds();
        // Fetched in parallel: comparison is only useful if adding a series is
        // cheap, and these are independent requests.
        const series = await Promise.all(ids.map(loadSeries));

        state.chartSeries = series;
        // Derived from the series that actually loaded, so a promoted primary
        // names itself correctly; syncing before the fetch reads the previous
        // selection and leaves a stale name in the header.
        syncChartTitle();
        // Keep the single-series cache in step — setChartLimit and the range
        // controls still read it to decide whether a refetch is needed.
        const primary = series[0];
        state.chartPointCache = primary ? {
            datastreamId: primary.datastreamId,
            rangeKey: chartRangeKey(),
            points: primary.points,
            observationTotal: primary.observationTotal,
            unitSymbol: primary.unitSymbol,
            datastreamName: primary.name,
        } : null;

        renderFromCache();
    } catch (error) {
        console.error('Error loading chart data:', error);
        destroyChartInstance();
        document.getElementById('chartPanelContent').innerHTML = `
            <div class="no-data-message">
                <h3>Could not load this datastream</h3>
                <p>${error.message}</p>
            </div>`;
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

function renderFromCache() {
    const series = state.chartSeries || [];
    const withData = series.filter(s => s.points.length);

    if (!withData.length) {
        destroyChartInstance();
        // Distinguish "this datastream is empty" from "your window is empty" —
        // otherwise picking 24h on a stale sensor looks like missing data.
        const windowed = chartRangeFilter() !== '';
        document.getElementById('chartPanelContent').innerHTML = windowed
            ? `<div class="no-data-message">
                <h3>No observations in this range</h3>
                <p>Nothing recorded in the selected window. Try a wider range, or All.</p>
            </div>`
            : `<div class="no-data-message">
                <h3>No observations found</h3>
                <p>This datastream has no observation data available.</p>
            </div>`;
        updateStatus(
            windowed ? 'No observations in the selected range' : 'No data available',
            'warning',
        );
        return;
    }

    // Slice each series to the point limit independently: they may have very
    // different cadences, and "last N points" means N of *that* series.
    const shown = withData.map(s => ({
        ...s,
        shownPoints: s.points.length > state.currentLimit
            ? s.points.slice(-state.currentLimit)
            : s.points,
    }));

    renderOrUpdateChart(shown);
    hideChartOverlay();

    const primary = shown[0];
    if (shown.length === 1) {
        // Say plainly when this is the newest slice rather than the whole series
        // — every statistic on screen is computed over the shown points only.
        const total = primary.observationTotal;
        updateStatus(
            Number.isFinite(total) && total > primary.shownPoints.length
                ? `Showing newest ${primary.shownPoints.length.toLocaleString()} of `
                  + `${total.toLocaleString()} observations`
                : `Loaded ${primary.shownPoints.length.toLocaleString()} observations`,
            'success',
        );
    } else {
        const totalPoints = shown.reduce((n, s) => n + s.shownPoints.length, 0);
        updateStatus(
            `Comparing ${shown.length} datastreams · ${totalPoints.toLocaleString()} points`,
            'success',
        );
    }
}

// Array observations can unpack into thousands of points each, so page them
// one entity at a time. Scalar streams use a single $top=pointLimit request.

function finalizeChartPoints(collected, pointLimit) {
    if (collected.length === 0) return [];
    collected.sort((a, b) => a.x.getTime() - b.x.getTime());
    if (collected.length > pointLimit) {
        return collected.slice(-pointLimit);
    }
    return collected;
}

// ── Time range ─────────────────────────────────────────────────────────────
// Rolling presets, in milliseconds. 'all' and 'custom' are handled separately.
const CHART_RANGE_PRESETS = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
};

/** Resolve state.chartRange to concrete {from, to} Dates; null means unbounded. */
function chartRangeBounds(range = state.chartRange) {
    if (!range || range.preset === 'all') return { from: null, to: null };
    if (range.preset === 'custom') {
        return { from: range.from || null, to: range.to || null };
    }
    const span = CHART_RANGE_PRESETS[range.preset];
    if (!span) return { from: null, to: null };
    return { from: new Date(Date.now() - span), to: null };
}

/**
 * OData predicate for the active range, or '' when unbounded.
 *
 * Always emits a full RFC3339 instant via toISOString(). A date-only literal
 * (`phenomenonTime ge 2026-08-01`) makes FROST 2.6 answer 500, not 400, so this
 * is worth keeping deliberate. The OData 3 `datetime'...'` form is rejected too;
 * STA 1.1 wants the bare literal.
 */
function chartRangeFilter(range = state.chartRange) {
    const { from, to } = chartRangeBounds(range);
    const clauses = [];
    if (from instanceof Date && !Number.isNaN(from.getTime())) {
        clauses.push(`phenomenonTime ge ${from.toISOString()}`);
    }
    if (to instanceof Date && !Number.isNaN(to.getTime())) {
        clauses.push(`phenomenonTime le ${to.toISOString()}`);
    }
    return clauses.join(' and ');
}

/**
 * Cache identity for a range. The cached points are whatever the *server*
 * returned for a given window, so a window change is a different dataset, not a
 * different view of the same one — without this in the key, switching range
 * would redraw stale points.
 */
function chartRangeKey(range = state.chartRange) {
    const { from, to } = chartRangeBounds(range);
    if (range?.preset && range.preset !== 'custom' && range.preset !== 'all') {
        // Rolling presets move with the clock; key on the preset, not the
        // computed instant, or every render would look like a new range.
        return range.preset;
    }
    return `${from ? from.toISOString() : '*'}..${to ? to.toISOString() : '*'}`;
}

function observationsUrl(datastreamId, top) {
    // $count=true rides along on a request we already make — FROST returns the
    // datastream's full observation total next to the page, at no extra cost.
    // Without it the chart cannot tell whether it is showing everything or a
    // truncated tail, which is the difference between a reading and a guess.
    const filter = chartRangeFilter();
    return (
        `${state.frostRoot}/Datastreams(${datastreamId})/Observations` +
        `?$top=${top}&$count=true&$orderby=phenomenonTime%20desc` +
        (filter ? `&$filter=${encodeURIComponent(filter)}` : '')
    );
}

async function fetchObservationsPage(url) {
    const response = await frostFetch(url);
    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
    return response.json();
}

// Probe the newest observation: array result → careful paging; scalar → one shot.
// Returns the points plus the datastream's total observation count, so callers
// can tell a complete trace from a truncated tail.
async function fetchChartPoints(datastreamId, pointLimit) {
    const probeUrl = observationsUrl(datastreamId, 1);
    const probeData = await fetchObservationsPage(probeUrl);
    const probePage = probeData.value || [];
    const observationTotal = frostCount(probeData, state.frostVersion);
    if (probePage.length === 0) return { points: [], observationTotal: 0 };

    const newest = probePage[0];
    const points = isArrayResult(newest.result)
        ? await fetchArrayChartPoints(
            Math.min(pointLimit, CHART_MAX_POINTS_ARRAY), newest, probeData, probeUrl)
        : await fetchScalarChartPoints(datastreamId, pointLimit);

    return { points, observationTotal };
}

async function fetchScalarChartPoints(datastreamId, pointLimit) {
    const obsData = await fetchObservationsPage(observationsUrl(datastreamId, pointLimit));
    const page = obsData.value || [];
    if (page.length === 0) return [];

    const collected = [];
    for (const obs of page) {
        collected.push(...expandObservationToPoints(obs));
    }
    return finalizeChartPoints(collected, pointLimit);
}

async function fetchArrayChartPoints(pointLimit, firstObs, firstPageData, firstPageUrl) {
    const collected = [];

    collected.push(...expandObservationToPoints(firstObs, pointLimit));
    if (collected.length >= pointLimit) {
        return finalizeChartPoints(collected, pointLimit);
    }

    let nextUrl = frostNextLink(firstPageData, firstPageUrl);
    if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);

    // Probe used $top=1; follow next-links one observation at a time.
    while (nextUrl && collected.length < pointLimit) {
        const obsData = await fetchObservationsPage(nextUrl);
        const page = obsData.value || [];
        if (page.length === 0) break;

        for (const obs of page) {
            const remaining = pointLimit - collected.length;
            collected.push(...expandObservationToPoints(obs, remaining > 0 ? remaining : null));
            if (collected.length >= pointLimit) break;
        }

        nextUrl = frostNextLink(obsData, nextUrl);
        if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
    }

    return finalizeChartPoints(collected, pointLimit);
}

function medianOf(sortedValues) {
    if (sortedValues.length === 0) return null;
    const mid = Math.floor(sortedValues.length / 2);
    if (sortedValues.length % 2 === 0) {
        return (sortedValues[mid - 1] + sortedValues[mid]) / 2;
    }
    return sortedValues[mid];
}

function interPointDeltasMs(points) {
    const deltas = [];
    for (let i = 1; i < points.length; i += 1) {
        const delta = points[i].x.getTime() - points[i - 1].x.getTime();
        if (delta > 0) deltas.push(delta);
    }
    return deltas;
}

// Infer reporting cadence from inter-arrival times, ignoring intervals that
// already look like outages so a long gap does not skew the estimate.
function estimateCadenceMs(points) {
    const deltas = interPointDeltasMs(points);
    if (deltas.length === 0) return null;

    deltas.sort((a, b) => a - b);
    let cadence = medianOf(deltas);
    if (!cadence) return null;

    const inliers = deltas.filter(d => d <= cadence * 4);
    if (inliers.length >= Math.max(2, Math.ceil(deltas.length * 0.25))) {
        inliers.sort((a, b) => a - b);
        cadence = medianOf(inliers);
    }

    return cadence;
}

function gapThresholdMs(cadenceMs) {
    if (!cadenceMs || cadenceMs <= 0) return Infinity;
    return cadenceMs * GAP_CADENCE_FACTOR;
}

function formatCadence(ms) {
    if (!ms || ms <= 0) return null;
    const seconds = ms / 1000;
    if (seconds < 90) return `${Math.round(seconds)}s`;
    const minutes = ms / 60000;
    if (minutes < 90) return `${Math.round(minutes)}m`;
    const hours = ms / 3600000;
    if (hours < 48) return `${hours < 10 ? hours.toFixed(1) : Math.round(hours)}h`;
    const days = ms / 86400000;
    return `${days < 10 ? days.toFixed(1) : Math.round(days)}d`;
}

function splitTraceSegments(points, cadenceMs) {
    if (points.length === 0) return [];
    if (points.length === 1) return [points];

    const gapMs = gapThresholdMs(cadenceMs);
    const segments = [[points[0]]];
    for (let i = 1; i < points.length; i += 1) {
        const prev = points[i - 1];
        const curr = points[i];
        const interval = curr.x.getTime() - prev.x.getTime();
        if (interval > gapMs) {
            segments.push([curr]);
        } else {
            segments[segments.length - 1].push(curr);
        }
    }
    return segments;
}

function calculateChartStats(points, segmentCount, unitSymbol, cadenceMs) {
    const values = points.map(p => p.y);
    const current = values[values.length - 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const gaps = Math.max(0, segmentCount - 1);

    return {
        current: current.toFixed(2),
        min: min.toFixed(2),
        max: max.toFixed(2),
        avg: avg.toFixed(2),
        unit: unitSymbol,
        gaps,
        cadence: formatCadence(cadenceMs),
        totalPoints: values.length,
        latestTime: points[points.length - 1].x,
    };
}

function renderChartStats(stats) {
    let latestStampHTML = '';
    if (stats.latestTime instanceof Date && !Number.isNaN(stats.latestTime.getTime())) {
        const mins = (Date.now() - stats.latestTime.getTime()) / 60000;
        const tier = getHealthTier(mins);
        const absText = stats.latestTime.toLocaleString([], {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
        const relText = formatTimeSince(mins);
        const bg = hexToRgba(tier.color, 0.14);
        const bd = hexToRgba(tier.color, 0.34);
        const fg = lightenHex(tier.color, 0.35);
        latestStampHTML = `
            <div class="stat-timestamp" title="${absText}"
                 style="background:${bg};border-color:${bd};color:${fg};">
                ${relText}
            </div>`;
    }

    return `
        <div class="stat-card">
            <span class="stat-label">Latest</span>
            <span class="stat-value">${stats.current}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
            ${latestStampHTML}
        </div>
        <div class="stat-card">
            <span class="stat-label">Min</span>
            <span class="stat-value">${stats.min}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Max</span>
            <span class="stat-value">${stats.max}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Avg</span>
            <span class="stat-value">${stats.avg}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
        </div>
        ${stats.gaps > 0 ? `
        <div class="stat-card stat-card-gap">
            <span class="stat-label">Gaps</span>
            <span class="stat-value"><span class="gap-indicator"></span>${stats.gaps}</span>
        </div>` : ''}
        <div class="stat-card">
            <span class="stat-label">Points</span>
            <span class="stat-value">${stats.totalPoints}</span>
        </div>
        ${stats.cadence ? `
        <div class="stat-card">
            <span class="stat-label">Cadence</span>
            <span class="stat-value">~${stats.cadence}</span>
        </div>` : ''}`;
}

function buildTraceDataset(points, cadenceMs, datastreamName, unitSymbol, gradient,
                           color = CHART_TRACE_COLOR, axisId = 'y', filled = true) {
    const gapMs = gapThresholdMs(cadenceMs);

    function intervalBefore(index) {
        if (index <= 0) return 0;
        return points[index].x.getTime() - points[index - 1].x.getTime();
    }

    function isGapBoundary(index) {
        return index > 0 && intervalBefore(index) > gapMs;
    }

    return {
        label: unitSymbol ? `${datastreamName} (${unitSymbol})` : datastreamName,
        unitSymbol,
        yAxisID: axisId,
        data: points,
        parsing: false,
        borderColor: color,
        backgroundColor: gradient,
        borderWidth: 2,
        // Only a lone series is filled: overlapping translucent fills muddy
        // every trace underneath and make a comparison harder to read.
        fill: filled ? 'origin' : false,
        tension: 0.22,
        cubicInterpolationMode: 'monotone',
        pointRadius: 0,
        pointHoverRadius: 0,
        pointHitRadius: 10,
        // Break line and fill at cadence gaps without splitting into separate
        // datasets (which caused post-gap traces to drop out).
        segment: {
            borderColor(ctx) {
                return isGapBoundary(ctx.p1DataIndex) ? 'transparent' : color;
            },
            backgroundColor(ctx) {
                return isGapBoundary(ctx.p1DataIndex) ? 'transparent' : gradient;
            },
        },
    };
}

function buildChartOptions(points, unitGroups = []) {
    const xTimes = points.map(p => p.x.getTime());
    const xMin = xTimes.length ? Math.min(...xTimes) : undefined;
    const xMax = xTimes.length ? Math.max(...xTimes) : undefined;

    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: CHART_ANIMATION_MS,
            easing: 'easeOutQuart',
        },
        interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false,
        },
        elements: {
            point: {
                radius: 0,
                hoverRadius: 0,
                hitRadius: 10,
            },
        },
        plugins: {
            legend: {
                // Only worth the vertical space when there is more than one
                // trace to tell apart.
                display: unitGroups.reduce((n, g) => n + g.series.length, 0) > 1,
                position: 'top',
                align: 'end',
                labels: {
                    boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'line',
                    color: '#9fb0c3', font: { size: 11 },
                },
            },
            decimation: {
                enabled: points.length > 600,
                algorithm: 'lttb',
                samples: 600,
            },
            tooltip: {
                backgroundColor: 'rgba(5, 9, 18, 0.92)',
                borderColor: 'rgba(34, 211, 238, 0.4)',
                borderWidth: 1,
                titleColor: '#9fb0c3',
                bodyColor: '#e6eef7',
                padding: 12,
                cornerRadius: 10,
                displayColors: false,
                titleFont: { family: "'Space Grotesk', sans-serif", weight: '500', size: 11 },
                bodyFont: { family: "'JetBrains Mono', monospace", weight: '600', size: 13 },
                callbacks: {
                    label(context) {
                        const v = context.parsed.y;
                        const unit = context.dataset.unitSymbol || '';
                        return `${v != null ? v.toFixed(2) : 'N/A'} ${unit}`.trim();
                    },
                },
            },
        },
        scales: {
            x: {
                type: 'time',
                min: xMin,
                max: xMax,
                time: {
                    tooltipFormat: 'yyyy-MM-dd HH:mm',
                    displayFormats: {
                        minute: 'HH:mm',
                        hour: 'HH:mm',
                        day: 'MMM dd',
                    },
                },
                border: { display: false },
                ticks: {
                    autoSkip: true,
                    maxTicksLimit: 8,
                    maxRotation: 0,
                    color: '#6b7c93',
                    font: { family: "'JetBrains Mono', monospace", size: 10 },
                },
                grid: { display: false },
            },
            y: {
                beginAtZero: false,
                position: 'left',
                title: unitGroups[0]?.unit
                    ? { display: true, text: unitGroups[0].unit, color: '#6b7c93',
                        font: { family: "'JetBrains Mono', monospace", size: 10 } }
                    : { display: false },
                border: { display: false },
                ticks: {
                    color: '#6b7c93',
                    font: { family: "'JetBrains Mono', monospace", size: 10 },
                    padding: 8,
                },
                grid: {
                    color: 'rgba(140, 170, 210, 0.1)',
                    drawTicks: false,
                },
            },
            // Second unit gets the right-hand axis. Its gridlines are off so
            // two sets of horizontal lines do not overlay each other.
            ...(unitGroups.length > 1 ? {
                y2: {
                    beginAtZero: false,
                    position: 'right',
                    title: { display: true, text: unitGroups[1].unit, color: '#6b7c93',
                             font: { family: "'JetBrains Mono', monospace", size: 10 } },
                    border: { display: false },
                    ticks: {
                        color: '#6b7c93',
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                        padding: 8,
                    },
                    grid: { drawOnChartArea: false },
                },
            } : {}),
        },
    };
}

/**
 * Draw every series in `shown` (each with a `shownPoints` array).
 *
 * Series are grouped by unit so a second unit lands on the right-hand axis;
 * beyond two units the chart says so rather than plotting values that cannot
 * share a scale.
 */
function renderOrUpdateChart(shown) {
    ensureChartShell();

    const unitGroups = groupSeriesByUnit(shown);
    const overflow = unitGroups.slice(CHART_MAX_UNIT_AXES);
    const drawable = unitGroups.slice(0, CHART_MAX_UNIT_AXES);
    const drawnSeries = drawable.flatMap(g => g.series);

    const statsEl = document.getElementById('chartStats');
    if (statsEl) {
        statsEl.innerHTML = shown.length === 1
            ? renderChartStats(singleSeriesStats(shown[0]))
            : renderComparisonStats(drawnSeries, shown);
    }

    const canvas = document.getElementById('timeSeriesChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const allPoints = drawnSeries.flatMap(s => s.shownPoints);
    const options = buildChartOptions(allPoints, drawable);

    const datasets = [];
    drawable.forEach(group => {
        group.series.forEach(series => {
            const index = drawnSeries.indexOf(series);
            const color = CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length];

            let gradient = color;
            if (drawnSeries.length === 1) {
                gradient = ctx.createLinearGradient(0, 0, 0, 340);
                gradient.addColorStop(0, 'rgba(34, 211, 238, 0.35)');
                gradient.addColorStop(0.55, 'rgba(34, 211, 238, 0.08)');
                gradient.addColorStop(1, 'rgba(34, 211, 238, 0)');
            }

            datasets.push(buildTraceDataset(
                series.shownPoints,
                estimateCadenceMs(series.shownPoints),
                series.name,
                series.unitSymbol,
                gradient,
                color,
                group.axisId,
                drawnSeries.length === 1,
            ));
        });
    });

    if (overflow.length) {
        const units = overflow.map(g => g.unit || 'unitless').join(', ');
        updateStatus(`Not shown: ${units} — only two units can share a chart`, 'warning');
    }

    Chart.defaults.font.family = "'Space Grotesk', sans-serif";
    Chart.defaults.color = '#9fb0c3';

    // A changed axis set means a different chart shape; rebuild rather than
    // patch, or Chart.js keeps the stale scale around.
    const axesChanged = state.currentChart
        && !!state.currentChart.options.scales.y2 !== (drawable.length > 1);
    if (axesChanged) destroyChartInstance();

    if (state.currentChart) {
        state.currentChart.data.datasets = datasets;
        state.currentChart.options = options;
        state.currentChart.update('active');
        scheduleChartResize();
        return;
    }

    state.currentChart = new Chart(ctx, { type: 'line', data: { datasets }, options });
    scheduleChartResize();
}

/** Stats for the single-series case, unchanged in appearance. */
function singleSeriesStats(series) {
    const cadenceMs = estimateCadenceMs(series.shownPoints);
    const segments = splitTraceSegments(series.shownPoints, cadenceMs);
    const stats = calculateChartStats(series.shownPoints, segments.length, series.unitSymbol, cadenceMs);
    stats.observationTotal = series.observationTotal;
    return stats;
}

/**
 * Compact per-series readout when comparing.
 *
 * The single-series pills (LATEST / MIN / MAX / AVG) become ambiguous with more
 * than one trace — whose latest? — so each series gets its own row instead,
 * colour-matched to its line.
 */
function renderComparisonStats(drawnSeries, allSeries) {
    const hidden = allSeries.length - drawnSeries.length;
    const rows = drawnSeries.map((series, index) => {
        const values = series.shownPoints.map(p => p.y);
        const color = CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length];
        const unit = series.unitSymbol ? ` ${series.unitSymbol}` : '';
        const latest = values[values.length - 1];
        return `
            <div class="chart-compare-row">
                <span class="chart-compare-swatch" style="background:${color}"></span>
                <span class="chart-compare-name">${series.name}</span>
                <span class="chart-compare-stat">last <b>${latest.toFixed(2)}${unit}</b></span>
                <span class="chart-compare-stat">min <b>${Math.min(...values).toFixed(2)}</b></span>
                <span class="chart-compare-stat">max <b>${Math.max(...values).toFixed(2)}</b></span>
                <span class="chart-compare-stat">${values.length.toLocaleString()} pts</span>
            </div>`;
    }).join('');

    const note = hidden
        ? `<p class="chart-compare-note">${hidden} series hidden — a chart can only carry two units.</p>`
        : '';
    return `<div class="chart-compare-stats">${rows}${note}</div>`;
}

function scheduleChartResize() {
    requestAnimationFrame(() => {
        state.currentChart?.resize();
    });
}

function setChartLimit(limit) {
    state.currentLimit = limit;

    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.dataset.limit, 10) === limit);
    });

    if (chartCacheIsCurrent()) {
        renderFromCache();
    } else if (state.currentDatastream) {
        loadChartData(state.currentDatastream);
    }
}

/** True when the cached points are for the datastream *and* window on screen. */
function chartCacheIsCurrent() {
    const cache = state.chartPointCache;
    return !!cache
        && cache.datastreamId === state.currentDatastream
        && cache.rangeKey === chartRangeKey();
}

/**
 * Apply a time window and reload.
 *
 * Always refetches: the window is a server-side $filter, so a different window
 * is a different set of observations — not a subset of what is already cached.
 * (The point *limit* is the opposite: it slices the cache and needs no request.)
 */
function setChartRange(preset, from = null, to = null) {
    state.chartRange = { preset, from, to };

    document.querySelectorAll('.chart-panel-btn[data-range]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.range === preset);
    });
    // The Custom button carries the active state when no preset does.
    document.getElementById('chartRangeCustomBtn')
        ?.classList.toggle('active', preset === 'custom');
    syncChartRangeInputs();

    if (state.currentDatastream) {
        loadChartData(state.currentDatastream);
    }
}

/** Mirror the active window into the custom from/to inputs. */
function syncChartRangeInputs() {
    const fromInput = document.getElementById('chartRangeFrom');
    const toInput = document.getElementById('chartRangeTo');
    if (!fromInput || !toInput) return;

    // datetime-local wants local wall-clock 'YYYY-MM-DDTHH:mm' with no zone.
    const toLocalInput = (date) => {
        if (!(date instanceof Date) || Number.isNaN(date.getTime())) return '';
        const pad = n => String(n).padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
            + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    };

    const { from, to } = chartRangeBounds();
    fromInput.value = toLocalInput(from);
    toInput.value = toLocalInput(to);
}

/** Open or close the custom-range popover. */
function setChartRangePopover(open) {
    const popover = document.getElementById('chartRangePopover');
    const btn = document.getElementById('chartRangeCustomBtn');
    if (!popover || !btn) return;
    popover.hidden = !open;
    btn.setAttribute('aria-expanded', String(open));
    if (open) {
        syncChartRangeInputs();
        document.getElementById('chartRangeFrom')?.focus();
    }
}

/**
 * Read the custom inputs and apply them as the window.
 * Returns true when a window was applied, false when the input was rejected.
 */
function applyCustomChartRange() {
    const fromInput = document.getElementById('chartRangeFrom');
    const toInput = document.getElementById('chartRangeTo');
    if (!fromInput || !toInput) return false;

    // A datetime-local value has no zone, so `new Date(...)` reads it as local
    // time — which is what the user meant. toISOString() converts to UTC later.
    const parse = (value) => {
        if (!value) return null;
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? null : date;
    };

    const from = parse(fromInput.value);
    const to = parse(toInput.value);

    if (from && to && from > to) {
        updateStatus('Range start is after its end', 'error');
        return false;
    }
    if (!from && !to) {
        setChartRange('all');
        return true;
    }
    setChartRange('custom', from, to);
    return true;
}

function toggleChartPanel() {
    document.getElementById('chartPanel')?.classList.toggle('expanded');
}

function updateDatastreamNavigation() {
    const nextBtn = document.getElementById('chartNextDatastreamBtn');
    if (!nextBtn) return;

    const hasMultiple = state.currentThingDatastreams.length > 1;
    nextBtn.style.display = hasMultiple ? 'flex' : 'none';
    nextBtn.disabled = false;
}

function navigateToDatastream(direction) {
    if (state.currentThingDatastreams.length === 0) return;

    let newIndex = state.currentDatastreamIndex + direction;
    if (newIndex < 0) {
        newIndex = state.currentThingDatastreams.length - 1;
    } else if (newIndex >= state.currentThingDatastreams.length) {
        newIndex = 0;
    }

    const datastream = state.currentThingDatastreams[newIndex];
    selectDatastream(frostEntityId(datastream), formatDatastreamName(datastream.name));
}
