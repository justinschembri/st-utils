# standard
import unittest

# external
from lnetatmo import ClientAuth

# internal
from sensorthings_utils.config import netatmo_auth_check


class Test_AuthCheck(unittest.TestCase):
    def test_failure(self):
        authentication = ClientAuth(
            clientId="BadID", clientSecret="BadSecret", refreshToken="BadToken"
        )
        self.assertFalse(netatmo_auth_check(authentication))

    def test_success(self):
        authentication = ClientAuth()
        self.assertTrue(netatmo_auth_check(authentication))
