from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.messagebus.message import Message

import httplib2
from googleapiclient import discovery
import oauth2client
from oauth2client import file
from oauth2client import client
from oauth2client import tools
from oauth2client.client import OAuth2WebServerFlow

import datetime as dt
import os
from os.path import dirname, abspath
import sys
from mycroft.util.log import getLogger

from parsedatetime import Calendar

cal = Calendar()

logger = getLogger('gcalendar_skill')
sys.path.append(abspath(dirname(__file__)))


__author__ = 'forslund'


def is_today(d):
    return d.date() == dt.datetime.today().date()


def is_tomorrow(d):
    return d.date() == dt.datetime.today().date() + dt.timedelta(days=1)

CID = \
    "1090750226387-sh7u7flhs8kja784eetfl779ukuu52m6.apps.googleusercontent.com"
SSTRING = "gxJdIGxWtOc8Fk4I0CHmC8XY"
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'

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
    logger.info('checking for cached credentials')
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
        logger.info('Storing credentials to ' + credential_path)
    else:
        logger.info('Loaded credentials from store')
    return credentials


class GoogleCalendarSkill(MycroftSkill):
    def __init__(self):
        super(GoogleCalendarSkill, self).__init__('Google Calendar')

    def _calendar_connect(self, msg=None):
        argv = sys.argv
        sys.argv = []
        self.credentials = get_credentials()
        http = self.credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)
        sys.argv = argv

        self.load_data_files(dirname(__file__))
        intent = IntentBuilder('GetNextAppointment')\
            .require('NextKeyword')\
            .require('AppointmentKeyword')\
            .build()
        self.register_intent(intent, self.get_next)

        intent = IntentBuilder('GetDaysAppointmentsIntent')\
            .require('AppointmentKeyword')\
            .build()
        self.register_intent(intent, self.get_day)

    def initialize(self):
        self.load_data_files(dirname(__file__))
        self.emitter.on(self.name + '.calendar_connect',
                        self._calendar_connect)
        self.emitter.emit(Message(self.name + '.calendar_connect'))

    def get_next(self, msg=None):
        now = dt.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        eventsResult = self.service.events().list(
            calendarId='primary', timeMin=now, maxResults=10,
            singleEvents=True, orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        if not events:
            self.speak_dialog('NoNextAppointments')
        else:
            event = events[0]
            start = event['start'].get('dateTime', event['start'].get('date'))
            d = dt.datetime.strptime(start.split('+')[0], '%Y-%m-%dT%H:%M:%S')
            starttime = d.strftime('%H . %M')
            startdate = d.strftime('%-m %B')
            if d.date() == dt.datetime.today().date():
                data = {'appointment': event['summary'],
                        'time': starttime}
                self.speak_dialog('NextAppointment', data)
            elif is_tomorrow(d):
                data = {'appointment': event['summary'],
                        'time': starttime}
                self.speak_dialog('NextAppointmentTomorrow', data)
            else:
                data = {'appointment': event['summary'],
                        'time': starttime,
                        'date': startdate}
                self.speak_dialog('NextAppointmentDate', data)

    def speak_interval(self, start, stop):
        eventsResult = self.service.events().list(
            calendarId='primary', timeMin=start, timeMax=stop,
            singleEvents=True, orderBy='startTime').execute()
        events = eventsResult.get('items', [])
        if not events:
            print start
            d = dt.datetime.strptime(start.split('.')[0], '%Y-%m-%dT%H:%M:%SZ')
            if is_today(d):
                self.speak_dialog('NoAppointmentsToday')
            elif is_tomorrow(d):
                self.speak_dialog('NoAppointmentsTomorrow')
            else:
                self.speak_dialog('NoAppointments')
        else:
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                d = dt.datetime.strptime(start[:-6], '%Y-%m-%dT%H:%M:%S')
                starttime = d.strftime('%H . %M')
                if is_today(d) or is_tomorrow(d) or True:
                    data = {'appointment': e['summary'],
                            'time': starttime}
                    self.speak_dialog('NextAppointment', data)

    def get_day(self, msg=None):
        d = cal.parseDT(msg.metadata['utterance'])[0]
        d = d.replace(hour=0, minute=0, second=1)
        d_end = d.replace(hour=23, minute=59, second=59)
        d = d.isoformat() + 'Z'
        d_end = d_end.isoformat() + 'Z'
        self.speak_interval(d, d_end)
        return


def create_skill():
    return GoogleCalendarSkill()
