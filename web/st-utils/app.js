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
    maxClusterSize: 1 // Track maximum cluster size for color normalization
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

    // Chart panel toggle
    const chartPanelHeader = document.getElementById('chartPanelHeader');
    chartPanelHeader.addEventListener('click', () => {
        toggleChartPanel();
    });

    // Chart limit buttons
    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const limit = parseInt(e.target.dataset.limit);
            setChartLimit(limit);
        });
    });

    // Zoom extents button
    const zoomExtentsBtn = document.getElementById('zoomExtentsBtn');
    if (zoomExtentsBtn) {
        zoomExtentsBtn.addEventListener('click', zoomToExtents);
    }
}

// Update status message
function updateStatus(message, type = '') {
    const statusEl = document.getElementById('statusMessage');
    statusEl.textContent = message;
    statusEl.className = `status-message ${type}`;
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
    
    // Create marker (coordinates are [lat, lon] from FROST API)
    const marker = L.marker([coordinates[0], coordinates[1]]);
    
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
    
    // Create popup content
    const popupContent = createPopupContent(thing);
    marker.bindPopup(popupContent);
    
    // Handle marker click
    marker.on('click', async () => {
        highlightThingInList(thing.name);
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
        
        // Update popup
        await updatePopupWithDatastreams(thingId, datastreamData.value);
        
        // Update sidebar if thing is visible
        updateThingDatastreamsInSidebar(thingId, datastreamData.value);
        
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
        const escapedName = ds.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        newContent += `
            <div style="padding: 0.5rem; margin: 0.25rem 0; background: #f3f4f6; border-radius: 0.375rem; cursor: pointer; transition: background 0.2s;"
                 onclick="selectDatastream(${ds['@iot.id']}, '${escapedName}')"
                 onmouseover="this.style.background='#93c5fd'"
                 onmouseout="this.style.background='#f3f4f6'">
                <div style="font-weight: 500; margin-bottom: 0.25rem;">${ds.name}</div>
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

// Update thing datastreams in sidebar
function updateThingDatastreamsInSidebar(thingId, datastreams) {
    const thingItem = document.querySelector(`[data-thing-id="${thingId}"]`);
    if (!thingItem) return;
    
    let datastreamsDiv = thingItem.querySelector('.thing-datastreams');
    if (!datastreamsDiv) {
        datastreamsDiv = document.createElement('div');
        datastreamsDiv.className = 'thing-datastreams';
        thingItem.appendChild(datastreamsDiv);
    }
    
    datastreamsDiv.innerHTML = '';
    
    datastreams.forEach(async (ds) => {
        const unitSymbol = ds.unitOfMeasurement?.symbol || '';
        
        // Fetch latest observation
        try {
            const currentProtocol = window.location.protocol;
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await fetch(secureObsUrl);
            const obsData = await obsResponse.json();
            const latestValue = obsData.value?.[0]?.result || '-';
            
            const dsItem = document.createElement('div');
            dsItem.className = 'datastream-item';
            dsItem.dataset.datastreamId = ds['@iot.id'];
            dsItem.innerHTML = `
                <div class="datastream-name">${ds.name}</div>
                <div class="datastream-meta">
                    <span>${unitSymbol}</span>
                    <span class="datastream-latest">${latestValue}</span>
                </div>
            `;
            dsItem.addEventListener('click', () => {
                selectDatastream(ds['@iot.id'], ds.name);
            });
            datastreamsDiv.appendChild(dsItem);
        } catch (error) {
            const dsItem = document.createElement('div');
            dsItem.className = 'datastream-item';
            dsItem.dataset.datastreamId = ds['@iot.id'];
            dsItem.innerHTML = `
                <div class="datastream-name">${ds.name}</div>
                <div class="datastream-meta" style="color: #ef4444;">Error loading</div>
            `;
            dsItem.addEventListener('click', () => {
                selectDatastream(ds['@iot.id'], ds.name);
            });
            datastreamsDiv.appendChild(dsItem);
        }
    });
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
            <div class="thing-name">${thing.name}</div>
            ${thingData.locationDescription ? `<div class="thing-description">${thingData.locationDescription}</div>` : ''}
        `;
        
        li.addEventListener('click', () => {
            state.map.setView(thingData.coordinates, 15, {
                animate: true,
                duration: 0.8, // 0.8 second smooth animation
                easeLinearity: 0.25
            });
            // Open popup after zoom animation completes
            setTimeout(() => {
                thingData.marker.openPopup();
            }, 800);
            highlightThingInList(thing.name);
            loadDatastreamsForThing(thing['@iot.id']);
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
        const datastreamName = dsData.name || 'Unknown';
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

// Make selectDatastream available globally for onclick handlers
window.selectDatastream = selectDatastream;