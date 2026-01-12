// Sensor Config Builder JavaScript

// Model configurations with default datastreams and observedProperties
const MODEL_CONFIGS = {
    'milesight.am103l': {
        datastreams: [
            {
                name: 'temperature_indoor',
                description: 'This datastream is measuring the internal room temperature.',
                observedProperty: 'temperature_indoor',
                unit: { name: 'degree Celsius', symbol: '°C', definition: 'https://unitsofmeasure.org/ucum#para-30' }
            },
            {
                name: 'humidity',
                description: 'Datastream for observations of humidity levels.',
                observedProperty: 'internal_humidity',
                unit: { name: 'percent', symbol: '%', definition: 'https://unitsofmeasure.org/ucum#para-29' }
            },
            {
                name: 'co2',
                description: 'Datastream for observations of CO2 levels.',
                observedProperty: 'co2_levels',
                unit: { name: 'parts per million', symbol: 'ppm', definition: 'https://unitsofmeasure.org/ucum#para-29' }
            },
            {
                name: 'battery_level',
                description: 'Battery level of the sensor.',
                observedProperty: 'battery_level',
                unit: { name: 'percentage', symbol: 'percent', definition: '...' }
            }
        ],
        observedProperties: [
            { name: 'temperature_indoor', definition: 'https://dbpedia.org/page/Temperature', description: 'The temperature where the indoor module is placed.' },
            { name: 'internal_humidity', definition: 'https://en.wikipedia.org/wiki/Humidity', description: 'The internal humidity levels wherever the indoor sensor is placed.' },
            { name: 'co2_levels', definition: 'https://en.wikipedia.org/wiki/Indoor_air_quality#Carbon_dioxide', description: 'The CO2 levels wherever the indoor module is placed.' },
            { name: 'battery_level', definition: '...', description: '...' }
        ]
    },
    'milesight.am308l': {
        datastreams: [
            {
                name: 'temperature_indoor',
                description: 'This datastream is measuring the internal room temperature.',
                observedProperty: 'temperature_indoor',
                unit: { name: 'degree Celsius', symbol: '°C', definition: 'https://unitsofmeasure.org/ucum#para-30' }
            },
            {
                name: 'humidity',
                description: 'Datastream for observations of humidity levels.',
                observedProperty: 'internal_humidity',
                unit: { name: 'percent', symbol: '%', definition: 'https://unitsofmeasure.org/ucum#para-29' }
            },
            {
                name: 'co2',
                description: 'Datastream for observations of CO2 levels.',
                observedProperty: 'co2_levels',
                unit: { name: 'parts per million', symbol: 'ppm', definition: 'https://unitsofmeasure.org/ucum#para-29' }
            },
            {
                name: 'battery_level',
                description: 'Battery level of the sensor.',
                observedProperty: 'battery_level',
                unit: { name: 'percentage', symbol: 'percent', definition: '...' }
            },
            {
                name: 'light_level',
                description: 'Datastream for observations of light levels.',
                observedProperty: 'light_level',
                unit: { name: 'lux_scale', symbol: 'int', definition: 'Lux scale from 0 to 5 in bands of 10,000 lux' }
            },
            {
                name: 'passive_infrared',
                description: 'PIR motion detection datastream.',
                observedProperty: 'motion',
                unit: { name: 'idle | active', symbol: null, definition: 'boolean, active when motion was detected' }
            },
            {
                name: 'particulate_matter_10',
                description: 'Datastream for observations of PM10 levels.',
                observedProperty: 'coarse_airborne_particles',
                unit: { name: '...', symbol: 'μg/m³', definition: '...' }
            },
            {
                name: 'particulate_matter_2_5',
                description: 'Datastream for observations of PM2.5 levels.',
                observedProperty: 'fine_airborne_particles',
                unit: { name: '...', symbol: 'μg/m³', definition: '...' }
            },
            {
                name: 'gauge_pressure',
                description: 'Datastream for observations of pressure levels.',
                observedProperty: 'gauge_pressure',
                unit: { name: 'millibar', symbol: 'mbar', definition: 'https://unitsofmeasure.org/ucum#datyp2apdxatblxmp' }
            },
            {
                name: 'total_volatile_organic_compounds',
                description: 'Datastream for observations of TVOC levels.',
                observedProperty: 'tvoc',
                unit: { name: '...', symbol: null, definition: '...' }
            }
        ],
        observedProperties: [
            { name: 'temperature_indoor', definition: 'https://dbpedia.org/page/Temperature', description: 'The temperature where the indoor module is placed.' },
            { name: 'internal_humidity', definition: 'https://en.wikipedia.org/wiki/Humidity', description: 'The internal humidity levels wherever the indoor sensor is placed.' },
            { name: 'co2_levels', definition: 'https://en.wikipedia.org/wiki/Indoor_air_quality#Carbon_dioxide', description: 'The CO2 levels wherever the indoor module is placed.' },
            { name: 'battery_level', definition: '...', description: '...' },
            { name: 'light_level', definition: 'The amount of light in a room, in lux.', description: '...' },
            { name: 'motion', definition: '...', description: '...' },
            { name: 'coarse_airborne_particles', definition: '...', description: '...' },
            { name: 'fine_airborne_particles', definition: '...', description: '...' },
            { name: 'gauge_pressure', definition: 'https://en.wikipedia.org/wiki/Pressure_measurement#Absolute', description: 'The gauge pressure where the indoor module is placed.' },
            { name: 'tvoc', definition: '...', description: '...' }
        ]
    },
    'netatmo.nws03': {
        datastreams: [
            {
                name: 'temperature_indoor',
                description: 'This datastream is measuring the internal room temperature.',
                observedProperty: 'indoor_temperature',
                unit: { name: 'degree Celsius', symbol: '°C', definition: 'https://unitsofmeasure.org/ucum#para-30' }
            },
            {
                name: 'humidity',
                description: 'Datastream for observations of humidity levels.',
                observedProperty: 'internal_humidity',
                unit: { name: 'percent', symbol: '%', definition: 'https://unitsofmeasure.org/ucum#para-29' }
            },
            {
                name: 'co2',
                description: 'Datastream for observations of CO2 levels.',
                observedProperty: 'co2_levels',
                unit: { name: 'parts per million', symbol: 'ppm', definition: 'https://unitsofmeasure.org/ucum#para-29' }
            },
            {
                name: 'gauge_pressure',
                description: 'Datastream for observations of pressure levels.',
                observedProperty: 'gauge_pressure',
                unit: { name: 'millibar', symbol: 'mbar', definition: 'https://unitsofmeasure.org/ucum#datyp2apdxatblxmp' }
            },
            {
                name: 'absolute_pressure',
                description: 'Datastream for observations of absolute pressure levels.',
                observedProperty: 'absolute_pressure',
                unit: { name: 'millibar', symbol: 'mbar', definition: 'https://unitsofmeasure.org/ucum#datyp2apdxatblxmp' }
            },
            {
                name: 'noise',
                description: 'Datastream for observations of noise levels.',
                observedProperty: 'internal_noise_levels',
                unit: { name: 'decibel', symbol: 'db', definition: 'https://unitsofmeasure.org/ucum#para-46' }
            }
        ],
        observedProperties: [
            { name: 'indoor_temperature', definition: 'https://dbpedia.org/page/Temperature', description: 'The temperature where the indoor module is placed.' },
            { name: 'internal_humidity', definition: 'https://en.wikipedia.org/wiki/Humidity', description: 'The internal humidity levels wherever the indoor sensor is placed.' },
            { name: 'co2_levels', definition: 'https://en.wikipedia.org/wiki/Indoor_air_quality#Carbon_dioxide', description: 'The CO2 levels wherever the indoor module is placed.' },
            { name: 'gauge_pressure', definition: 'https://en.wikipedia.org/wiki/Pressure_measurement#Absolute', description: 'The gauge pressure where the indoor module is placed.' },
            { name: 'absolute_pressure', definition: 'https://en.wikipedia.org/wiki/Pressure_measurement#Absolute', description: 'The absolute pressure where the indoor module is placed.' },
            { name: 'internal_noise_levels', definition: 'https://en.wikipedia.org/wiki/Ambient_noise_level', description: 'The internal ambient noise level where the sensor is placed.' }
        ]
    }
};

let datastreamCounter = 0;
let observedPropertyCounter = 0;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
});

function initializeEventListeners() {
    const sensorModelSelect = document.getElementById('sensorModel');
    const addDatastreamBtn = document.getElementById('addDatastreamBtn');
    const form = document.getElementById('sensorConfigForm');
    const previewBtn = document.getElementById('previewBtn');
    const closePreviewModal = document.getElementById('closePreviewModal');
    const closePreviewBtn = document.getElementById('closePreviewBtn');
    const copyYamlBtn = document.getElementById('copyYamlBtn');
    const modal = document.getElementById('previewModal');

    sensorModelSelect.addEventListener('change', handleModelChange);
    addDatastreamBtn.addEventListener('click', addDatastream);
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        handlePreview();
    });
    previewBtn.addEventListener('click', handlePreview);
    closePreviewModal.addEventListener('click', () => modal.classList.remove('show'));
    closePreviewBtn.addEventListener('click', () => modal.classList.remove('show'));
    copyYamlBtn.addEventListener('click', copyYamlToClipboard);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('show');
    });

    // Initially disable all fields until model is selected
    disableFormUntilModelSelected();
}

function disableFormUntilModelSelected() {
    // Disable all form elements except sensor model
    document.querySelectorAll('[data-disabled-until-model]').forEach(el => {
        if (el.tagName === 'SECTION') {
            el.classList.remove('enabled');
        } else if (el.tagName === 'DIV' && el.classList.contains('form-group')) {
            el.classList.remove('enabled');
            el.querySelectorAll('input, select, textarea').forEach(input => {
                input.disabled = true;
            });
        } else if (el.classList.contains('form-actions')) {
            el.classList.remove('enabled');
            el.querySelectorAll('button').forEach(btn => {
                btn.disabled = true;
            });
        } else {
            el.disabled = true;
        }
    });
}

function enableFormAfterModelSelected() {
    // Enable all form elements
    document.querySelectorAll('[data-disabled-until-model]').forEach(el => {
        if (el.tagName === 'SECTION') {
            el.classList.add('enabled');
            // Enable inputs within sections
            el.querySelectorAll('input, select, textarea').forEach(input => {
                input.disabled = false;
            });
        } else if (el.tagName === 'DIV' && el.classList.contains('form-group')) {
            el.classList.add('enabled');
            el.querySelectorAll('input, select, textarea').forEach(input => {
                input.disabled = false;
            });
        } else if (el.classList.contains('form-actions')) {
            el.classList.add('enabled');
            el.querySelectorAll('button').forEach(btn => {
                btn.disabled = false;
            });
        } else {
            el.disabled = false;
        }
    });
}

function handleModelChange(e) {
    const model = e.target.value;
    if (!model || !MODEL_CONFIGS[model]) {
        disableFormUntilModelSelected();
        return;
    }

    // Enable the form
    enableFormAfterModelSelected();

    const config = MODEL_CONFIGS[model];
    
    // Auto-populate sensor key if empty
    const sensorKeyInput = document.getElementById('sensorKey');
    if (!sensorKeyInput.value) {
        sensorKeyInput.value = model;
    }

    // Clear existing datastreams and observedProperties
    const datastreamsContainer = document.getElementById('datastreamsContainer');
    const observedPropertiesContainer = document.getElementById('observedPropertiesContainer');
    datastreamsContainer.innerHTML = '';
    observedPropertiesContainer.innerHTML = '';
    datastreamCounter = 0;
    observedPropertyCounter = 0;

    // Add datastreams
    config.datastreams.forEach(ds => {
        addDatastreamFromConfig(ds);
    });

    // Add observedProperties
    config.observedProperties.forEach(op => {
        addObservedPropertyFromConfig(op);
    });

    // Open the compact sections by default after populating
    const datastreamsSection = datastreamsContainer.closest('details');
    const observedPropertiesSection = observedPropertiesContainer.closest('details');
    if (datastreamsSection) datastreamsSection.open = false;
    if (observedPropertiesSection) observedPropertiesSection.open = false;
}

function addDatastreamFromConfig(config) {
    datastreamCounter++;
    const container = document.getElementById('datastreamsContainer');
    container.querySelector('.info-message')?.remove();

    const dsId = `datastream_${datastreamCounter}`;
    const item = document.createElement('div');
    item.className = 'datastream-item';
    item.id = dsId;
    item.innerHTML = `
        <div class="datastream-item-header">
            <h3>${config.name}</h3>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.75rem;">
            <div><strong>ObservedProperty:</strong> ${config.observedProperty}</div>
            <div><strong>Unit:</strong> ${config.unit.symbol || config.unit.name}</div>
        </div>
        <input type="hidden" class="ds-name" value="${config.name}">
        <input type="hidden" class="ds-observed-property" value="${config.observedProperty}">
        <textarea class="ds-description" style="display: none;">${config.description}</textarea>
        <input type="hidden" class="ds-observation-type" value="instant">
        <input type="hidden" class="ds-unit-name" value="${config.unit.name}">
        <input type="hidden" class="ds-unit-symbol" value="${config.unit.symbol || ''}">
        <input type="hidden" class="ds-unit-definition" value="${config.unit.definition}">
        <input type="hidden" class="ds-observed-area-type" value="Polygon">
        <input type="hidden" class="ds-observed-area-coords" value="null">
    `;
    container.appendChild(item);
    updateDatastreamCount();
}

function updateDatastreamCount() {
    const count = document.querySelectorAll('.datastream-item').length;
    const countElement = document.getElementById('datastreamCount');
    if (countElement) countElement.textContent = count;
}

function updateObservedPropertyCount() {
    const count = document.querySelectorAll('.observed-property-item').length;
    const countElement = document.getElementById('observedPropertyCount');
    if (countElement) countElement.textContent = count;
}

function addObservedPropertyFromConfig(config) {
    observedPropertyCounter++;
    const container = document.getElementById('observedPropertiesContainer');
    container.querySelector('.info-message')?.remove();

    const opId = `observedproperty_${observedPropertyCounter}`;
    const item = document.createElement('div');
    item.className = 'observed-property-item';
    item.id = opId;
    item.innerHTML = `
        <div class="observed-property-item-header">
            <h3>${config.name}</h3>
        </div>
        <div style="font-size: 0.75rem;">
            <div><strong>Definition:</strong> <a href="${config.definition}" target="_blank" style="color: var(--primary);">${config.definition}</a></div>
        </div>
        <input type="hidden" class="op-name" value="${config.name}">
        <input type="hidden" class="op-definition" value="${config.definition}">
        <textarea class="op-description" style="display: none;">${config.description}</textarea>
    `;
    container.appendChild(item);
    updateObservedPropertyCount();
}

function parseJSONField(value) {
    if (!value || value.trim() === '' || value.trim() === 'null') return null;
    try {
        return JSON.parse(value);
    } catch (e) {
        return value; // Return as string if not valid JSON
    }
}

function parseCoordinates(value) {
    if (!value || value.trim() === '' || value.trim().toLowerCase() === 'null') return null;
    try {
        return JSON.parse(value);
    } catch (e) {
        return null;
    }
}

function collectFormData() {
    const sensorModel = document.getElementById('sensorModel').value;
    const sensorKey = document.getElementById('sensorKey').value;
    const sensorName = document.getElementById('sensorName').value;
    const sensorDescription = document.getElementById('sensorDescription').value;
    const sensorMetadata = document.getElementById('sensorMetadata').value || 'none';
    const sensorEncodingType = document.getElementById('sensorEncodingType').value;
    const sensorProperties = parseJSONField(document.getElementById('sensorProperties').value);

    const thingName = document.getElementById('thingName').value;
    const thingDescription = document.getElementById('thingDescription').value;
    const thingProperties = parseJSONField(document.getElementById('thingProperties').value);

    const locationName = document.getElementById('locationName').value;
    const locationDescription = document.getElementById('locationDescription').value;
    const locationProperties = parseJSONField(document.getElementById('locationProperties').value);
    const locationType = document.getElementById('locationType').value;
    const locationLongitude = parseFloat(document.getElementById('locationLongitude').value);
    const locationLatitude = parseFloat(document.getElementById('locationLatitude').value);

    // Collect datastreams
    const datastreams = [];
    document.querySelectorAll('.datastream-item').forEach(item => {
        const name = item.querySelector('.ds-name').value;
        const description = item.querySelector('.ds-description').value;
        const observationType = item.querySelector('.ds-observation-type').value;
        const unitName = item.querySelector('.ds-unit-name').value;
        const unitSymbol = item.querySelector('.ds-unit-symbol').value;
        const unitDefinition = item.querySelector('.ds-unit-definition').value;
        const observedAreaType = item.querySelector('.ds-observed-area-type').value;
        const observedAreaCoords = parseCoordinates(item.querySelector('.ds-observed-area-coords').value);
        const observedProperty = item.querySelector('.ds-observed-property').value;

        const unit = {
            name: unitName,
            definition: unitDefinition
        };
        if (unitSymbol && unitSymbol.trim() !== '') {
            unit.symbol = unitSymbol;
        } else {
            unit.symbol = null;
        }

        datastreams.push({
            name,
            description,
            observationType,
            unitOfMeasurement: unit,
            observedArea: {
                type: observedAreaType,
                coordinates: observedAreaCoords
            },
            phenomenon_time: null,
            result_time: null,
            properties: null,
            observedProperty,
            sensorName,
            thingName
        });
    });

    // Collect observedProperties
    const observedProperties = {};
    document.querySelectorAll('.observed-property-item').forEach(item => {
        const name = item.querySelector('.op-name').value;
        const definition = item.querySelector('.op-definition').value;
        const description = item.querySelector('.op-description').value;
        observedProperties[name] = {
            name,
            definition,
            description,
            properties: null
        };
    });

    return {
        sensor: {
            key: sensorKey,
            name: sensorName,
            description: sensorDescription,
            metadata: sensorMetadata === 'none' ? 'none' : sensorMetadata,
            encodingType: sensorEncodingType,
            properties: sensorProperties
        },
        thing: {
            name: thingName,
            description: thingDescription,
            properties: thingProperties
        },
        location: {
            name: locationName,
            description: locationDescription,
            properties: locationProperties,
            type: locationType,
            coordinates: [locationLongitude, locationLatitude]
        },
        datastreams,
        observedProperties
    };
}

function generateYAML(data) {
    const yaml = {};
    
    // Sensors section
    yaml.sensors = {};
    yaml.sensors[data.sensor.key] = {
        name: data.sensor.name,
        description: data.sensor.description,
        metadata: data.sensor.metadata,
        encodingType: data.sensor.encodingType,
        properties: data.sensor.properties,
        iot_links: {
            datastreams: data.datastreams.map(ds => ds.name)
        }
    };

    // Things section
    yaml.things = {};
    yaml.things[data.thing.name] = {
        name: data.thing.name,
        description: data.thing.description,
        properties: data.thing.properties,
        iot_links: {
            datastreams: data.datastreams.map(ds => ds.name),
            locations: [data.location.name]
        }
    };

    // Locations section
    yaml.locations = {};
    yaml.locations[data.location.name] = {
        name: data.location.name,
        description: data.location.description,
        properties: data.location.properties,
        encodingType: 'application/geo+json',
        location: {
            type: data.location.type,
            coordinates: data.location.coordinates
        },
        iot_links: {
            things: [data.thing.name]
        }
    };

    // Datastreams section
    yaml.datastreams = {};
    data.datastreams.forEach(ds => {
        yaml.datastreams[ds.name] = {
            name: ds.name,
            description: ds.description,
            observationType: ds.observationType,
            unitOfMeasurement: ds.unitOfMeasurement,
            observedArea: ds.observedArea,
            phenomenon_time: ds.phenomenon_time,
            result_time: ds.result_time,
            properties: ds.properties,
            iot_links: {
                observedProperties: [ds.observedProperty],
                sensors: [ds.sensorName],
                things: [ds.thingName]
            }
        };
    });

    // ObservedProperties section
    yaml.observedProperties = data.observedProperties;

    return yaml;
}

function validateForm() {
    const requiredFields = [
        'sensorModel', 'sensorKey', 'sensorName', 'sensorDescription', 'sensorEncodingType',
        'thingName', 'thingDescription',
        'locationName', 'locationDescription', 'locationLongitude', 'locationLatitude'
    ];

    for (const fieldId of requiredFields) {
        const field = document.getElementById(fieldId);
        if (!field.value.trim()) {
            field.focus();
            alert(`Please fill in the required field: ${field.previousElementSibling?.textContent || fieldId}`);
            return false;
        }
    }

    // Validate datastreams
    const datastreamItems = document.querySelectorAll('.datastream-item');
    if (datastreamItems.length === 0) {
        alert('Please add at least one datastream.');
        return false;
    }

    for (const item of datastreamItems) {
        const name = item.querySelector('.ds-name').value;
        const description = item.querySelector('.ds-description').value;
        const observedProperty = item.querySelector('.ds-observed-property').value;
        const unitName = item.querySelector('.ds-unit-name').value;
        const unitDefinition = item.querySelector('.ds-unit-definition').value;

        if (!name || !description || !observedProperty || !unitName || !unitDefinition) {
            alert(`Please fill in all required fields for datastream: ${name || 'unnamed'}`);
            item.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return false;
        }

        // Check if observedProperty exists
        const opExists = Array.from(document.querySelectorAll('.op-name')).some(
            op => op.value === observedProperty
        );
        if (!opExists) {
            alert(`ObservedProperty "${observedProperty}" referenced by datastream "${name}" does not exist. Please add it or fix the reference.`);
            return false;
        }
    }

    // Validate coordinates
    const lon = parseFloat(document.getElementById('locationLongitude').value);
    const lat = parseFloat(document.getElementById('locationLatitude').value);
    if (isNaN(lon) || isNaN(lat)) {
        alert('Location coordinates must be valid numbers.');
        return false;
    }
    if (lon < -180 || lon > 180) {
        alert('Longitude must be between -180 and 180.');
        return false;
    }
    if (lat < -90 || lat > 90) {
        alert('Latitude must be between -90 and 90.');
        return false;
    }

    return true;
}

function handlePreview(e) {
    if (e) e.preventDefault();
    if (!validateForm()) return;

    try {
        // Check if js-yaml is loaded
        if (typeof jsyaml === 'undefined' && typeof jsYAML === 'undefined') {
            alert('Error: js-yaml library not loaded. Please ensure you have an internet connection to load the library from CDN.');
            return;
        }

        // Use jsyaml or jsYAML (different versions use different names)
        const yamlLib = typeof jsyaml !== 'undefined' ? jsyaml : jsYAML;

        const data = collectFormData();
        const yaml = generateYAML(data);
        const yamlString = yamlLib.dump(yaml, {
            indent: 2,
            lineWidth: -1,
            quotingType: '"',
            forceQuotes: false,
            sortKeys: false
        });

        // Store YAML string for copying
        document.getElementById('yamlPreview').dataset.yamlContent = yamlString;
        document.getElementById('yamlPreview').querySelector('code').textContent = yamlString;
        document.getElementById('previewModal').classList.add('show');
    } catch (error) {
        console.error('Preview error:', error);
        alert('Error generating preview: ' + error.message);
    }
}

function copyYamlToClipboard() {
    const yamlContent = document.getElementById('yamlPreview').dataset.yamlContent;
    if (!yamlContent) {
        alert('No YAML content to copy. Please generate a preview first.');
        return;
    }

    // Use the Clipboard API if available
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(yamlContent).then(() => {
            const btn = document.getElementById('copyYamlBtn');
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            btn.style.backgroundColor = 'var(--success)';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.backgroundColor = '';
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            fallbackCopyTextToClipboard(yamlContent);
        });
    } else {
        fallbackCopyTextToClipboard(yamlContent);
    }
}

function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            const btn = document.getElementById('copyYamlBtn');
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            btn.style.backgroundColor = 'var(--success)';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.backgroundColor = '';
            }, 2000);
        } else {
            alert('Copy failed. Please manually select and copy the YAML text from the preview.');
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        alert('Copy failed. Please manually select and copy the YAML text from the preview.');
    }
    
    document.body.removeChild(textArea);
}
