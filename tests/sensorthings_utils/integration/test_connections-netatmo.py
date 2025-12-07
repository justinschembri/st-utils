"""Test concrete implementations in connections.py"""

# standard
import json
from pathlib import Path
# external
import lnetatmo
import pytest
# internal
from sensorthings_utils.connections import (
        NetatmoConnection
        )

@pytest.fixture
def bad_netatmo_tokens(tmp_path: Path) -> Path:
    path = tmp_path / "./bad_netatmo_tokens"
    bad_tokens = {
            "client_id": "foo",
            "client_secret":"bar",
            "refresh_token":"foobar"
        }
    path.write_text(json.dumps(bad_tokens))
    return path

@pytest.fixture
def valid_netatmo_connection() -> NetatmoConnection:
    """A valid Netatmo connection with good tokens."""
    return NetatmoConnection(
            "netatmo-test-application", "tokens" 
            )

class TestNetatmoConnectionAuthentication:
    """
    Parent class that tests the NetatmoConnection's basic auth process.
    
    Testing Strategy:
        - *Authentication* as implemented in `_auth()`:
            - good tokens, 
            - bad tokens, 
            - no tokens,
    """
    def test_auth_good_tokens(self, valid_netatmo_connection: NetatmoConnection):
        """Happy path testing: good tokens should return a ClientAuthObject."""
        assert isinstance(valid_netatmo_connection._auth(), lnetatmo.ClientAuth)

    def test_bad_tokens(self, bad_netatmo_tokens):
        """Passing bad tokens."""
        netatmo_connection = NetatmoConnection(
                "netatmo-test-application",
                bad_netatmo_tokens)
        # override this for test:
        netatmo_connection._authentication_file = bad_netatmo_tokens
        assert isinstance(netatmo_connection._auth(), lnetatmo.ClientAuth)

    def test_no_tokens(self):
        """Pass no tokens."""
        with pytest.raises(TypeError):
            NetatmoConnection("netatmo-test-application") #type: ignore


class TestNetatmoPulling:
    """
    Parent class that tests the actual data pulling. Requires valid tokens!

    Valid netatmo tokens needed at: 
        `/deployment/secrets/tokens/netatmo-testing.json`
    
    Testing Strategy:
        - *Pulling* as implemented in `_data_pulling()`:
            - basic data arrival, type and structure

    """
    @pytest.mark.real
    def test_basic_pulling(self, valid_netatmo_connection: NetatmoConnection):
        """Happy path testing: data should arrive, check structure too."""
        application_payload = valid_netatmo_connection._pull_data()
        assert application_payload is not None
        assert isinstance(application_payload, list) 

