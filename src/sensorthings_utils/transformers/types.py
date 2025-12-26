"""Result types from unpacking and transforming protocols."""
#standard
#external
from enum import Enum
#internal

SensorID = str

class ObservedProperties(Enum):

    PHENOMENON_TIME = "phenomenon_time"
    BATTERY_LEVEL = "battery_level"
    HUMIDITY_INDOOR = "humidity"
    CO2_INDOOR = "co2"
    TEMP_IN= "temperature_indoor"
    LIGHT_LVL_IN= "light_level"
    PIR= "passive_infrared"
    PM10= "particulate_matter_10"
    PM_2PT5= "particulate_matter_2_5"
    G_PRESSURE_IN= "gauge_pressure"
    A_PRESSURE_IN= "absolute_pressure"
    NOISE_IN="noise"
    TVOC= "total_volatile_organic_compounds"

class SupportedSensors(Enum):
    
    MILESIGHT_AM103L = "milesight.am103l"
    MILESIGHT_AM308L = "milesight.am308l"
    NETATMO_NWS03 = "netatmo.nws03"

