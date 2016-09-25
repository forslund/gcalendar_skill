import sys
from os.path import dirname, abspath
sys.path.append(abspath(dirname(__file__)))

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
from os.path import dirname

from mycroft.util.log import getLogger
logger = getLogger(dirname(__name__))

__author__ = 'forslund'

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
    print "getting home"
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    print "checking for cached credentials"
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
        print 'Storing credentials to ' + credential_path
    return credentials


class GoogleCalendarSkill(MycroftSkill):
    def __init__(self):
        super(GoogleCalendarSkill, self).__init__('Google Calendar')
    

    def _calendar_connect(self, msg=None):
        print "getting credentials"
        self.credentials = get_credentials()
        http = self.credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)
        intent = IntentBuilder('GetNextAppointment')\
            .require('NextKeyword')\
            .require('AppointmentKeyword')\
            .build()
        self.register_intent(intent, self.get_next)

        intent = IntentBuilder('GetTodaysAppointmentsIntent')\
            .require('TodayKeyword')\
            .require('AppointmentKeyword')\
            .build()
        self.register_intent(intent, self.get_today)

        intent = IntentBuilder('GetAppointmentsForDayIntent')\
            .require('WeekdayKeyword') \
            .require('AppointmentKeyword') \
            .build()
        self.register_intent(intent, self.get_day)

    def initialize(self):
        self.load_data_files(dirname(__file__))
        self.emitter.on(self.name + '.calendar_connect',
                        self._calendar_connect)
        self.emitter.emit(Message(self.name + '.calendar_connect'))

    def get_next(self, msg=None):
        now = dt.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        eventsResult = self.service.events().list(
            calendarId='primary', timeMin=now, maxResults=10, singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        if not events:
            self.speak('No upcoming events scheduled')
        else:
            event = events[0]
            start = event['start'].get('dateTime', event['start'].get('date'))
            d = dt.datetime.strptime(start.split('+')[0], '%Y-%m-%dT%H:%M:%S')
            starttime = d.strftime('%H %M')
            if d.date() == dt.datetime.today().date():
                self.speak(event['summary'] + ' at ' + starttime)
            else:
                startdate = d.strftime('%A the %-d of %B')
                self.speak(event['summary'] + ' at ' + starttime + startdate)

    def get_today(self, msg=None):
        now = dt.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        day_end = dt.datetime.utcnow().replace(hour=23, minute=59, second=59)
        day_end = day_end.isoformat() + 'Z'
        eventsResult = self.service.events().list(
            calendarId='primary', timeMin=now, timeMax=day_end,
            singleEvents=True, orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        if not events:
            self.speak('No upcoming events scheduled')
        else:
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                d = dt.datetime.strptime(start[:-6], '%Y-%m-%dT%H:%M:%S')
                starttime = d.strftime('%H %M')
                if d.date() == dt.datetime.today().date():
                    self.speak(e['summary'] + ' at ' + starttime)

    def get_day(self, msg=None):
        return

def create_skill():
    return GoogleCalendarSkill()
