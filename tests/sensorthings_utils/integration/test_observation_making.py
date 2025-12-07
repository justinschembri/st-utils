"""Test the processes around making observations and pushing to FROST."""
# stdlib
from datetime import datetime
# external
import pytest
# internal
from sensorthings_utils.frost import make_frost_object
from sensorthings_utils.sensor_things.core import Observation

@pytest.fixture
def valid_observation() -> Observation:
    return Observation(
            result=100,
            phenomenonTime=datetime(year=2025, month=1, day=1)
            )

def test_double_observation(valid_observation) -> None:
    """Test if pushing two identical observations ..."""
    make_frost_object
