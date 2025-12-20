"""Test sensor_things/extensions.py"""

# standard
import logging
from pathlib import Path

# external
import pytest

# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.config import TEST_DATA_DIR


@pytest.fixture
def good_config():
    path = TEST_DATA_DIR / "complete_sensor_config.yaml"
    good_config_file = SensorConfig(path)
    return good_config_file


@pytest.fixture
def bad_sensor_name(caplog):
    """A config where the sensor object key and sensor name do not match."""
    path = TEST_DATA_DIR / "bad_sensor_name.yaml"
    bad_config_file = SensorConfig(path)
    logs = caplog.text
    return bad_config_file, logs


class TestSensorConfig:
    """Test the SensorConfig class."""

    def test_good_config_validates(self, good_config: SensorConfig):
        assert good_config.check_validity == True

    def test_bad_sensor_name(self, bad_sensor_name: SensorConfig):
        bad_config, logs = bad_sensor_name
        assert bad_config.is_valid == False
        assert "does not match its primary key" in logs
