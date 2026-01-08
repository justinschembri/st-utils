// Configuration and constants

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

