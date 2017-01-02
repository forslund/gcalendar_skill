from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.messagebus.message import Message

import httplib2
from googleapiclient import discovery

import datetime as dt
import os
from os.path import dirname, abspath
import sys
from mycroft.util.log import getLogger

path = os.path.dirname(sys.modules[__name__].__file__)
sys.path.insert(0, path)

extractdate = __import__('extractdate').extractdate
get_credentials = __import__('google_cred').get_credentials
logger = getLogger('gcalendar_skill')
sys.path.append(abspath(dirname(__file__)))


__author__ = 'forslund'


def is_today(d):
    return d.date() == dt.datetime.today().date()


def is_tomorrow(d):
    return d.date() == dt.datetime.today().date() + dt.timedelta(days=1)

def is_wholeday_event(e):
    return 'dateTime' not in e['start']


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

        intent = IntentBuilder('GetFirstAppointmentIntent')\
            .require('AppointmentKeyword')\
            .require('FirstKeyword')\
            .build()
        self.register_intent(intent, self.get_first)

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
            print event
            if not is_wholeday_event(event):
                start = event['start'].get('dateTime')
                d = dt.datetime.strptime(start.split('+')[0], '%Y-%m-%dT%H:%M:%S')
                starttime = d.strftime('%H . %M')
                startdate = d.strftime('%-d %B')
            else:
                start = event['start']['date']
                d = dt.datetime.strptime(start, '%Y-%m-%d')
                startdate = d.strftime('%-d %B')
                starttime = None
            # Speak result
            if starttime is None:
                if d.date() == dt.datetime.today().date():
                    data = {'appointment': event['summary']}
                    self.speak_dialog('NextAppointmentWholeToday', data)
                elif is_tomorrow(d):
                    data = {'appointment': event['summary']}
                    self.speak_dialog('NextAppointmentWholeTomorrow', data)
                else:
                    data = {'appointment': event['summary'],
                            'date': startdate}
                    self.speak_dialog('NextAppointmentWholeDay', data)
            elif d.date() == dt.datetime.today().date():
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

    def speak_interval(self, start, stop, max_results=None):
        eventsResult = self.service.events().list(
            calendarId='primary', timeMin=start, timeMax=stop,
            singleEvents=True, orderBy='startTime',
            maxResults = max_results).execute()
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
                if is_wholeday_event(e):
                    data = {'appointment': e['summary']}
                    self.speak_dialog('WholedayAppointment', data)
                else:
                    start = e['start'].get('dateTime', e['start'].get('date'))
                    d = dt.datetime.strptime(start[:-6], '%Y-%m-%dT%H:%M:%S')
                    starttime = d.strftime('%H . %M')
                    if is_today(d) or is_tomorrow(d) or True:
                        data = {'appointment': e['summary'],
                                'time': starttime}
                        self.speak_dialog('NextAppointment', data)

    def get_day(self, msg=None):
        d = extractdate(msg.data['utterance'])
        d = d.replace(hour=0, minute=0, second=1)
        d_end = d.replace(hour=23, minute=59, second=59)
        d = d.isoformat() + 'Z'
        d_end = d_end.isoformat() + 'Z'
        self.speak_interval(d, d_end)
        return

    def get_first(self, msg=None):
        d = extractdate(msg.data['utterance'])
        d = d.replace(hour=0, minute=0, second=1)
        d_end = d.replace(hour=23, minute=59, second=59)
        d = d.isoformat() + 'Z'
        d_end = d_end.isoformat() + 'Z'
        self.speak_interval(d, d_end, max_results=1)


def create_skill():
    return GoogleCalendarSkill()
