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

// Global state
const state = {
    things: {},
    thingsByName: {},
    markers: {},
    currentDatastream: null,
    currentChart: null,
    currentLimit: 1000,
    map: null,
    markerCluster: null,
    maxClusterSize: 1, // Track maximum cluster size for color normalization
    currentThingDatastreams: [], // Track datastreams for current thing
    currentDatastreamIndex: -1, // Track current datastream index for cycling
    selectedThingId: null // Track currently selected thing for marker highlighting
};

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();
    initializeEventListeners();
    fetchThings();
});

// Initialize Leaflet map
function initializeMap() {
    state.map = L.map('map', {
        zoomAnimation: true,
        zoomAnimationThreshold: 4, // Animate zoom if difference is less than 4 levels
        fadeAnimation: true,
        markerZoomAnimation: true,
        zoomControl: true,
        doubleClickZoom: true,
        scrollWheelZoom: true
    }).setView([52.00482, 4.37034], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        fadeAnimation: true,
        updateWhenZooming: true
    }).addTo(state.map);
    
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
            
            // Update max cluster size if this cluster is larger
            if (count > state.maxClusterSize) {
                state.maxClusterSize = count;
            }
            
            // Calculate color based on count (red for few, green for many)
            // Use logarithmic scale for better color distribution
            // Normalize count to 0-1 range using log scale
            const maxCount = Math.max(state.maxClusterSize, 10);
            const normalized = Math.min(Math.log(count + 1) / Math.log(maxCount + 1), 1);
            
            // Interpolate between red (few) and green (many)
            // Red: rgb(239, 68, 68), Green: rgb(34, 197, 94)
            const red = Math.round(239 - (239 - 34) * normalized);
            const green = Math.round(68 + (197 - 68) * normalized);
            const blue = Math.round(68 + (94 - 68) * normalized);
            
            const color = `rgb(${red}, ${green}, ${blue})`;
            
            // Determine size based on count
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
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        filterThings(e.target.value);
    });

    // Chart panel toggle - only on header title area, not buttons
    const chartPanelTitle = document.querySelector('.chart-panel-title > div:not(.chart-panel-nav)');
    if (chartPanelTitle) {
        chartPanelTitle.addEventListener('click', (e) => {
            // Only toggle if clicking on the title text area, not on buttons
            if (!e.target.closest('button') && !e.target.closest('.chart-panel-nav')) {
                toggleChartPanel();
            }
        });
    }

    // Chart panel toggle button (separate handler)
    const chartPanelToggle = document.getElementById('chartPanelToggle');
    if (chartPanelToggle) {
        chartPanelToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleChartPanel();
        });
    }

    // Chart limit buttons
    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const limit = parseInt(e.target.dataset.limit || e.target.closest('button').dataset.limit);
            setChartLimit(limit);
        });
    });

    // Zoom extents button
    const zoomExtentsBtn = document.getElementById('zoomExtentsBtn');
    if (zoomExtentsBtn) {
        zoomExtentsBtn.addEventListener('click', zoomToExtents);
    }

    // Thing metadata sidebar close button
    const thingMetadataClose = document.getElementById('thingMetadataClose');
    if (thingMetadataClose) {
        thingMetadataClose.addEventListener('click', () => {
            hideThingMetadata();
        });
    }

    // Chart next datastream button
    const chartNextDatastreamBtn = document.getElementById('chartNextDatastreamBtn');
    if (chartNextDatastreamBtn) {
        chartNextDatastreamBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            navigateToDatastream(1);
        });
    }
}

// Update status message
function updateStatus(message, type = '') {
    const statusEl = document.getElementById('statusMessage');
    statusEl.textContent = message;
    statusEl.className = `status-message ${type}`;
}

// Calculate thing health status asynchronously
async function calculateThingHealthStatusAsync(thingId, datastreams) {
    const thing = state.things[thingId];
    if (!thing || !datastreams || datastreams.length === 0) {
        thing.healthStatus = 'active';
        thing.timeSinceLastObservation = null;
        updateThingStatusTags();
        return;
    }
    
    // Fetch last observations for all datastreams in parallel
    const currentProtocol = window.location.protocol;
    const observationPromises = datastreams.map(async (ds) => {
        try {
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await fetch(secureObsUrl);
            const obsData = await obsResponse.json();
            
            if (obsData.value && obsData.value.length > 0) {
                return new Date(obsData.value[0].phenomenonTime);
            }
            return null;
        } catch (error) {
            console.warn(`Error fetching last observation for datastream ${ds['@iot.id']}:`, error);
            return null;
        }
    });
    
    const observationTimes = await Promise.all(observationPromises);
    
    // Find the most recent observation
    const validTimes = observationTimes.filter(t => t !== null);
    let mostRecentTime = null;
    
    if (validTimes.length > 0) {
        mostRecentTime = new Date(Math.max(...validTimes.map(t => t.getTime())));
    }
    
    // Calculate time since last observation
    if (mostRecentTime) {
        const now = new Date();
        const timeDiffMinutes = (now - mostRecentTime) / (1000 * 60);
        thing.timeSinceLastObservation = timeDiffMinutes;
        const healthInfo = calculateThingHealthStatus(timeDiffMinutes);
        thing.healthStatus = healthInfo.status;
        thing.healthLabel = healthInfo.label;
    } else {
        // No observations found
        thing.timeSinceLastObservation = null;
        thing.healthStatus = 'down';
        thing.healthLabel = 'No data';
    }
    
    // Update status tags
    updateThingStatusTags();
}

// Calculate thing health status based on time since last observation
function calculateThingHealthStatus(timeSinceLastObservationMinutes) {
    if (timeSinceLastObservationMinutes === null || timeSinceLastObservationMinutes === undefined) {
        return { status: 'down', label: 'No data' }; // No observations
    }
    
    if (timeSinceLastObservationMinutes < 60) {
        return { status: 'active', label: '<60mins' };
    } else if (timeSinceLastObservationMinutes < 120) {
        return { status: 'warning', label: '<120mins' };
    } else {
        return { status: 'down', label: '>120mins' };
    }
}

// Format time since last observation
function formatTimeSince(minutes) {
    if (minutes === null || minutes === undefined) {
        return 'Never';
    }
    
    if (minutes < 60) {
        return `${Math.round(minutes)}m ago`;
    } else if (minutes < 1440) {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return `${hours}h ${mins}m ago`;
    } else {
        const days = Math.floor(minutes / 1440);
        const hours = Math.floor((minutes % 1440) / 60);
        return `${days}d ${hours}h ago`;
    }
}

// Update status tags on things
function updateThingStatusTags() {
    // Update sidebar list
    document.querySelectorAll('.thing-item').forEach(item => {
        const thingId = item.dataset.thingId;
        const thing = state.things[thingId];
        if (!thing) return;
        
        // Get status from thing's last observation time
        const status = thing.healthStatus || 'active';
        const label = thing.healthLabel || '<60mins';
        const timeSince = thing.timeSinceLastObservation;
        updateThingItemStatus(item, status, label, timeSince);
    });
    
    // Update metadata sidebar if open
    const metadataSidebar = document.getElementById('thingMetadataSidebar');
    if (metadataSidebar && metadataSidebar.classList.contains('open')) {
        const thingId = Object.keys(state.things).find(id => {
            const thing = state.things[id];
            return thing && document.getElementById('thingMetadataTitle')?.textContent === thing.name;
        });
        if (thingId) {
            const thing = state.things[thingId];
            const status = thing.healthStatus || 'active';
            const label = thing.healthLabel || '<60mins';
            const timeSince = thing.timeSinceLastObservation;
            updateMetadataSidebarStatus(status, label, timeSince);
        }
    }
}

// Update thing item with status tag
function updateThingItemStatus(item, status, label, timeSince = null) {
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
    statusTag.className = `thing-status-tag thing-status-${status}`;
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
    const timeText = timeSince !== null ? `<div class="metadata-value" style="font-size: 0.875rem; color: var(--gray-600); margin-top: 0.5rem;">Last observation: ${formatTimeSince(timeSince)}</div>` : '';
    statusSection.innerHTML = `
        <div class="metadata-section">
            <h3>Status</h3>
            <div class="metadata-item">
                <div class="status-tag status-tag-${status}">${label}</div>
                ${timeText}
            </div>
        </div>
    `;
    
    content.insertBefore(statusSection, content.firstChild);
}

// Fetch things from FROST API
async function fetchThings() {
    updateStatus('Fetching things...', '');
    
    try {
        const response = await fetch('../FROST-Server/v1.1/Things');
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const thingData = await response.json();
        
        if (thingData.value && thingData.value.length > 0) {
            for (const thing of thingData.value) {
                try {
                    await processThing(thing);
                } catch (error) {
                    console.error(`Error processing thing ${thing['@iot.id']}:`, error);
                }
            }
            
            // Adjust map view to show all markers using cluster group bounds
            if (Object.keys(state.markers).length > 0 && state.markerCluster.getLayers().length > 0) {
                // Recalculate max cluster size by checking all clusters
                state.maxClusterSize = 1;
                state.markerCluster.eachLayer(function(marker) {
                    // This will trigger iconCreateFunction which updates maxClusterSize
                });
                // Refresh clusters to update colors with accurate max count
                state.markerCluster.refreshClusters();
                state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
                    animate: true,
                    duration: 1.0, // 1 second smooth animation
                    padding: [20, 20] // Padding in pixels
                });
            }
            
            updateStatus(`Loaded ${Object.keys(state.things).length} things`, 'success');
            populateThingsList(thingData.value);
            
            // Load datastreams for all things to calculate health status (in parallel)
            const datastreamPromises = thingData.value.map(thing => loadDatastreamsForThing(thing['@iot.id']));
            await Promise.all(datastreamPromises);
        } else {
            throw new Error('No things found in API response');
        }
    } catch (error) {
        console.error("Error fetching things:", error);
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

// Process a single thing
async function processThing(thing) {
    const thingId = thing['@iot.id'];
    const currentProtocol = window.location.protocol;
    
    // Fetch location
    const locationUrl = thing['Locations@iot.navigationLink'];
    const secureUrl = locationUrl.replace(/^http:/, currentProtocol);
    const locationResponse = await fetch(secureUrl);
    const locationData = await locationResponse.json();
    
    if (!locationData.value || locationData.value.length === 0) {
        return;
    }
    
    const coordinates = locationData.value[0].location.coordinates;
    const locationDescription = locationData.value[0].description || '';
    
    // Create custom icon for marker
    const defaultIcon = L.divIcon({
        className: 'custom-marker',
        html: '<div style="background-color: #3b82f6; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    
    // Create marker (coordinates are [lat, lon] from FROST API)
    const marker = L.marker([coordinates[0], coordinates[1]], {
        icon: defaultIcon
    });
    
    // Add marker to cluster group instead of directly to map
    state.markerCluster.addLayer(marker);
    
    // Store thing data
    state.things[thingId] = {
        marker,
        name: thing.name,
        description: thing.description || '',
        coordinates: [coordinates[0], coordinates[1]],
        locationDescription,
        thingId
    };
    
    state.thingsByName[thing.name] = {
        marker,
        id: thingId,
        coordinates: [coordinates[0], coordinates[1]],
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
}

// Create popup content for marker
function createPopupContent(thing) {
    let content = `<div style="min-width: 250px;">`;
    content += `<h3 style="margin: 0 0 0.5rem 0; color: #3b82f6; font-weight: 600;">${thing.name}</h3>`;
    
    if (thing.description) {
        content += `<p style="margin: 0 0 0.5rem 0; color: #6b7280; font-size: 0.875rem;">${thing.description}</p>`;
    }
    
    content += `<div id="datastreams-${thing['@iot.id']}" style="margin-top: 0.5rem;">`;
    content += `<div style="color: #9ca3af; font-size: 0.875rem;">Loading datastreams...</div>`;
    content += `</div>`;
    content += `</div>`;
    
    return content;
}

// Load datastreams for a thing
async function loadDatastreamsForThing(thingId) {
    const thing = state.things[thingId];
    if (!thing) return;
    
    try {
        const response = await fetch(`../FROST-Server/v1.1/Things(${thingId})/Datastreams`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const datastreamData = await response.json();
        
        // Store datastreams for navigation
        state.currentThingDatastreams = datastreamData.value;
        
        // Calculate time since last observation for this thing (async, don't block)
        calculateThingHealthStatusAsync(thingId, datastreamData.value);
        
        // Update metadata sidebar if open
        updateThingMetadataDatastreams(thingId, datastreamData.value);
        
    } catch (error) {
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
        const unitSymbol = ds.unitOfMeasurement?.symbol || '';
        try {
            const currentProtocol = window.location.protocol;
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await fetch(secureObsUrl);
            const obsData = await obsResponse.json();
            return { 
                ds, 
                latestValue: obsData.value?.[0]?.result ?? '-', 
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
                 onclick="selectDatastream(${ds['@iot.id']}, '${escapedDisplayName}')"
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


// Populate things list in sidebar
function populateThingsList(things) {
    const thingsList = document.getElementById('thingsList');
    thingsList.innerHTML = '';

    things.forEach(thing => {
        const thingData = state.things[thing['@iot.id']];
        if (!thingData) return;
        
        const li = document.createElement('li');
        li.className = 'thing-item';
        li.dataset.thingId = thing['@iot.id'];
        li.dataset.thingName = thing.name;
        
        li.innerHTML = `
            <div class="thing-name"><span class="thing-name-text">${thing.name}</span></div>
        `;
        
        li.addEventListener('click', async () => {
            state.map.setView(thingData.coordinates, 15, {
                animate: true,
                duration: 0.8, // 0.8 second smooth animation
                easeLinearity: 0.25
            });
                highlightThingInList(thing.name);
            showThingMetadata(thing['@iot.id']);
            await loadDatastreamsForThing(thing['@iot.id']);
        });
        
        thingsList.appendChild(li);
    });
}

// Highlight thing in list
function highlightThingInList(thingName) {
    document.querySelectorAll('.thing-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const thingElement = document.querySelector(`[data-thing-name="${thingName.replace(/"/g, '\\"')}"]`);
    if (thingElement) {
        thingElement.classList.add('active');
        thingElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// Filter things by search
function filterThings(query) {
    const things = document.querySelectorAll('.thing-item');
    const lowerQuery = query.toLowerCase();
    
    things.forEach(thing => {
        const name = thing.dataset.thingName.toLowerCase();
        if (name.includes(lowerQuery)) {
            thing.style.display = '';
        } else {
            thing.style.display = 'none';
        }
    });
}

// Select datastream and load chart
async function selectDatastream(datastreamId, datastreamName) {
    state.currentDatastream = datastreamId;
    
    // Find current datastream index
    state.currentDatastreamIndex = state.currentThingDatastreams.findIndex(ds => ds['@iot.id'] === datastreamId);
    
    // Update UI
    document.querySelectorAll('.datastream-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const activeItem = document.querySelector(`[data-datastream-id="${datastreamId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
    
    // Update chart panel
    document.getElementById('chartTitle').textContent = datastreamName;
    document.getElementById('chartSubtitle').textContent = `Datastream ID: ${datastreamId}`;
    
    // Expand chart panel
    const chartPanel = document.getElementById('chartPanel');
    if (!chartPanel.classList.contains('expanded')) {
        chartPanel.classList.add('expanded');
    }
    
    // Close metadata sidebar
    hideThingMetadata();
    
    // Update navigation arrows visibility
    updateDatastreamNavigation();
    
    // Load chart data
    await loadChartData(datastreamId);
}

// Load chart data
async function loadChartData(datastreamId) {
    updateStatus('Loading chart data...', '');
    
    const chartPanelContent = document.getElementById('chartPanelContent');
    chartPanelContent.innerHTML = '<div class="no-data-message"><div class="loading"></div> Loading data...</div>';
    
    try {
        // Fetch datastream info
        const dsResponse = await fetch(`../FROST-Server/v1.1/Datastreams(${datastreamId})`);
        if (!dsResponse.ok) throw new Error(`HTTP error! Status: ${dsResponse.status}`);
        
        const dsData = await dsResponse.json();
        const unitSymbol = dsData.unitOfMeasurement?.symbol || '';
        const datastreamName = formatDatastreamName(dsData.name || 'Unknown');
        const datastreamDescription = dsData.description || '';
        
        // Fetch observations
        const currentProtocol = window.location.protocol;
        const obsUrl = `../FROST-Server/v1.1/Datastreams(${datastreamId})/Observations?$top=${state.currentLimit}&$orderby=phenomenonTime%20desc`;
        const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
        const obsResponse = await fetch(secureObsUrl);
        
        if (!obsResponse.ok) throw new Error(`HTTP error! Status: ${obsResponse.status}`);
        
        const obsData = await obsResponse.json();
        
        if (!obsData.value || obsData.value.length === 0) {
            chartPanelContent.innerHTML = `
                <div class="no-data-message">
                    <h3>No observations found</h3>
                    <p>This datastream has no observation data available.</p>
                </div>
            `;
            updateStatus('No data available', 'warning');
            return;
        }
        
        // Process observations
        const processedData = processObservations(obsData.value);
        
        // Calculate stats
        const stats = calculateStats(processedData, unitSymbol);
        
        // Render chart
        renderChart(processedData, unitSymbol, datastreamName, stats);
        
        updateStatus(`Loaded ${processedData.length} observations`, 'success');
        
                } catch (error) {
        console.error('Error loading chart data:', error);
        chartPanelContent.innerHTML = `
            <div class="no-data-message">
                <h3>Error loading data</h3>
                <p>${error.message}</p>
            </div>
        `;
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

// Process observations and detect gaps (original style with gap fillers)
function processObservations(observations) {
    const gapThreshold = 15 * 60 * 1000; // 15 minutes
    const fillerInterval = 5 * 60 * 1000; // 5 minutes
    let formattedData = [];
    let previousTime = null;
    
    // Sort by time (oldest first)
    const sorted = [...observations].sort((a, b) => {
        return new Date(a.phenomenonTime) - new Date(b.phenomenonTime);
    });
    
    sorted.forEach(entry => {
        const timestamp = new Date(entry.phenomenonTime);
        const value = entry.result;
        
        if (previousTime) {
            const gap = timestamp - previousTime;
            
            // If gap is larger than threshold, insert gap fillers
            if (gap > gapThreshold) {
                let fillerTime = new Date(previousTime.getTime() + fillerInterval);
                while (fillerTime < timestamp) {
                    formattedData.push({ 
                        x: fillerTime, 
                        y: 0, 
                        gapFiller: true 
                    });
                    fillerTime = new Date(fillerTime.getTime() + fillerInterval);
                }
            }
        }
        
        formattedData.push({ 
            x: timestamp, 
            y: value, 
            gapFiller: false 
        });
        previousTime = timestamp;
    });
    
    return formattedData;
}

// Calculate statistics
function calculateStats(data, unitSymbol) {
    const validData = data.filter(d => !d.gapFiller && d.y !== null);
    
    if (validData.length === 0) {
        return {
            current: 'N/A',
            min: 'N/A',
            max: 'N/A',
            avg: 'N/A',
            unit: unitSymbol
        };
    }
    
    const values = validData.map(d => d.y);
    const current = values[values.length - 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    
    // Count gap fillers
    const gaps = data.filter(d => d.gapFiller).length;
    
    return {
        current: current.toFixed(2),
        min: min.toFixed(2),
        max: max.toFixed(2),
        avg: avg.toFixed(2),
        unit: unitSymbol,
        gaps: gaps,
        totalPoints: validData.length
    };
}

// Render chart
function renderChart(data, unitSymbol, datastreamName, stats) {
    const chartPanelContent = document.getElementById('chartPanelContent');
    
    // Destroy existing chart
    if (state.currentChart) {
        state.currentChart.destroy();
    }
    
    // Create stats HTML
    const statsHTML = `
        <div class="chart-stats">
            <div class="stat-card">
                <div class="stat-label">Current Value</div>
                <div class="stat-value">${stats.current} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Minimum</div>
                <div class="stat-value">${stats.min} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Maximum</div>
                <div class="stat-value">${stats.max} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Average</div>
                <div class="stat-value">${stats.avg} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            ${stats.gaps > 0 ? `
            <div class="stat-card" style="border-color: var(--gap-color); background: var(--gap-bg);">
                <div class="stat-label">Data Gaps</div>
                <div class="stat-value"><span class="gap-indicator"></span>${stats.gaps}</div>
            </div>
            ` : ''}
            <div class="stat-card">
                <div class="stat-label">Data Points</div>
                <div class="stat-value">${stats.totalPoints}</div>
            </div>
        </div>
    `;
    
    // Create chart container
    const chartHTML = `
        ${statsHTML}
        <div class="chart-container">
            <canvas id="timeSeriesChart"></canvas>
        </div>
    `;
    
    chartPanelContent.innerHTML = chartHTML;
    
    // Prepare chart data (original style)
    const chartData = {
        datasets: [
            {
                label: 'Observed Value',
                data: data,
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                tension: 0.5,
                cubicInterpolationMode: 'monotone', // smooth curve
                spanGaps: (ctx) => ctx.raw && ctx.raw.gapFiller !== true
            }
        ]
    };
    
    // Check for valid data
    const validValues = data.filter(d => !d.gapFiller && d.y !== null).map(d => d.y);
    
    if (validValues.length === 0) {
        chartPanelContent.innerHTML = `
            <div class="no-data-message">
                <h3>No valid data points</h3>
                <p>Unable to render chart with available data.</p>
            </div>
        `;
        return;
    }
    
    // Create chart
    const ctx = document.getElementById('timeSeriesChart').getContext('2d');
    state.currentChart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            if (context.raw.gapFiller) {
                                return 'Data Gap';
                            }
                            return `${context.dataset.label}: ${context.raw.y?.toFixed(2) || 'N/A'} ${unitSymbol}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        tooltipFormat: 'yyyy-MM-dd HH:mm',
                        displayFormats: {
                            minute: 'HH:mm',
                            hour: 'HH:mm',
                            day: 'MMM dd'
                        }
                    },
                    ticks: {
                        autoSkip: true,
                        maxRotation: 45,
                        minRotation: 45
                    },
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                }
            }
        }
    });
}

// Set chart limit
function setChartLimit(limit) {
    state.currentLimit = limit;
    
    // Update button states
    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.classList.remove('active');
        if (parseInt(btn.dataset.limit) === limit) {
            btn.classList.add('active');
        }
    });
    
    // Reload chart if datastream is selected
    if (state.currentDatastream) {
        loadChartData(state.currentDatastream);
    }
}

// Toggle chart panel
function toggleChartPanel() {
    const chartPanel = document.getElementById('chartPanel');
    const isExpanded = chartPanel.classList.contains('expanded');
    
    if (isExpanded) {
        chartPanel.classList.remove('expanded');
    } else {
        chartPanel.classList.add('expanded');
    }
    
    // Update toggle icon rotation
    const toggleIcon = document.getElementById('chartPanelToggle').querySelector('svg');
    if (chartPanel.classList.contains('expanded')) {
        toggleIcon.style.transform = 'rotate(180deg)';
    } else {
        toggleIcon.style.transform = 'rotate(0deg)';
    }
}

// Zoom to extents (fit all markers)
function zoomToExtents() {
    if (state.markerCluster && state.markerCluster.getLayers().length > 0) {
        state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
            animate: true,
            duration: 1.2, // 1.2 second smooth animation
            padding: [30, 30], // Padding in pixels
            maxZoom: 18 // Don't zoom in too far
        });
        updateStatus('Zoomed to show all sensors', 'success');
    } else {
        updateStatus('No sensors to zoom to', 'warning');
    }
}

// Update marker icon based on selection state
function updateMarkerIcon(thingId, isSelected) {
    const marker = state.markers[thingId];
    if (!marker) return;
    
    const color = isSelected ? '#ef4444' : '#3b82f6'; // Red when selected, blue otherwise
    const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    
    marker.setIcon(icon);
}

// Show thing metadata sidebar
function showThingMetadata(thingId) {
    const thing = state.things[thingId];
    if (!thing) return;
    
    // Update marker icons - deselect previous, select current
    if (state.selectedThingId && state.selectedThingId !== thingId) {
        updateMarkerIcon(state.selectedThingId, false);
    }
    state.selectedThingId = thingId;
    updateMarkerIcon(thingId, true);
    
    const sidebar = document.getElementById('thingMetadataSidebar');
    const title = document.getElementById('thingMetadataTitle');
    const content = document.getElementById('thingMetadataContent');
    const mainContent = document.querySelector('.main-content');
    
    title.textContent = thing.name;
    
    // Add class to main content to adjust chart panel
    if (mainContent) {
        mainContent.classList.add('has-metadata-sidebar');
    }
    
    // Build metadata content (status will be added by updateMetadataSidebarStatus)
    let metadataHTML = `
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
        </div>
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
    const healthStatus = thing.healthStatus || 'active';
    const healthLabel = thing.healthLabel || '<60mins';
    const timeSince = thing.timeSinceLastObservation;
    updateMetadataSidebarStatus(healthStatus, healthLabel, timeSince);
}

// Hide thing metadata sidebar
function hideThingMetadata() {
    // Deselect marker when sidebar is closed
    if (state.selectedThingId) {
        updateMarkerIcon(state.selectedThingId, false);
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

// Update datastreams in metadata sidebar
function updateThingMetadataDatastreams(thingId, datastreams) {
    const datastreamsDiv = document.getElementById('thingMetadataDatastreams');
    if (!datastreamsDiv) return;
    
    if (datastreams.length === 0) {
        datastreamsDiv.innerHTML = '<div style="color: var(--gray-500); font-size: 0.875rem;">No datastreams available</div>';
        return;
    }
    
    datastreamsDiv.innerHTML = '';
    
    datastreams.forEach(async (ds) => {
        const unitSymbol = ds.unitOfMeasurement?.symbol || '';
        
        try {
            const currentProtocol = window.location.protocol;
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await fetch(secureObsUrl);
            const obsData = await obsResponse.json();
            const latestValue = obsData.value?.[0]?.result || '-';
            
            const displayName = formatDatastreamName(ds.name);
            const dsItem = document.createElement('div');
            dsItem.className = 'metadata-datastream-item';
            dsItem.innerHTML = `
                <div class="metadata-datastream-name">${displayName}</div>
                <div class="metadata-datastream-meta">
                    <span>${unitSymbol}</span>
                    <span style="font-weight: 600;">${latestValue}</span>
                </div>
            `;
            dsItem.addEventListener('click', () => {
                selectDatastream(ds['@iot.id'], displayName);
            });
            datastreamsDiv.appendChild(dsItem);
        } catch (error) {
            const displayName = formatDatastreamName(ds.name);
            const dsItem = document.createElement('div');
            dsItem.className = 'metadata-datastream-item';
            dsItem.innerHTML = `
                <div class="metadata-datastream-name">${displayName}</div>
                <div class="metadata-datastream-meta" style="color: #ef4444;">Error loading</div>
            `;
            dsItem.addEventListener('click', () => {
                selectDatastream(ds['@iot.id'], displayName);
            });
            datastreamsDiv.appendChild(dsItem);
        }
    });
}

// Update datastream navigation button visibility
function updateDatastreamNavigation() {
    const nextBtn = document.getElementById('chartNextDatastreamBtn');
    
    if (!nextBtn) return;
    
    const hasMultiple = state.currentThingDatastreams.length > 1;
    
    if (hasMultiple) {
        nextBtn.style.display = 'flex';
        // Button is always enabled - it cycles through all datastreams
        nextBtn.disabled = false;
    } else {
        nextBtn.style.display = 'none';
    }
}

// Navigate to next datastream (cycles through all)
function navigateToDatastream(direction) {
    if (state.currentThingDatastreams.length === 0) return;
    
    let newIndex = state.currentDatastreamIndex + direction;
    // Wrap around: if at end, go to beginning; if at beginning going back, go to end
    if (newIndex < 0) {
        newIndex = state.currentThingDatastreams.length - 1;
    } else if (newIndex >= state.currentThingDatastreams.length) {
        newIndex = 0;
    }
    
    const datastream = state.currentThingDatastreams[newIndex];
    const displayName = formatDatastreamName(datastream.name);
    selectDatastream(datastream['@iot.id'], displayName);
}

// Make selectDatastream available globally for onclick handlers
window.selectDatastream = selectDatastream;