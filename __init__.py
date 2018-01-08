from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_file_handler
from mycroft.messagebus.message import Message
from mycroft.util.log import LOG

import httplib2
from googleapiclient import discovery

import datetime as dt
import os
from os.path import dirname, abspath
import sys
from tzlocal import get_localzone
from datetime import datetime, timedelta
from mycroft.util.parse import extract_datetime

path = os.path.dirname(sys.modules[__name__].__file__)
sys.path.insert(0, path)

extractdate = __import__('extractdate').extractdate
get_credentials = __import__('google_cred').get_credentials
sys.path.append(abspath(dirname(__file__)))

UTC_TZ = u'+00:00'
def is_today(d):
    return d.date() == dt.datetime.today().date()


def is_tomorrow(d):
    return d.date() == dt.datetime.today().date() + dt.timedelta(days=1)


def is_wholeday_event(e):
    return 'dateTime' not in e['start']

def remove_tz(string):
    return string[:-6]

class GoogleCalendarSkill(MycroftSkill):
    def __init__(self):
        super(GoogleCalendarSkill, self).__init__('Google Calendar')

    def __calendar_connect(self, msg=None):
        argv = sys.argv
        sys.argv = []
        self.credentials = get_credentials()
        http = self.credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)
        sys.argv = argv

        self.load_data_files(dirname(__file__))
        intent = IntentBuilder('GetNextAppointment')\
            .require('NextKeyword')\
            .one_of('AppointmentKeyword', 'ScheduleKeyword')\
            .build()
        self.register_intent(intent, self.get_next)

        intent = IntentBuilder('GetDaysAppointmentsIntent')\
            .require('QueryKeyword')\
            .one_of('AppointmentKeyword', 'ScheduleKeyword')\
            .build()
        self.register_intent(intent, self.get_day)

        intent = IntentBuilder('GetFirstAppointmentIntent')\
            .one_of('AppointmentKeyword', 'ScheduleKeyword')\
            .require('FirstKeyword')\
            .build()
        self.register_intent(intent, self.get_first)

    def initialize(self):
        self.load_data_files(dirname(__file__))
        self.schedule_event(self.__calendar_connect, datetime.now(),
                                      name='calendar_connect')

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
            LOG.debug(event)
            if not is_wholeday_event(event):
                start = event['start'].get('dateTime')
                d = dt.datetime.strptime(remove_tz(start), '%Y-%m-%dT%H:%M:%S')
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
            maxResults=max_results).execute()
        events = eventsResult.get('items', [])
        if not events:
            LOG.debug(start)
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
                    d = dt.datetime.strptime(remove_tz(start),
                                             '%Y-%m-%dT%H:%M:%S')
                    starttime = d.strftime('%H . %M')
                    if is_today(d) or is_tomorrow(d) or True:
                        data = {'appointment': e['summary'],
                                'time': starttime}
                        self.speak_dialog('NextAppointment', data)

    def get_day(self, msg=None):
        d = extract_datetime(msg.data['utterance'])[0]
        d = d.replace(hour=0, minute=0, second=1)
        d_end = d.replace(hour=23, minute=59, second=59)
        d = d.isoformat() + 'Z'
        d_end = d_end.isoformat() + 'Z'
        self.speak_interval(d, d_end)
        return

    def get_first(self, msg=None):
        d = extract_datetime(msg.data['utterance'])[0]
        d = d.replace(hour=0, minute=0, second=1)
        d_end = d.replace(hour=23, minute=59, second=59)
        d = d.isoformat() + 'Z'
        d_end = d_end.isoformat() + 'Z'
        self.speak_interval(d, d_end, max_results=1)

    @intent_file_handler('Schedule')
    def add_new(self, message=None):
        title = self.get_response('what\'s the new event')
        start = self.get_response('when does it start')
        end = self.get_response('when does it end')
        st = extract_datetime(start)
        et = extract_datetime(end)
        self.add_calendar_event(title, start_time=st, end_time=et)

    @intent_file_handler('ScheduleAt.intent')
    def add_new_quick(self, msg=None):
        title = msg.data.get('appointmenttitle', None)
        if title is None:
            print "NO TITLE"
            return

        st = extract_datetime(msg.data['utterance'])[0] # start time
        # convert to UTC
        st -= timedelta(seconds=self.location['timezone']['offset'] / 1000)
        et = st + timedelta(hours=1)
        self.add_calendar_event(title, st, et)

    def add_calendar_event(self, title, start_time, end_time, summary=None):
        print type(start_time)
        start_time = start_time.strftime('%Y-%m-%dT%H:%M:00')
        stop_time = end_time.strftime('%Y-%m-%dT%H:%M:00')
        stop_time += UTC_TZ
        event = {}
        event['summary'] = title
        event['start'] = {
            'dateTime': start_time,
            'timeZone': 'UTC'
        }
        event['end'] = {
            'dateTime': stop_time,
            'timeZone': 'UTC'
        }
        data = {'appointment': title}
        try:
            self.service.events()\
                .insert(calendarId='primary', body=event).execute()
            self.speak_dialog('AddSucceeded', data)
        except:
            self.speak_dialog('AddFailed', data)


def create_skill():
    return GoogleCalendarSkill()
