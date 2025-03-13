async function fetchThings() {
    // Fetch SensorThings from the API.
    updateStatus('Fetching Things...');
    try {
        // Fetch from the Locations API
        const response = await fetch('http://localhost:8080/FROST-Server/v1.1/Things');
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const thingData = await response.json();
        console.log('Things data:', thingData);
        
        if (thingData.value && thingData.value.length > 0) {
            for (thing of thingData.value) {
                try {
                    const locationResponse = await fetch(thing["Locations@iot.navigationLink"])
                    const locationData = await locationResponse.json()
                    const coordinates = locationData.value[0].location.coordinates
                    const locationDescription = locationData.value[0].description
                    // Create marker for this location
                    const marker = L.marker([coordinates[0], coordinates[1]]).addTo(map)
                        .bindPopup(createPopupContent(thing));
                    
                    // Store location data
                    thingsData[thing["@iot.id"]] = { 
                        marker, 
                        name: thing.name,
                        description: thing.description,
                        coordinates: [coordinates[0], coordinates[1]],
                        locationDescription: locationDescription
                    };
                    
                    // Also store by name for easier lookup
                    thingsByName[thing.name] = {
                        marker,
                        id: thing["@iot.id"],
                        coordinates: [coordinates[0], coordinates[1]],
                        description: thing.description,
                        locationDescription: locationDescription
                    };
                    
                    // Add click event to marker to highlight corresponding list item
                    marker.on('click', () => {
                        map.closePopup();
                        marker.bindPopup(createPopupContent(thing)).openPopup();
                        highlightThingInList(thing.name);
                        // Fetch datastreams when marker is clicked
                        fetchDatastreamsForThing(thing["@iot.id"]);
                    });
                } catch (error) {
                    console.error(`Error processing location ${thing["@iot.id"]}:`, error);
                }
            };
            
            // Adjust map view to show all markers
            if (Object.keys(thingsData).length > 0) {
                const markers = Object.values(thingsData).map(l => l.marker);
                const group = L.featureGroup(markers);
                map.fitBounds(group.getBounds().pad(0.1));
            }
            
            updateStatus(`Loaded ${Object.keys(thingsData).length} of ${thingData.value.length} locations`, 'success');
            
            // Populate the Things list
            populateThingList(thingData.value);
        } else {
            throw new Error('No locations found in API response');
        }
    } catch (error) {
        console.error("Error fetching locations:", error);
        updateStatus(`Error fetching locations: ${error.message}. Using sample data.`, 'error');
        
        // Use sample data if API fails
        useSampleData();
    }
}

function createPopupContent(thing) {
    let content = `<div class="popup-content">`;
    content += `<b>${thing.name}</b>`;
    
    if (thing.description) {
        content += `<br>${thing.description}`;
    }
    
    // content += `<br>Coordinates: [${thing.location.coordinates[0]}, ${thing.location.coordinates[1]}]`;
    
    // Add placeholder for datastreams that will be loaded dynamically
    content += `<div id="datastreams-${thing['@iot.id']}" class="popup-section">
        <div class="loading-datastreams">Loading datastreams...</div>
    </div>`;
    
    content += `</div>`;
    
    return content;
}

function highlightThingInList(locationName) {
    // Remove highlight from all locations
    document.querySelectorAll('#locations li').forEach(li => {
        li.classList.remove('active-location');
    });
    
    // Find and highlight the clicked location
    const locationElement = document.querySelector(`#locations li[data-name="${locationName}"]`);
    if (locationElement) {
        locationElement.classList.add('active-location');
        // Scroll the location into view in the list
        locationElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function populateThingList(things) {
    const thingList = document.getElementById('locations');
    
    // Make sure to clear the list before adding new entries
    thingList.innerHTML = '';

    things.forEach(thing => {
        const li = document.createElement('li');
        li.textContent = thing.name;
        li.setAttribute('data-name', thing.name);
        li.setAttribute('data-id', thing["@iot.id"]);
        
        // Add description if available
        const locationData = thingsData[thing["@iot.id"]]
        console.log(thingsData[thing])
        if (locationData) {
            const descriptionDiv = document.createElement('div');
            descriptionDiv.className = 'location-details';
            descriptionDiv.textContent = locationData.locationDescription;
            li.appendChild(descriptionDiv);
        }
        
        li.addEventListener('click', () => {
            // Find the location information based on the name
            const locationInfo = thingsByName[thing.name];
            if (locationInfo) {
                // Set the map view to the location's coordinates and open the popup
                map.setView(locationInfo.coordinates, 15); // Zoom level 15
                locationInfo.marker.openPopup();
                
                // Highlight this location in the list
                highlightThingInList(thing.name);
                
                updateStatus(`Focused on location: ${thing.name}`, 'success');
                
                // Fetch datastreams for this location
                fetchDatastreamsForThing(locationInfo.id);
            } else {
                updateStatus(`Could not find coordinates for location: ${thing.name}`, 'error');
            }
        });

        thingList.appendChild(li);
    });
}

async function fetchDatastreamsForThing(thingId) {
    updateStatus(`Fetching Datastreams for Thing ID: ${thingId}...`);
    try {
        // First, fetch the Datastreams associated with this Thing
        const datastreamResponse = await fetch(`http://localhost:8080/FROST-Server/v1.1/Things(${thingId})/Datastreams`);
        
        if (!datastreamResponse.ok) {
            throw new Error(`HTTP error! Status: ${datastreamResponse.status}`);
        }
        
        const datastreamData = await datastreamResponse.json();
        console.log(`Datastream data for location ${thingId}:`, datastreamData);
        
        // if (datastreamData.value && datastreamData.value.length > 0) {
        //     // Create a container for all datastreams from all things
        let allDatastreamsContent = `<h4>Available Datastreams:</h4>`;
        // Process each Datastream
        for (const datastream of datastreamData.value) {
        // Add each datastream
                allDatastreamsContent += `<div class="thing-name">${datastream.name}</div>`;
                const unitSymbol = datastream.unitOfMeasurement ? datastream.unitOfMeasurement.symbol : '';
                const unitName = datastream.unitOfMeasurement ? datastream.unitOfMeasurement.name : '';
                const resultsResposne = await fetch(datastream["Observations@iot.navigationLink"])
                const results = await resultsResposne.json()
                let latestResult, latestResultTime, latestResultValue
                try {
                    latestResult = results.value.at(-1)
                    latestResultValue = latestResult.result
                    latestResultTime = latestResult.phenomenonTime
                } catch (error) {
                    latestResultValue = "-"
                    latestResultTime = "-"
                }
                allDatastreamsContent += `
                    <div class="datastream-item">
                        <span class="datastream-name">${latestResultTime}</span>
                        <div>${latestResultValue ||'' } ${unitSymbol}</div>
                    </div>`;
            };
            updatePopupWithDatastreams(thingId, allDatastreamsContent);
    } catch (error) {
        console.error(`Error fetching datastreams for location ${thingId}:`, error);
        updateStatus(`Error fetching datastreams: ${error.message}`, 'error');
        updatePopupWithDatastreams(thingId, `<h4>Error loading datastreams</h4><div>${error.message}</div>`);
    }
}

function updatePopupWithDatastreams(locationId, content) {
    const locationInfo = thingsData[locationId];
    if (locationInfo) {
        const popup = locationInfo.marker.getPopup();
        const popupContent = popup.getContent();
        
        // Replace the loading placeholder with actual content
        const updatedContent = popupContent.replace(
            new RegExp(`<div id="datastreams-${locationId}" class="popup-section">.*?</div>`, 's'),
            `<div id="datastreams-${locationId}" class="popup-section">${content}</div>`
        );
        
        popup.setContent(updatedContent);
        
        // If the popup is already open, update it
        if (locationInfo.marker.isPopupOpen()) {
            locationInfo.marker.openPopup();
        }
    }
}