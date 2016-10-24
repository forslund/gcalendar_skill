import os

import httplib2
from googleapiclient import discovery
import oauth2client
from oauth2client import file
from oauth2client import client
from oauth2client import tools
from oauth2client.client import OAuth2WebServerFlow


CID = \
    "1090750226387-sh7u7flhs8kja784eetfl779ukuu52m6.apps.googleusercontent.com"
SSTRING = "gxJdIGxWtOc8Fk4I0CHmC8XY"
SCOPES = 'https://www.googleapis.com/auth/calendar'

APP_NAME = 'Google Calendar Mycroft Skill'
VERSION = '0.1dev'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    print('checking for cached credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-skill.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        credentials = tools.run_flow(
            OAuth2WebServerFlow(client_id=CID,
                                client_secret=SSTRING,
                                scope=SCOPES,
                                user_agent=APP_NAME + '/' + VERSION),
            store)
        print('Storing credentials to ' + credential_path)
    else:
        print('Loaded credentials from store')
    return credentials



