// Core application — map, health, things fetch, metadata, and bootstrap.
// Shared modules: js/config.js, js/state.js, js/api.js, js/ui.js, js/chart.js, js/roster.js

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();
    initializeEventListeners();
    // With no STA server configured there is nothing to fetch — show an empty
    // map and let the endpoint switcher collect a server URL. Applying one
    // calls resetAndReload(), which starts the normal fetch path.
    if (state.isConfigured) {
        fetchThings();
    } else {
        promptForEndpoint();
    }
});

// True until the user picks an endpoint themselves. A boot-time endpoint comes
// from stored or deployed config that nobody typed in this session, so if it
// turns out to be unreachable the right response is to ask for a server — not
// to show a dead error screen. Once the user has chosen one, failures are their
// answer and get reported normally. Cleared by resetAndReload() (ui.js), which
// only runs from the endpoint switcher. See the catch block in fetchThings().
let isInitialLoad = true;

/**
 * Open whatever `?thing=` or `?datastream=` asked for, once Things are loaded.
 *
 * These links come from the investigate page, so the entity may not be on the
 * map at all — a Thing with no Location has no marker. Fetch the datastream's
 * own name rather than assuming it is one of the selected Thing's, and say so
 * plainly when the target cannot be shown, instead of failing silently.
 */
async function applyDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const thingId = params.get('thing');
    const datastreamId = params.get('datastream');
    if (!thingId && !datastreamId) return;

    try {
        if (datastreamId) {
            const response = await frostFetch(`${state.frostRoot}/Datastreams(${datastreamId})?$expand=Thing`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const datastream = await response.json();

            // Load the parent Thing's datastreams first so the datastream pills
            // and prev/next navigation work, exactly as clicking through the
            // map would. selectDatastream() reads state.currentThingDatastreams.
            const parentId = frostEntityId(datastream.Thing, state.frostVersion);
            if (parentId != null && state.things[parentId]) {
                showThingMetadata(parentId);
                await loadDatastreamsForThing(parentId);
            }

            await selectDatastream(datastreamId, formatDatastreamName(datastream.name || 'Unknown'));
            return;
        }

        const thing = state.things[thingId];
        if (!thing) {
            updateStatus(`Thing ${thingId} is not on the map (it may have no Location)`, 'warning');
            return;
        }
        // Same sequence the roster uses when a Thing is clicked (roster.js).
        if (!thing.virtual && thing.coordinates) {
            state.map.setView(thing.coordinates, 15, { animate: true, duration: 0.8 });
        }
        showThingMetadata(thingId);
        await loadDatastreamsForThing(thingId);
    } catch (error) {
        console.error('Deep link failed:', error);
        updateStatus(`Could not open the requested entity: ${error.message}`, 'error');
    }
}

// Initialize Leaflet map
function initializeMap() {
    state.map = L.map('map', {
        zoomAnimation: true,
        zoomAnimationThreshold: 4, // Animate zoom if difference is less than 4 levels
        fadeAnimation: true,
        markerZoomAnimation: true,
        // Disable the built-in top-left zoom control (the roster sits over it);
        // custom +/- buttons live in the right-side .map-controls stack instead.
        zoomControl: false,
        doubleClickZoom: true,
        scrollWheelZoom: true
    }).setView([52.00482, 4.37034], 13);

    // Modern basemaps (CARTO + Esri imagery) with a tasteful default
    const voyager = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
        updateWhenZooming: true
    });

    const positron = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    });

    const darkMatter = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    });

    const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
        maxZoom: 19
    });

    satellite.addTo(state.map);

    L.control.layers({
        'Satellite': satellite,
        'Dark': darkMatter,
        'Streets': voyager,
        'Light': positron,
    }, null, { position: 'topright', collapsed: true }).addTo(state.map);

    // Initialize marker cluster group
    state.markerCluster = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 80, // Cluster markers within 80 pixels
        disableClusteringAtZoom: 15, // Only show individual markers at zoom 15+
        spiderfyOnMaxZoom: false, // Don't spiderfy, just zoom
        showCoverageOnHover: true, // Show circle indicating cluster area on hover
        zoomToBoundsOnClick: true, // Zoom to bounds when clicking cluster
        animate: true, // Animate marker clustering/unclustering
        animateAddingMarkers: true, // Animate when adding markers
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();

            if (count > state.maxClusterSize) {
                state.maxClusterSize = count;
            }

            // Cluster glow scales cyan -> indigo with group size
            const maxCount = Math.max(state.maxClusterSize, 10);
            const normalized = Math.min(Math.log(count + 1) / Math.log(maxCount + 1), 1);
            // Cyan-400 (#22d3ee) -> Indigo-400 (#818cf8)
            const red = Math.round(34 + (129 - 34) * normalized);
            const green = Math.round(211 - (211 - 140) * normalized);
            const blue = Math.round(238 + (248 - 238) * normalized);
            const color = `rgb(${red}, ${green}, ${blue})`;

            let size = 'small';
            let iconSize = 40;
            if (count > 100) {
                size = 'large';
                iconSize = 60;
            } else if (count > 10) {
                size = 'medium';
                iconSize = 50;
            }

            return L.divIcon({
                html: `<div style="background-color: ${color};"><span>${count}</span></div>`,
                className: 'marker-cluster marker-cluster-' + size,
                iconSize: L.point(iconSize, iconSize)
            });
        }
    });

    state.map.addLayer(state.markerCluster);
    
    // Handle cluster click to zoom to cluster extents
    state.markerCluster.on('clusterclick', function(a) {
        const cluster = a.layer;
        const bounds = cluster.getBounds();
        
        // Zoom to cluster bounds with animation
        state.map.fitBounds(bounds, {
            animate: true,
            duration: 0.8,
            padding: [30, 30],
            maxZoom: 18
        });
    });
    
    updateStatus('Map initialized', 'success');
}

// Initialize event listeners
function initializeEventListeners() {
    buildLegend();

    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        filterThings(e.target.value);
    });

    document.querySelectorAll('.legend-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const filter = chip.dataset.filter;
            setStatusFilter(state.activeStatusFilter === filter ? 'all' : filter);
        });
    });

    const healthCheckBtn = document.getElementById('healthCheckBtn');
    if (healthCheckBtn) {
        healthCheckBtn.addEventListener('click', runHealthCheck);
    }

    mountConnectionControl(document.getElementById('connectionControl'), resetAndReload);
    observeCommandBarHeight();
    initChartPanel();

    const appShell = document.querySelector('.app-shell');
    const rosterCollapse = document.getElementById('rosterCollapse');
    const rosterReopen = document.getElementById('rosterReopen');
    if (rosterCollapse && appShell) {
        rosterCollapse.addEventListener('click', () => {
            appShell.classList.add('roster-collapsed');
            setTimeout(() => state.map && state.map.invalidateSize(), 450);
        });
    }
    if (rosterReopen && appShell) {
        rosterReopen.addEventListener('click', () => {
            appShell.classList.remove('roster-collapsed');
            setTimeout(() => state.map && state.map.invalidateSize(), 450);
        });
    }

    const virtualExitBtn = document.getElementById('virtualExitBtn');
    if (virtualExitBtn) {
        virtualExitBtn.addEventListener('click', () => setShowVirtualThings(false));
    }

    document.querySelectorAll('.roster-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => setRosterView(btn.dataset.view));
    });

    const virtualThingsCheckbox = document.getElementById('virtualThingsCheckbox');
    if (virtualThingsCheckbox) {
        virtualThingsCheckbox.addEventListener('change', () => {
            setShowVirtualThings(virtualThingsCheckbox.checked);
        });
    }

    syncVirtualModeChrome();

    const zoomInBtn = document.getElementById('zoomInBtn');
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => state.map && state.map.zoomIn());
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => state.map && state.map.zoomOut());

    const zoomExtentsBtn = document.getElementById('zoomExtentsBtn');
    if (zoomExtentsBtn) zoomExtentsBtn.addEventListener('click', zoomToExtents);

    const thingMetadataClose = document.getElementById('thingMetadataClose');
    if (thingMetadataClose) {
        thingMetadataClose.addEventListener('click', () => hideThingMetadata());
    }

    const loadingErrorBtn = document.getElementById('loadingErrorBtn');
    if (loadingErrorBtn) {
        loadingErrorBtn.addEventListener('click', () => hideLoadingOverlay(true));
    }

    initMobileBottomSheet();
}

// Non-health UI colours (health tier colours come from HEALTH_TIER_MAP).
const SELECTED_COLOR = '#22d3ee';
const UNKNOWN_COLOR  = '#6b7c93';

// Resolve any status key (health tier, 'selected', or 'unknown') to a colour.
function getStatusColor(status) {
    if (status === 'selected') return SELECTED_COLOR;
    if (!status || status === 'unknown') return UNKNOWN_COLOR;
    return HEALTH_TIER_MAP[status]?.color || UNKNOWN_COLOR;
}

// Build a status-aware map marker icon
function makePinIcon(status, isSelected) {
    const color = isSelected ? SELECTED_COLOR : getStatusColor(status);
    const classes = ['rime-pin'];
    if (isSelected) classes.push('selected');
    // Only the freshest tier pulses (keeps the map calm once health is graded).
    if (status === 'fresh' && !isSelected) classes.push('pulse');
    return L.divIcon({
        className: 'custom-marker',
        html: `<div class="${classes.join(' ')}" style="position:relative;background:${color};color:${color};"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });
}

// Map "minutes since last observation" to a graded health tier.
function calculateThingHealthStatus(timeSinceLastObservationMinutes) {
    const tier = getHealthTier(timeSinceLastObservationMinutes);
    return { status: tier.key, label: tier.label, color: tier.color };
}


// Format time since last observation
function formatTimeSince(minutes) {
    if (minutes === null || minutes === undefined || Number.isNaN(minutes)) {
        return 'Never';
    }

    if (minutes < 60) {
        return `${Math.round(minutes)}m ago`;
    } else if (minutes < 1440) {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return `${hours}h ${mins}m ago`;
    } else if (minutes < 43200) {
        const days = Math.floor(minutes / 1440);
        const hours = Math.floor((minutes % 1440) / 60);
        return `${days}d ${hours}h ago`;
    } else if (minutes < 525600) {
        const months = Math.floor(minutes / 43200);
        const days = Math.floor((minutes % 43200) / 1440);
        return `${months}mo ${days}d ago`;
    } else {
        const years = Math.floor(minutes / 525600);
        const months = Math.floor((minutes % 525600) / 43200);
        return `${years}y ${months}mo ago`;
    }
}

// Update status tags on things
function updateThingStatusTags() {
    // Update roster list — skip nodes whose health is not yet known
    document.querySelectorAll('.thing-item').forEach(item => {
        const thingId = item.dataset.thingId;
        const thing = state.things[thingId];
        if (!thing || !thing.healthStatus || thing.healthStatus === 'unknown') return;
        updateThingItemStatus(item, thing.healthStatus, thing.healthLabel, thing.timeSinceLastObservation);
    });

    refreshMarkerStatusColors();
    updateStatusCounts();

    // Update metadata sidebar if open
    const metadataSidebar = document.getElementById('thingMetadataSidebar');
    if (metadataSidebar && metadataSidebar.classList.contains('open')) {
        const thingId = Object.keys(state.things).find(id => {
            const t = state.things[id];
            return t && document.getElementById('thingMetadataTitle')?.textContent === t.name;
        });
        if (thingId) {
            const thing = state.things[thingId];
            if (thing.healthStatus && thing.healthStatus !== 'unknown') {
                updateMetadataSidebarStatus(thing.healthStatus, thing.healthLabel, thing.timeSinceLastObservation);
            }
        }
    }
}

// Apply a health tier's colour scheme to a pill-style element (roster tag or
// inspector status tag).
function applyTierStyle(el, status) {
    const color = getStatusColor(status);
    el.style.background = hexToRgba(color, 0.14);
    el.style.borderColor = hexToRgba(color, 0.34);
    el.style.color = lightenHex(color, 0.35);
}

// Update thing item with status tag
function updateThingItemStatus(item, status, label, timeSince = null) {
    // Reflect status on the item's accent border via a CSS custom property
    item.style.setProperty('--status-color', getStatusColor(status));
    item.dataset.status = status;

    // Remove existing status tag
    const existingTag = item.querySelector('.thing-status-tag');
    if (existingTag) {
        existingTag.remove();
    }
    
    const thingName = item.querySelector('.thing-name');
    if (!thingName) return;
    
    // Wrap the text content if it's not already wrapped
    let nameText = thingName.querySelector('.thing-name-text');
    if (!nameText) {
        // Get the current text content
        const currentText = thingName.textContent;
        // Clear the thing-name element
        thingName.textContent = '';
        // Create a text wrapper
        nameText = document.createElement('span');
        nameText.className = 'thing-name-text';
        nameText.textContent = currentText;
        thingName.appendChild(nameText);
    }
    
    // Add new status tag
    const statusTag = document.createElement('div');
    statusTag.className = 'thing-status-tag';
    applyTierStyle(statusTag, status);
    statusTag.textContent = label;
    if (timeSince !== null) {
        statusTag.title = `Last observation: ${formatTimeSince(timeSince)}`;
    }
    
    thingName.appendChild(statusTag);
}

// Update metadata sidebar with status
function updateMetadataSidebarStatus(status, label, timeSince = null) {
    const content = document.getElementById('thingMetadataContent');
    if (!content) return;
    
    // Remove existing status section
    const existingStatus = content.querySelector('.metadata-status-section');
    if (existingStatus) {
        existingStatus.remove();
    }
    
    // Add status section at the top
    const statusSection = document.createElement('div');
    statusSection.className = 'metadata-status-section';
    const timeText = timeSince !== null ? `<div class="metadata-value" style="font-size: 0.8rem; color: var(--txt-dim); margin-top: 0.5rem;">Last observation: ${formatTimeSince(timeSince)}</div>` : '';
    statusSection.innerHTML = `
        <div class="metadata-section">
            <h3>Status</h3>
            <div class="metadata-item">
                <div class="status-tag">${label}</div>
                ${timeText}
            </div>
        </div>
    `;
    const tag = statusSection.querySelector('.status-tag');
    if (tag) applyTierStyle(tag, status);

    content.insertBefore(statusSection, content.firstChild);
}

// ── Virtual layer — terminal nodes over the faded map ────────────────
function buildVirtualNodeHtml(thingData) {
    const health = thingData.healthStatus;
    const statusLabel = (health && health !== 'unknown')
        ? (HEALTH_TIER_MAP[health]?.label || health)
        : 'no data';
    const color = (health && health !== 'unknown')
        ? (HEALTH_TIER_MAP[health]?.color || '#4ade80')
        : '#4ade80';
    return `
        <div class="virtual-node-header">
            <span class="virtual-node-prompt">&gt;</span>
            <span class="virtual-node-name" title="${thingData.name}">${thingData.name}</span>
        </div>
        <div class="virtual-node-id">id:${thingData.thingId}</div>
        <div class="virtual-node-footer">
            <span class="virtual-node-dot" style="background:${color};box-shadow:0 0 6px ${color}80;"></span>
            <span class="virtual-node-status">${statusLabel}</span>
        </div>
    `;
}

function renderVirtualLayer() {
    const layer = document.getElementById('virtualLayer');
    if (!layer) return;

    layer.innerHTML = '';
    const virtualThings = Object.values(state.things).filter(t => t.virtual);

    virtualThings.forEach((thingData, i) => {
        const node = document.createElement('div');
        node.className = 'virtual-node';
        node.dataset.thingId = thingData.thingId;
        node.style.animationDelay = `${i * 35}ms`;
        node.innerHTML = buildVirtualNodeHtml(thingData);

        node.addEventListener('click', async () => {
            document.querySelectorAll('.virtual-node').forEach(n => n.classList.remove('active'));
            node.classList.add('active');
            showThingMetadata(thingData.thingId);
            await loadDatastreamsForThing(thingData.thingId);
        });

        layer.appendChild(node);
    });
}

function updateVirtualLayerHealth() {
    if (!state.showVirtualThings) return;
    document.querySelectorAll('.virtual-node').forEach(node => {
        const thingId = node.dataset.thingId;
        const thingData = thingId ? state.things[thingId] : null;
        if (!thingData) return;
        node.innerHTML = buildVirtualNodeHtml(thingData);
        if (state.selectedThingId === thingId) {
            node.classList.add('active');
        }
        // Re-attach click handler
        node.onclick = async (e) => {
            e.stopPropagation();
            document.querySelectorAll('.virtual-node').forEach(n => n.classList.remove('active'));
            node.classList.add('active');
            showThingMetadata(thingId);
            await loadDatastreamsForThing(thingId);
        };
    });
}

function clearVirtualLayer() {
    const layer = document.getElementById('virtualLayer');
    if (layer) layer.innerHTML = '';
}

// Debounced status tag update ─────────────────────────────────────────────
// Health checks complete at ~5/batch; without batching, updateThingStatusTags
// would be called thousands of times, each doing a full DOM scan. Instead,
// we coalesce all calls within a single animation frame into one flush.
let _statusUpdatePending = false;
function scheduleStatusUpdate() {
    if (_statusUpdatePending) return;
    _statusUpdatePending = true;
    requestAnimationFrame(() => {
        _statusUpdatePending = false;
        updateThingStatusTags();
        updateVirtualLayerHealth();
    });
}

// ── Manual health check ──────────────────────────────────────────────────
// The health scan runs only when the user presses "Check health" — never on
// load, never per click, never on a timer.
function setHealthCheckButtonState(stateName) {
    const btn = document.getElementById('healthCheckBtn');
    const label = document.getElementById('healthCheckLabel');
    if (!btn || !label) return;

    btn.classList.remove('checking', 'done');
    switch (stateName) {
        case 'disabled':                 // before nodes are loaded
            btn.disabled = true;
            label.textContent = 'Check health';
            break;
        case 'ready':                    // nodes loaded, scan not yet run
            btn.disabled = false;
            label.textContent = 'Check health';
            break;
        case 'checking':                 // scan in progress
            btn.disabled = true;
            btn.classList.add('checking');
            label.textContent = 'Checking…';
            break;
        case 'done':                     // scan finished, allow manual rescan
            btn.disabled = false;
            btn.classList.add('done');
            label.textContent = 'Recheck';
            break;
    }
}

async function runHealthCheck() {
    const btn = document.getElementById('healthCheckBtn');
    if (!btn || btn.disabled) return;
    if (Object.keys(state.things).length === 0) return;

    setHealthCheckButtonState('checking');
    updateStatus('Scanning Thing health…', '');
    try {
        await fetchHealthData(state.fetchGeneration);
        setHealthCheckButtonState('done');
    } catch (err) {
        console.error('Health check failed:', err);
        updateStatus(`Health check failed: ${err.message}`, 'error');
        setHealthCheckButtonState('ready');
        
        if (!document.getElementById('loadingOverlay')?.classList.contains('status-error')) {
            if (err instanceof TypeError || err.message.startsWith('HTTP error') || err.message.includes('Failed to fetch')) {
                const msg = (err instanceof TypeError || err.message.includes('Failed to fetch')) 
                    ? 'Network or CORS error. Check endpoint and credentials.' 
                    : err.message;
                showErrorOverlay('Health Check Failed', msg);
            }
        }
    }
}

// ── Status legend ──────────────────────────────────────────────────────────
// Builds the graded health legend/filters from HEALTH_TIERS so colours and
// labels stay in sync with config.js. The "all" (total) chip is authored in
// HTML; tier chips are injected after it.
function buildLegend() {
    const legend = document.getElementById('statusLegend');
    if (!legend) return;

    // Remove any previously-built tier chips (keep the total chip).
    legend.querySelectorAll('.legend-chip[data-tier]').forEach(el => el.remove());

    [...HEALTH_TIERS, NODATA_TIER].forEach(tier => {
        const chip = document.createElement('button');
        chip.className = 'legend-chip';
        chip.dataset.filter = tier.key;
        chip.dataset.tier = tier.key;
        chip.title = `${tier.label} since last observation`;
        chip.innerHTML = `
            <span class="legend-dot" style="background:${tier.color};box-shadow:0 0 9px ${tier.color};color:${tier.color}"></span>
            <span class="legend-count" id="count-${tier.key}">0</span>
            <span class="legend-label">${tier.label}</span>
        `;
        legend.appendChild(chip);
    });
}

// ── Phase 1: place all markers on the map as fast as possible ────────────
// Uses $expand=Locations only — the lightest query the server can answer.
// Health (Phase 2) is NOT triggered automatically: once markers are placed the
// "Check health" button is enabled so the user can run the heavy scan on demand.
async function fetchThings() {
    const gen = ++state.fetchGeneration;
    const stale = () => state.fetchGeneration !== gen;

    setHealthCheckButtonState('disabled');
    updateStatus('Fetching Things…', '');
    showLoadingOverlay('Fetching Things…', 'Contacting the SensorThings Server');

    const allThings = [];
    // Large $top collapses dozens of sequential pages into one or two requests.
    // The $top is carried forward by the next-link, so we only set it here.
    let nextUrl = `${state.frostRoot}/Things?$expand=Locations&$top=${THINGS_PAGE_SIZE}`;

    try {
        while (nextUrl) {
            const response = await frostFetch(nextUrl);
            if (stale()) return;

            if (!response.ok) {
                if (response.status === 401) {
                    showErrorOverlay(
                        'Unauthorized',
                        state.frostReadAuth
                            ? 'Those credentials were rejected by this server'
                            : 'This server requires credentials — open the connection panel',
                    );
                }
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();
            if (stale()) return;

            const pageThings = data.value || [];
            const pageAdded  = [];
            const pageMarkers = [];

            for (const thing of pageThings) {
                if (stale()) return;
                try {
                    const marker = await processThing(thing);
                    if (stale()) return;
                    if (marker) {
                        pageMarkers.push(marker);
                        pageAdded.push(thing);
                        allThings.push(thing);
                    }
                } catch (err) {
                    console.error(`Error processing thing ${frostEntityId(thing)}:`, err);
                }
            }

            if (pageAdded.length > 0 && !stale()) {
                state.markerCluster.addLayers(pageMarkers);

                const thingsList = document.getElementById('thingsList');
                const fragment   = document.createDocumentFragment();
                for (const thing of pageAdded) {
                    const li = buildThingListItem(thing);
                    if (li) fragment.appendChild(li);
                }
                thingsList.appendChild(fragment);
                updateStatus(`Loading… ${allThings.length} Things`, '');
                updateLoadingOverlay(`${allThings.length} Things placed…`);
                // Keep the top-bar total in sync as Things stream in, even
                // before any health check has run.
                updateStatusCounts();
            }

            nextUrl = frostNextLink(data, nextUrl);
            if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
        }

        if (stale()) return;

        const totalThings = Object.keys(state.things).length;
        const virtualCount = Object.values(state.things).filter(t => t.virtual).length;

        if (totalThings === 0) {
            hideLoadingOverlay();
            throw new Error('No Things found at this endpoint');
        }

        if (state.showVirtualThings) {
            rebuildThingsList();
        }

        if (state.markerCluster.getLayers().length > 0) {
            state.markerCluster.refreshClusters();
            state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
                animate: true, duration: 1.0, padding: [20, 20]
            });
        }

        const virtualNote = virtualCount > 0 ? ` · ${virtualCount} virtual` : '';
        updateStatus(`Loaded ${allThings.length} on map${virtualNote} · health on demand`, 'success');
        updateStatusCounts();
        hideLoadingOverlay();

        // Health is no longer scanned automatically — it is a heavy, server-
        // taxing operation. The user triggers it explicitly via the
        // "Check health" button (see runHealthCheck). Enable it now.
        setHealthCheckButtonState('ready');

        // A server answered — drop any "could not reach ..." message.
        clearEndpointHint();

        // Deep link from the investigate page. Runs after the fetch because
        // both handlers need the Things and Datastreams to exist first.
        await applyDeepLink();

    } catch (error) {
        if (stale()) return;

        // Boot-time endpoint that nobody chose in this session and that does not
        // answer: the STA server may be stopped, or the stored endpoint may
        // belong to a different deployment. Fall back to the connect prompt.
        if (isInitialLoad) {
            const host = state.frostBase.replace(/^https?:\/\//, '');
            // A 401 is not "unreachable" — the server answered, it just wants
            // credentials. This is the common case in a fresh tab, where the
            // endpoint comes back from localStorage but credentials do not
            // (they are per-tab; see js/connection.js). Saying "could not
            // reach" there sends people to check the wrong thing.
            const unauthorized = /Status:\s*401/.test(error.message || '');
            hideLoadingOverlay(true);
            updateStatus(unauthorized ? 'Server requires credentials' : 'No server connected', 'error');
            promptForEndpoint(
                unauthorized
                    ? `${host} requires credentials — enter them below.`
                    : `Could not reach ${host} — choose a server.`,
            );
            console.error('Error fetching things:', error);
            return;
        }

        // Show overlay for network/CORS errors which throw TypeErrors, or other HTTP errors
        if (!document.getElementById('loadingOverlay')?.classList.contains('status-error')) {
            if (error instanceof TypeError || error.message.startsWith('HTTP error') || error.message.includes('Failed to fetch')) {
                const msg = (error instanceof TypeError || error.message.includes('Failed to fetch')) 
                    ? 'Network or CORS error. Check endpoint and credentials.' 
                    : error.message;
                showErrorOverlay('Connection Failed', msg);
            }
        }

        // Don't auto-hide if we just showed an error overlay
        const overlay = document.getElementById('loadingOverlay');
        if (!overlay || !overlay.classList.contains('status-error')) {
            hideLoadingOverlay();
        }
        console.error('Error fetching things:', error);
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

// ── Phase 2 (on-demand): grade every node's health ───────────────────────
// Invoked only by runHealthCheck. Fetches Datastreams with phenomenonTime
// (last observation edge) and paginates via the version-aware next-link.
// Whole phenomenonTime is selected so the same query works on STA 1.x
// (ISO string / interval) and STA 2.0 (TM_Period object).

function buildHealthDatastreamsUrl() {
    const idField = frostIdField();
    return `${state.frostRoot}/Datastreams?$select=phenomenonTime,${idField}`
        + `&$expand=Thing($select=${idField})&$top=${HEALTH_PAGE_SIZE}`;
}

function thingIdFromDatastream(datastream) {
    const expandedId = frostEntityId(datastream.Thing);
    if (expandedId != null) {
        return String(expandedId);
    }
    const link = frostNavLink(datastream, 'Thing');
    if (!link) return null;
    const match = link.match(/Things\((\d+)\)/);
    return match ? match[1] : null;
}

function lastObservationEndFromDatastream(datastream) {
    if (!datastream) return null;
    // Prefer nested / dotted legacy forms, then the full phenomenonTime value.
    const dotted = datastream['phenomenonTime/end'];
    if (dotted) {
        const date = new Date(dotted);
        if (!Number.isNaN(date.getTime())) return date;
    }
    return parsePhenomenonTime(datastream.phenomenonTime);
}

function applyHealthFromMostRecent(stored, mostRecentMs) {
    if (mostRecentMs == null) {
        stored.timeSinceLastObservation = null;
        stored.healthStatus = NODATA_TIER.key;
        stored.healthLabel  = NODATA_TIER.label;
        return;
    }
    const mins = (Date.now() - mostRecentMs) / 60000;
    const health = calculateThingHealthStatus(mins);
    stored.timeSinceLastObservation = mins;
    stored.healthStatus = health.status;
    stored.healthLabel  = health.label;
}

function mergeHealthPageDatastreams(datastreams, thingMostRecent, gen) {
    if (state.fetchGeneration !== gen) return false;

    for (const ds of (datastreams || [])) {
        if (state.fetchGeneration !== gen) return false;
        const thingId = thingIdFromDatastream(ds);
        if (!thingId || !state.things[thingId]) continue;

        const observed = lastObservationEndFromDatastream(ds);
        if (!observed) continue;

        const ms = observed.getTime();
        const prev = thingMostRecent.get(thingId);
        if (prev == null || ms > prev) {
            thingMostRecent.set(thingId, ms);
            applyHealthFromMostRecent(state.things[thingId], ms);
        }
    }
    return true;
}

async function fetchHealthData(gen) {
    const thingMostRecent = new Map();

    try {
        let nextUrl = buildHealthDatastreamsUrl();
        let pageNum = 0;

        while (nextUrl) {
            if (state.fetchGeneration !== gen) return;

            const response = await frostFetch(nextUrl);
            if (state.fetchGeneration !== gen) return;
            if (!response.ok) {
                if (response.status === 401) {
                    showErrorOverlay('Unauthorized', 'Invalid credentials for health scan');
                }
                throw new Error(`Health scan failed: HTTP ${response.status}`);
            }

            const data = await response.json();
            if (state.fetchGeneration !== gen) return;

            if (mergeHealthPageDatastreams(data.value, thingMostRecent, gen)) {
                pageNum += 1;
                updateStatus(`Scanning Thing health… page ${pageNum}`, '');
                scheduleStatusUpdate();
            }

            nextUrl = frostNextLink(data, nextUrl);
            if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
        }

        if (state.fetchGeneration !== gen) return;

        for (const [thingId, stored] of Object.entries(state.things)) {
            if (!thingMostRecent.has(thingId)) {
                applyHealthFromMostRecent(stored, null);
            }
        }
        scheduleStatusUpdate();

        if (state.fetchGeneration === gen) {
            updateStatus(`${Object.keys(state.things).length} Things · health ready`, 'success');
        }
    } catch (err) {
        if (state.fetchGeneration === gen) {
            console.error('Error fetching health data:', err);
            throw err;
        }
    }
}

// Register a Thing that has no usable Location (virtual Thing).
function registerVirtualThing(thing) {
    const thingId = frostEntityId(thing);
    if (state.things[thingId]) return;

    state.things[thingId] = {
        marker: null,
        virtual: true,
        name: thing.name,
        description: thing.description || '',
        coordinates: null,
        locationName: '',
        locationDescription: '',
        thingId,
        healthStatus: 'unknown',
        healthLabel: null,
        timeSinceLastObservation: null,
        datastreams: [],
    };

    state.thingsByName[thing.name] = {
        marker: null,
        id: thingId,
        coordinates: null,
        description: thing.description || '',
        locationDescription: '',
        virtual: true,
    };
}

// Process a single thing.
// Locations are expected to be inlined via $expand=Locations.
// Falls back to a separate fetch via the navigation link if not present.
// Things without a Location are registered as virtual (roster-only).
async function processThing(thing) {
    const thingId = frostEntityId(thing);

    let locationEntry;
    if (thing.Locations && thing.Locations.length > 0) {
        // Fast path: location was inlined by $expand
        locationEntry = thing.Locations[0];
    } else {
        const locationUrl = frostNavLink(thing, 'Locations');
        if (!locationUrl) {
            registerVirtualThing(thing);
            return null;
        }
        // Fallback: fetch from the navigation link
        const secureUrl = locationUrl.replace(/^http:/, window.location.protocol);
        const locationResponse = await frostFetch(secureUrl);
        const locationData = await locationResponse.json();
        if (!locationData.value || locationData.value.length === 0) {
            registerVirtualThing(thing);
            return null;
        }
        locationEntry = locationData.value[0];
    }

    if (!locationEntry?.location?.coordinates) {
        registerVirtualThing(thing);
        return null;
    }

    const coordinates = locationEntry.location.coordinates;
    const locationName = locationEntry.name || '';
    const locationDescription = locationEntry.description || '';
    
    // Create custom icon for marker (status colour filled in once health is known)
    const defaultIcon = makePinIcon('unknown', false);

    // GeoJSON coordinates are [longitude, latitude]; Leaflet expects [latitude, longitude]
    const latLng = [coordinates[1], coordinates[0]];
    const marker = L.marker(latLng, {
        icon: defaultIcon
    });
    
    // Store thing data — healthStatus starts as 'unknown' (not undefined) so that
    // || 'active' fallbacks elsewhere never fire before Phase 2 sets a real value.
    state.things[thingId] = {
        marker,
        virtual: false,
        name: thing.name,
        description: thing.description || '',
        coordinates: latLng,
        locationName,
        locationDescription,
        thingId,
        healthStatus: 'unknown',
        healthLabel: null,
        timeSinceLastObservation: null,
        datastreams: [],
    };
    
    state.thingsByName[thing.name] = {
        marker,
        id: thingId,
        coordinates: latLng,
        description: thing.description || '',
        locationDescription
    };
    
    state.markers[thingId] = marker;

    // Handle marker click - no popup, just open sidebar
    marker.on('click', async () => {
        highlightThingInList(thing.name);
        showThingMetadata(thingId);
        await loadDatastreamsForThing(thingId);
    });

    // Caller is responsible for adding to the cluster group (in bulk via addLayers)
    return marker;
}

// Create popup content for marker
function createPopupContent(thing) {
    let content = `<div style="min-width: 250px;">`;
    content += `<h3 style="margin: 0 0 0.5rem 0; color: #3b82f6; font-weight: 600;">${thing.name}</h3>`;
    
    if (thing.description) {
        content += `<p style="margin: 0 0 0.5rem 0; color: #6b7280; font-size: 0.875rem;">${thing.description}</p>`;
    }
    
    content += `<div id="datastreams-${frostEntityId(thing)}" style="margin-top: 0.5rem;">`;
    content += `<div style="color: #9ca3af; font-size: 0.875rem;">Loading datastreams...</div>`;
    content += `</div>`;
    content += `</div>`;
    
    return content;
}

// Load datastreams (with their latest observation) for a thing.
//
// Fetches datastreams AND their latest observation in ONE expand request.
async function loadDatastreamsForThing(thingId, gen = state.fetchGeneration) {
    if (state.fetchGeneration !== gen) return;
    const thing = state.things[thingId];
    if (!thing) return;

    // Serve from cache when datastreams already carry inline Observations.
    const cached = thing.datastreams;
    if (Array.isArray(cached) && cached.length > 0 && cached.some(ds => ds.Observations)) {
        updateThingMetadataDatastreams(thingId, cached);
        return;
    }

    try {
        // (3) One round-trip for datastreams + their single latest observation.
        const url = `${state.frostRoot}/Things(${thingId})?$expand=Datastreams($expand=Observations($top=1;$orderby=phenomenonTime%20desc))`;
        const response = await frostFetch(url);
        if (state.fetchGeneration !== gen) return;

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        if (state.fetchGeneration !== gen) return;

        const datastreams = data.Datastreams || [];
        thing.datastreams = datastreams; // cache for subsequent opens
        updateThingMetadataDatastreams(thingId, datastreams);

    } catch (error) {
        if (state.fetchGeneration !== gen) return;
        console.error(`Error fetching datastreams for thing ${thingId}:`, error);
        updateStatus(`Error loading datastreams: ${error.message}`, 'error');
    }
}

// Update popup with datastreams
async function updatePopupWithDatastreams(thingId, datastreams) {
    const thing = state.things[thingId];
    if (!thing) return;
    
    const popup = thing.marker.getPopup();
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = popup.getContent();
    
    const datastreamDiv = tempDiv.querySelector(`#datastreams-${thingId}`);
    if (!datastreamDiv) return;
    
    if (datastreams.length === 0) {
        datastreamDiv.innerHTML = `<div style="color: #9ca3af; font-size: 0.875rem;">No datastreams available</div>`;
        popup.setContent(tempDiv.innerHTML);
        if (thing.marker.isPopupOpen()) {
            thing.marker.openPopup();
        }
        return;
    }
    
    // Show loading state
    datastreamDiv.innerHTML = `<div style="color: #9ca3af; font-size: 0.875rem;">Loading datastreams...</div>`;
    popup.setContent(tempDiv.innerHTML);
    if (thing.marker.isPopupOpen()) {
        thing.marker.openPopup();
    }
    
    // Fetch latest observations for all datastreams
    const datastreamPromises = datastreams.map(async (ds) => {
        const unitSymbol = frostUnitSymbol(ds);
        try {
            const currentProtocol = window.location.protocol;
            const obsUrl = frostNavLink(ds, 'Observations') + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await frostFetch(secureObsUrl);
            const obsData = await obsResponse.json();
            const latestResult = latestObservationResult(obsData.value?.[0]?.result);
            return {
                ds,
                latestValue: latestResult ?? '-',
                unitSymbol,
                error: false
            };
        } catch (error) {
            return { 
                ds, 
                latestValue: 'Error', 
                unitSymbol,
                error: true 
            };
        }
    });
    
    const results = await Promise.all(datastreamPromises);
    
    // Build content
    let newContent = `<div style="margin-top: 0.5rem;">`;
    results.forEach(({ ds, latestValue, unitSymbol, error }) => {
        const displayName = formatDatastreamName(ds.name);
        const escapedName = ds.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const escapedDisplayName = displayName.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        newContent += `
            <div style="padding: 0.5rem; margin: 0.25rem 0; background: #f3f4f6; border-radius: 0.375rem; cursor: pointer; transition: background 0.2s;"
                 onclick="selectDatastream(${frostEntityId(ds)}, '${escapedDisplayName}')"
                 onmouseover="this.style.background='#93c5fd'"
                 onmouseout="this.style.background='#f3f4f6'">
                <div style="font-weight: 500; margin-bottom: 0.25rem;">${displayName}</div>
                <div style="font-size: 0.75rem; color: ${error ? '#ef4444' : '#6b7280'};">
                    Latest: <strong>${latestValue} ${unitSymbol}</strong>
                </div>
            </div>
        `;
    });
    newContent += `</div>`;
    
    // Update popup
    datastreamDiv.innerHTML = newContent;
    popup.setContent(tempDiv.innerHTML);
    if (thing.marker.isPopupOpen()) {
        thing.marker.openPopup();
    }
}

// Zoom to extents (fit all markers)
function zoomToExtents() {
    if (state.markerCluster && state.markerCluster.getLayers().length > 0) {
        state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
            animate: true,
            duration: 1.2,
            padding: [30, 30],
            maxZoom: 18,
        });
        updateStatus('Zoomed to show all sensors', 'success');
    } else {
        updateStatus('No sensors to zoom to', 'warning');
    }
}

function updateMarkerIcon(thingId, isSelected) {
    const marker = state.markers[thingId];
    const thing = state.things[thingId];
    if (!marker || !thing || thing.virtual) return;

    const status = thing.healthStatus || 'unknown';
    marker.setIcon(makePinIcon(status, isSelected));
}

function refreshMarkerStatusColors() {
    Object.keys(state.markers).forEach(thingId => {
        if (state.selectedThingId === thingId) return;
        updateMarkerIcon(thingId, false);
    });
}

function showThingMetadata(thingId) {
    const thing = state.things[thingId];
    if (!thing) return;

    if (!thing.virtual) {
        // Update marker icons - deselect previous, select current
        if (state.selectedThingId && state.selectedThingId !== thingId) {
            updateMarkerIcon(state.selectedThingId, false);
        }
        state.selectedThingId = thingId;
        updateMarkerIcon(thingId, true);
    } else if (state.selectedThingId) {
        updateMarkerIcon(state.selectedThingId, false);
        state.selectedThingId = null;
    }

    const sidebar = document.getElementById('thingMetadataSidebar');
    const title = document.getElementById('thingMetadataTitle');
    const content = document.getElementById('thingMetadataContent');
    const mainContent = document.querySelector('.main-content');

    title.textContent = thing.name;

    // Add class to main content to adjust chart panel
    if (mainContent) {
        mainContent.classList.add('has-metadata-sidebar');
    }
    // On mobile, collapse the roster sheet so the inspector can fill the screen
    mobileCollapseRoster();

    const locationSection = thing.virtual
        ? `
        <div class="metadata-section">
            <h3>Location</h3>
            <div class="metadata-item">
                <div class="metadata-value" style="color: #fca5a5;">Virtual Thing — no map location</div>
            </div>
        </div>`
        : `
        <div class="metadata-section">
            <h3>Location</h3>
            <div class="metadata-item">
                <div class="metadata-label">Coordinates</div>
                <div class="metadata-value">${thing.coordinates[0].toFixed(6)}, ${thing.coordinates[1].toFixed(6)}</div>
            </div>
            ${thing.locationDescription ? `
            <div class="metadata-item">
                <div class="metadata-label">Description</div>
                <div class="metadata-value">${thing.locationDescription}</div>
            </div>
            ` : ''}
        </div>`;

    // Build metadata content (status will be added by updateMetadataSidebarStatus)
    let metadataHTML = `
        ${locationSection}
        ${thing.description ? `
        <div class="metadata-section">
            <h3>Thing Details</h3>
            <div class="metadata-item">
                <div class="metadata-label">Description</div>
                <div class="metadata-value">${thing.description}</div>
            </div>
        </div>
        ` : ''}
        <div class="metadata-section">
            <h3>Datastreams</h3>
            <div class="metadata-datastreams" id="thingMetadataDatastreams">
                <div style="color: var(--gray-500); font-size: 0.875rem;">Loading datastreams...</div>
            </div>
        </div>
    `;

    content.innerHTML = metadataHTML;
    sidebar.classList.add('open');
    
    // Update status section after sidebar is open
    const healthStatus = (thing.healthStatus && thing.healthStatus !== 'unknown') ? thing.healthStatus : null;
    if (healthStatus) {
        updateMetadataSidebarStatus(healthStatus, thing.healthLabel, thing.timeSinceLastObservation);
    }
    
    // Add download button after status is added
    setTimeout(() => {
        addDownloadButton(thingId);
    }, 0);
}

// Hide thing metadata sidebar
function hideThingMetadata() {
    // Deselect marker / virtual node when sidebar is closed
    if (state.selectedThingId) {
        updateMarkerIcon(state.selectedThingId, false);
        document.querySelectorAll('.virtual-node.active').forEach(n => n.classList.remove('active'));
        state.selectedThingId = null;
    }
    
    const sidebar = document.getElementById('thingMetadataSidebar');
    const mainContent = document.querySelector('.main-content');
    
    sidebar.classList.remove('open');
    
    // Remove class from main content to restore chart panel
    if (mainContent) {
        mainContent.classList.remove('has-metadata-sidebar');
    }
}

// Render datastreams in the inspector sidebar.
// Reads the latest reading straight from each datastream's inlined Observation
// (provided by loadDatastreamsForThing's expand query) — no per-datastream
// network calls.
function updateThingMetadataDatastreams(thingId, datastreams) {
    const datastreamsDiv = document.getElementById('thingMetadataDatastreams');
    if (!datastreamsDiv) return;

    // Track for the chart panel's next/prev datastream navigation.
    state.currentThingDatastreams = datastreams || [];

    if (!datastreams || datastreams.length === 0) {
        datastreamsDiv.innerHTML = '<div style="color: var(--txt-mute); font-size: 0.85rem;">No datastreams available</div>';
        return;
    }

    datastreamsDiv.innerHTML = '';
    const fragment = document.createDocumentFragment();

    datastreams.forEach((ds) => {
        const unitSymbol = frostUnitSymbol(ds);
        const obs = Array.isArray(ds.Observations) ? ds.Observations[0] : null;
        const latestResult = obs ? latestObservationResult(obs.result) : null;
        const hasValue = latestResult !== null && latestResult !== undefined;
        const latestText = hasValue
            ? formatLatestObservationResult(obs.result, unitSymbol)
            : '-';

        // Relative time of the latest observation (handles interval times).
        const obsDate = obs ? parsePhenomenonTime(obs.phenomenonTime) : null;
        const metaLeft = obsDate
            ? formatTimeSince((Date.now() - obsDate.getTime()) / 60000)
            : 'Latest reading';

        const displayName = formatDatastreamName(ds.name);
        const dsItem = document.createElement('div');
        dsItem.className = 'metadata-datastream-item';
        dsItem.innerHTML = `
            <div class="metadata-datastream-name">${displayName}</div>
            <div class="metadata-datastream-meta">
                <span>${metaLeft}</span>
                <span class="ds-latest">${latestText}</span>
            </div>
        `;
        dsItem.addEventListener('click', () => {
            selectDatastream(frostEntityId(ds), displayName);
        });
        fragment.appendChild(dsItem);
    });

    datastreamsDiv.appendChild(fragment);
    updateDatastreamNavigation();
}

// Build a simple phenomenonTime filter for FROST $filter.
function buildPhenomenonTimeFilter(startDate, endDate) {
    const filters = [];
    if (startDate) filters.push(`phenomenonTime ge ${startDate.toISOString()}`);
    if (endDate) filters.push(`phenomenonTime le ${endDate.toISOString()}`);
    return filters.length > 0 ? filters.join(' and ') : null;
}

function buildObservationsUrl(datastreamId, startDate, endDate) {
    const params = new URLSearchParams();
    params.set('$select', 'phenomenonTime,resultTime,result');
    params.set('$orderby', `phenomenonTime asc,${frostIdField()} asc`);
    params.set('$top', String(DOWNLOAD_PAGE_SIZE));
    const filter = buildPhenomenonTimeFilter(startDate, endDate);
    if (filter) params.set('$filter', filter);
    return `${state.frostRoot}/Datastreams(${datastreamId})/Observations?${params.toString()}`;
}

const OBSERVATIONS_CSV_HEADER = 'phenomenonTime,resultTime,result';

function escapeCsvField(value) {
    if (value === null || value === undefined) return '';
    const stringValue = String(value);
    if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
        return `"${stringValue.replace(/"/g, '""')}"`;
    }
    return stringValue;
}

async function fetchAllDatastreamsForThing(thingId) {
    const datastreams = [];
    let nextUrl = `${state.frostRoot}/Things(${thingId})/Datastreams?$top=${DOWNLOAD_PAGE_SIZE}`;

    while (nextUrl) {
        const response = await frostFetch(nextUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        const page = data.value || [];
        if (page.length === 0) break;

        datastreams.push(...page);
        nextUrl = frostNextLink(data, nextUrl);
        if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
    }

    return datastreams;
}

async function fetchAllObservationsCsvRaw(datastreamId, startDate, endDate, onProgress = null) {
    const rows = [];
    let nextUrl = buildObservationsUrl(datastreamId, startDate, endDate);
    const maxRetries = 3;

    while (nextUrl) {
        let lastError;
        let data = null;

        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                const response = await frostFetch(nextUrl);
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                data = await response.json();
                break;
            } catch (error) {
                lastError = error;
                if (attempt < maxRetries - 1) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
        }

        if (!data) throw lastError;

        for (const obs of data.value || []) {
            rows.push(...observationToCsvRows(obs));
        }
        if (onProgress) onProgress(rows.length);

        nextUrl = frostNextLink(data, nextUrl);
        if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
    }

    return { header: OBSERVATIONS_CSV_HEADER, rows };
}

const DOWNLOAD_META_HEADERS = [
    'datastreamName',
    'unitOfMeasurement',
];

function buildMergedCsv(sections) {
    const active = sections.filter(section => section.rows.length > 0);
    if (active.length === 0) return '';

    const obsHeader = active[0].header;
    const lines = [[...DOWNLOAD_META_HEADERS, obsHeader].join(',')];

    for (const section of active) {
        const prefix = DOWNLOAD_META_HEADERS
            .map(header => escapeCsvField(section.meta[header]))
            .join(',');
        for (const row of section.rows) {
            lines.push(`${prefix},${row}`);
        }
    }

    return lines.join('\n');
}

function buildDatastreamCsv(section) {
    const lines = [[...DOWNLOAD_META_HEADERS, section.header].join(',')];
    const prefix = DOWNLOAD_META_HEADERS
        .map(header => escapeCsvField(section.meta[header]))
        .join(',');

    for (const row of section.rows) {
        lines.push(`${prefix},${row}`);
    }

    return lines.join('\n');
}

function sanitizeDownloadFilename(name) {
    return name.replace(/[^a-z0-9._-]+/gi, '_').replace(/_+/g, '_').replace(/^_|_$/g, '') || 'data';
}

function buildDownloadBaseName(thing) {
    const parts = [thing.name, thing.locationName].filter(Boolean);
    return sanitizeDownloadFilename(parts.join('_'));
}

function triggerFileDownload(content, filename, mimeType = 'text/csv;charset=utf-8;') {
    const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// Store-only ZIP for bundling one CSV per datastream (avoids browser multi-download blocking).
const CRC32_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
        let crc = i;
        for (let j = 0; j < 8; j++) {
            crc = (crc & 1) ? (0xEDB88320 ^ (crc >>> 1)) : (crc >>> 1);
        }
        table[i] = crc >>> 0;
    }
    return table;
})();

function crc32(bytes) {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) {
        crc = CRC32_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
}

function writeUint32LE(view, offset, value) {
    view.setUint32(offset, value, true);
}

function writeUint16LE(view, offset, value) {
    view.setUint16(offset, value, true);
}

function createZipArchive(files) {
    const encoder = new TextEncoder();
    const parts = [];
    const central = [];
    let offset = 0;

    for (const file of files) {
        const nameBytes = encoder.encode(file.name);
        const dataBytes = encoder.encode(file.content);
        const checksum = crc32(dataBytes);

        const localHeader = new Uint8Array(30 + nameBytes.length);
        const localView = new DataView(localHeader.buffer);
        writeUint32LE(localView, 0, 0x04034b50);
        writeUint16LE(localView, 4, 20);
        writeUint16LE(localView, 6, 0);
        writeUint16LE(localView, 8, 0);
        writeUint16LE(localView, 10, 0);
        writeUint16LE(localView, 12, 0);
        writeUint32LE(localView, 14, checksum);
        writeUint32LE(localView, 18, dataBytes.length);
        writeUint32LE(localView, 22, dataBytes.length);
        writeUint16LE(localView, 26, nameBytes.length);
        writeUint16LE(localView, 28, 0);
        localHeader.set(nameBytes, 30);

        parts.push(localHeader, dataBytes);

        const centralHeader = new Uint8Array(46 + nameBytes.length);
        const centralView = new DataView(centralHeader.buffer);
        writeUint32LE(centralView, 0, 0x02014b50);
        writeUint16LE(centralView, 4, 20);
        writeUint16LE(centralView, 6, 20);
        writeUint16LE(centralView, 8, 0);
        writeUint16LE(centralView, 10, 0);
        writeUint16LE(centralView, 12, 0);
        writeUint16LE(centralView, 14, 0);
        writeUint32LE(centralView, 16, checksum);
        writeUint32LE(centralView, 20, dataBytes.length);
        writeUint32LE(centralView, 24, dataBytes.length);
        writeUint16LE(centralView, 28, nameBytes.length);
        writeUint16LE(centralView, 30, 0);
        writeUint16LE(centralView, 32, 0);
        writeUint16LE(centralView, 34, 0);
        writeUint16LE(centralView, 36, 0);
        writeUint32LE(centralView, 38, 0);
        writeUint32LE(centralView, 42, offset);
        centralHeader.set(nameBytes, 46);
        central.push(centralHeader);

        offset += localHeader.length + dataBytes.length;
    }

    const centralSize = central.reduce((sum, part) => sum + part.length, 0);
    const endRecord = new Uint8Array(22);
    const endView = new DataView(endRecord.buffer);
    writeUint32LE(endView, 0, 0x06054b50);
    writeUint16LE(endView, 4, 0);
    writeUint16LE(endView, 6, 0);
    writeUint16LE(endView, 8, files.length);
    writeUint16LE(endView, 10, files.length);
    writeUint32LE(endView, 12, centralSize);
    writeUint32LE(endView, 16, offset);
    writeUint16LE(endView, 20, 0);

    return new Blob([...parts, ...central, endRecord], { type: 'application/zip' });
}

function setDownloadProgress(message) {
    const statusEl = document.getElementById('downloadStatus');
    const textEl = document.getElementById('downloadStatusText');
    if (!statusEl || !textEl) return;
    statusEl.hidden = false;
    textEl.textContent = message;
}

function clearDownloadProgress() {
    const statusEl = document.getElementById('downloadStatus');
    if (statusEl) statusEl.hidden = true;
}

function setDownloadBusy(busy, message = '') {
    const downloadBtn = document.getElementById('downloadThingBtn');
    const startDateInput = document.getElementById('downloadStartDate');
    const endDateInput = document.getElementById('downloadEndDate');
    const optionRadios = document.querySelectorAll('.download-option-radio');
    const layoutRadios = document.querySelectorAll('.download-layout-radio');

    if (downloadBtn) downloadBtn.disabled = busy;
    if (startDateInput) startDateInput.disabled = busy;
    if (endDateInput) endDateInput.disabled = busy;
    optionRadios.forEach(radio => { radio.disabled = busy; });
    layoutRadios.forEach(radio => { radio.disabled = busy; });

    if (busy) {
        setDownloadProgress(message);
    } else {
        clearDownloadProgress();
    }
}

// Download all data for a Thing
async function downloadThingData(thingId, startDate = null, endDate = null, layout = 'merged') {
    const thing = state.things[thingId];
    if (!thing) {
        updateStatus('Thing not found', 'error');
        return;
    }
    
    // Validate dates
    if (startDate && endDate && startDate > endDate) {
        updateStatus('Start date must be before end date', 'error');
        return;
    }
    
    setDownloadBusy(true, 'Preparing download from server…');
    updateStatus('Preparing download from server…', '');

    try {
        const datastreams = await fetchAllDatastreamsForThing(thingId);

        if (datastreams.length === 0) {
            updateStatus('No datastreams found for this thing', 'warning');
            return;
        }

        const dateRangeText = startDate && endDate
            ? ` (${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]})`
            : '';
        const sections = [];
        let totalObservations = 0;
        let datastreamsWithData = 0;
        const downloadBaseName = buildDownloadBaseName(thing);

        for (let i = 0; i < datastreams.length; i++) {
            const ds = datastreams[i];
            const dsName = formatDatastreamName(ds.name);
            const unitSymbol = frostUnitSymbol(ds);
            const progress = `Preparing data (${i + 1}/${datastreams.length}): ${dsName}…`;

            setDownloadProgress(`${progress} Large datasets may take a moment.`);
            updateStatus(`${progress}${dateRangeText}`, '');

            try {
                const frostCsv = await fetchAllObservationsCsvRaw(
                    frostEntityId(ds),
                    startDate,
                    endDate,
                    (fetched) => {
                        const detail = `${progress} ${fetched.toLocaleString()} observations fetched…`;
                        setDownloadProgress(`${detail} Large datasets may take a moment.`);
                        updateStatus(`${detail}${dateRangeText}`, '');
                    },
                );

                if (frostCsv.rows.length === 0) continue;

                totalObservations += frostCsv.rows.length;
                datastreamsWithData += 1;
                sections.push({
                    header: frostCsv.header,
                    rows: frostCsv.rows,
                    meta: {
                        datastreamName: ds.name,
                        unitOfMeasurement: unitSymbol,
                    },
                });
            } catch (error) {
                console.error(`Error fetching observations for ${dsName}:`, error);
                updateStatus(`Error fetching ${dsName}: ${error.message}`, 'error');
            }
        }

        if (sections.length === 0) {
            const rangeText = startDate && endDate
                ? ' for selected date range'
                : '';
            updateStatus(`No observations found to download${rangeText}`, 'warning');
            return;
        }

        const dateSuffix = startDate && endDate
            ? `_${startDate.toISOString().split('T')[0]}_to_${endDate.toISOString().split('T')[0]}`
            : '';

        if (layout === 'separate') {
            setDownloadProgress('Building ZIP archive…');
            updateStatus('Building ZIP archive…', '');

            const zipFiles = sections.map((section) => ({
                name: `${downloadBaseName}_${sanitizeDownloadFilename(section.meta.datastreamName)}${dateSuffix}.csv`,
                content: buildDatastreamCsv(section),
            }));
            const zipBlob = createZipArchive(zipFiles);
            triggerFileDownload(
                zipBlob,
                `${downloadBaseName}_datastreams${dateSuffix}.zip`,
                'application/zip',
            );
        } else {
            setDownloadProgress('Building CSV file…');
            updateStatus('Building CSV file…', '');

            const csv = buildMergedCsv(sections);
            triggerFileDownload(csv, `${downloadBaseName}_data${dateSuffix}.csv`);
        }

        updateStatus(
            `Downloaded ${totalObservations.toLocaleString()} observations from ${datastreamsWithData} datastream(s)`,
            'success',
        );

    } catch (error) {
        console.error('Error downloading thing data:', error);
        updateStatus(`Download error: ${error.message}`, 'error');
    } finally {
        setDownloadBusy(false);
    }
}

// Add download button and date picker to metadata sidebar
function addDownloadButton(thingId) {
    const content = document.getElementById('thingMetadataContent');
    if (!content) return;
    
    // Remove existing download section if any
    const existingSection = content.querySelector('.download-section');
    if (existingSection) {
        existingSection.remove();
    }
    
    // Set default dates (last 30 days)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);
    
    const dateFormat = (date) => {
        return date.toISOString().split('T')[0];
    };
    
    // Create download section
    const downloadSection = document.createElement('div');
    downloadSection.className = 'download-section';
    downloadSection.innerHTML = `
        <div class="metadata-section">
            <h3>Download Data</h3>
            <div class="download-option-group">
                <label class="download-option-label">
                    <input type="radio" name="downloadOption" value="range" checked class="download-option-radio">
                    <span>Date Range</span>
                </label>
                <label class="download-option-label">
                    <input type="radio" name="downloadOption" value="all" class="download-option-radio">
                    <span>All Data</span>
                </label>
            </div>
            <div class="download-date-range" id="downloadDateRange">
                <div class="date-input-group">
                    <label for="downloadStartDate">Start Date</label>
                    <input type="date" id="downloadStartDate" value="${dateFormat(startDate)}" class="date-input">
                </div>
                <div class="date-input-group">
                    <label for="downloadEndDate">End Date</label>
                    <input type="date" id="downloadEndDate" value="${dateFormat(endDate)}" class="date-input">
                </div>
            </div>
            <div class="download-option-group">
                <label class="download-option-label">
                    <input type="radio" name="downloadLayout" value="merged" checked class="download-layout-radio">
                    <span>Single CSV</span>
                </label>
                <label class="download-option-label">
                    <input type="radio" name="downloadLayout" value="separate" class="download-layout-radio">
                    <span>ZIP per datastream</span>
                </label>
            </div>
            <div class="download-status" id="downloadStatus" hidden>
                <span class="download-status-spinner" aria-hidden="true"></span>
                <span class="download-status-text" id="downloadStatusText"></span>
            </div>
            <button class="download-thing-btn" id="downloadThingBtn">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" style="margin-right: 0.5rem;">
                    <path d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"/>
                </svg>
                Download Data
            </button>
        </div>
    `;
    
    // Insert after status section or at the beginning
    const statusSection = content.querySelector('.metadata-status-section');
    if (statusSection && statusSection.nextSibling) {
        content.insertBefore(downloadSection, statusSection.nextSibling);
    } else {
        content.insertBefore(downloadSection, content.firstChild);
    }
    
    // Add event listeners
    const downloadBtn = document.getElementById('downloadThingBtn');
    const startDateInput = document.getElementById('downloadStartDate');
    const endDateInput = document.getElementById('downloadEndDate');
    const dateRangeDiv = document.getElementById('downloadDateRange');
    const optionRadios = document.querySelectorAll('.download-option-radio');
    
    // Toggle date range visibility based on option
    const toggleDateRange = () => {
        const selectedOption = document.querySelector('.download-option-radio:checked').value;
        dateRangeDiv.style.display = selectedOption === 'range' ? 'grid' : 'none';
    };
    
    optionRadios.forEach(radio => {
        radio.addEventListener('change', toggleDateRange);
    });
    
    // Validate dates on change (only if date range is selected)
    const validateDates = () => {
        const selectedOption = document.querySelector('.download-option-radio:checked').value;
        if (selectedOption === 'all') {
            downloadBtn.disabled = false;
            return;
        }
        
        const startDate = new Date(startDateInput.value);
        const endDate = new Date(endDateInput.value);
        
        if (startDate > endDate) {
            downloadBtn.disabled = true;
            return;
        }
        
        downloadBtn.disabled = false;
    };
    
    startDateInput.addEventListener('change', validateDates);
    endDateInput.addEventListener('change', validateDates);
    
    downloadBtn.addEventListener('click', async () => {
        const selectedOption = document.querySelector('.download-option-radio:checked').value;
        const layout = document.querySelector('.download-layout-radio:checked')?.value || 'merged';

        if (selectedOption === 'all') {
            await downloadThingData(thingId, null, null, layout);
        } else {
            const startDate = new Date(startDateInput.value);
            const endDate = new Date(endDateInput.value);
            endDate.setHours(23, 59, 59, 999); // Include full end date
            await downloadThingData(thingId, startDate, endDate, layout);
        }
    });
    
    // Initial setup
    toggleDateRange();
    validateDates();
}

// Make selectDatastream available globally for onclick handlers
window.selectDatastream = selectDatastream;
