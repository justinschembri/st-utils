// Global application state
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

