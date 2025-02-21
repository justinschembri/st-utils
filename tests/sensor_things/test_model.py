# standard
import unittest
from pathlib import Path

# external
# internal
from netatmo.sensor_things.extensions import SensorArrangementMap, SensorArrangement


class Test_SensorArrangement(unittest.TestCase):
    MOCK_DATA_PATH = Path("tests/sensor_things/data/70:ee:50:7f:9d:32.yaml")

    def setUp(self) -> None:
        self.sensor_arrangement_map = SensorArrangementMap(self.MOCK_DATA_PATH)
        self.sensor_arrangement = SensorArrangement(self.sensor_arrangement_map)

    def test_instantiation(self) -> None:
        """Test basic instantiation using good data."""
        sensor_arrangement_map = SensorArrangementMap(self.MOCK_DATA_PATH)
        assert isinstance(sensor_arrangement_map, SensorArrangementMap)
