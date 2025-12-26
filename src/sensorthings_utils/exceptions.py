class UnpackError(Exception):
    """Parent exception for sensor uplink message unpack failures."""
    
class MissingPayloadKeysError(UnpackError):
    """Failed to unpack the uplink message due to missing keys."""

class UnregisteredSensorError(Exception):
    """Receieved a message from an unregistered sensor."""

class FailedSensorConfigValidation(Exception):
    """Failure to validate a sensor conifiguration."""
