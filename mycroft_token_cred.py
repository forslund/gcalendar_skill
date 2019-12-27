"""
oauth2client token credentials class for updating token through the mycroft
backend as needed.
"""

from requests import HTTPError

from mycroft.api import DeviceApi
from oauth2client import client


class MycroftTokenCredentials(client.AccessTokenCredentials):
    def __init__(self, cred_id):
        self.cred_id = cred_id
        d = self.get_credentials()
        super().__init__(d['access_token'], d['user_agent'])

    def get_credentials(self):
        """Get credentials through backend.

        Will do a single retry for if an HTTPError occurs.

        Returns:
            dict with data received from backend
        """
        retry = False
        try:
            d = DeviceApi().get_oauth_token(self.cred_id)
        except HTTPError:
            retry = True
        if retry:
            d = DeviceApi().get_oauth_token(self.cred_id)
        return d

    def _refresh(self, http):
        """Override to handle refresh through mycroft backend."""
        d = self.get_credentials()
        self.access_token = d['access_token']
