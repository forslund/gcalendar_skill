from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_file_handler
from mycroft.messagebus.message import Message
from mycroft.util.log import LOG

import httplib2
from googleapiclient import discovery
from oauth2client import client

import sys
from tzlocal import get_localzone
from datetime import datetime, timedelta
from mycroft.util.parse import extract_datetime
from mycroft.api import DeviceApi
from requests import HTTPError
from parsedatetime import Calendar
import time

UTC_TZ = u'+00:00'

def is_gcalendar_reminder(event):
    if 'reminders' in event and event['reminders'].get('useDefault') == False:
        for override in event['reminders']['overrides']:
            if override['method'] == 'popup':
                return True
    return False


def nice_time(dt, lang="en-us", speech=True, use_24hour=False,
              use_ampm=False):
    """
    Format a time to a comfortable human format

    For example, generate 'five thirty' for speech or '5:30' for
    text display.

    Args:
        dt (datetime): date to format (assumes already in local timezone)
        lang (str): code for the language to use
        speech (bool): format for speech (default/True) or display (False)=Fal
        use_24hour (bool): output in 24-hour/military or 12-hour format
        use_ampm (bool): include the am/pm for 12-hour format
    Returns:
        (str): The formatted time string
    """

    if use_24hour:
        # e.g. "03:01" or "14:22"
        string = dt.strftime("%H:%M")
    else:
        if use_ampm:
            # e.g. "3:01 AM" or "2:22 PM"
            string = dt.strftime("%I:%M %p")
        else:
            # e.g. "3:01" or "2:22"
            string = dt.strftime("%I:%M")
        if string[0] == '0':
            string = string[1:]  # strip leading zeros
        return string

    if not speech:
        return string

    # Generate a speakable version of the time
    if use_24hour:
        speak = ""

        # Either "0 8 hundred" or "13 hundred"
        if string[0] == '0':
            if string[1] == '0':
                speak = "0 0"
            else:
                speak = "0 " + string[1]
        else:
            speak += string[0:2]

        if string[3] == '0':
            if string[4] == '0':
                # Ignore the 00 in, for example, 13:00
                speak += " oclock"  # TODO: Localize
            else:
                speak += " o " + string[4]  # TODO: Localize
        else:
            if string[0] == '0':
                speak += " " + string[3:5]
            else:
                # TODO: convert "23" to "twenty three" in helper method

                # Mimic is speaking "23 34" as "two three 43" :(
                # but it does say "2343" correctly.  Not ideal for general
                # TTS but works for the moment.
                speak += ":" + string[3:5]

        return speak
    else:
        if lang.startswith("en"):
            if dt.hour == 0 and dt.minute == 0:
                return "midnight"  # TODO: localize
            if dt.hour == 12 and dt.minute == 0:
                return "noon"  # TODO: localize
            # TODO: "half past 3", "a quarter of 4" and other idiomatic times

            # lazy for now, let TTS handle speaking "03:22 PM" and such
        return string


def is_today(d):
    return d.date() == datetime.today().date()


def is_tomorrow(d):
    return d.date() == datetime.today().date() + timedelta(days=1)


def is_wholeday_event(e):
    return 'dateTime' not in e['start']

def remove_tz(string):
    return string[:-6]

class MycroftTokenCredentials(client.AccessTokenCredentials):
    def __init__(self, cred_id):
        self.cred_id = cred_id
        d = self.get_credentials()
        super(MycroftTokenCredentials, self).__init__(d['access_token'],
                                                      d['user_agent'])

    def get_credentials(self):
        """
            Get credentials through backend. Will do a single retry for
            if an HTTPError occurs.

            Returns: dict with data received from backend
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
        """
            Override to handle refresh through mycroft backend.
        """
        d = self.get_credentials()
        self.access_token = d['access_token']


class GoogleCalendarSkill(MycroftSkill):
    def __init__(self):
        super(GoogleCalendarSkill, self).__init__('Google Calendar')
        if 'reminders' not in self.settings:
            self.settings['reminders'] = []
        self.gcal_reminders = []

    @property
    def use_24hour(self):
        return self.config_core.get('time_format') == 'full'

    def __calendar_connect(self, msg=None):
        argv = sys.argv
        sys.argv = []
        try:
            # Get token for this skill (id 4)
            self.credentials = MycroftTokenCredentials(4)
            LOG.info('Credentials: {}'.format(self.credentials))
            http = self.credentials.authorize(httplib2.Http())
            self.service = discovery.build('calendar', 'v3', http=http)
            sys.argv = argv

            # Load calendars
            self.__load_calendars()
            self.__register_intents()
            self.__update_reminders()
            self.cancel_scheduled_event('calendar_connect')
        except HTTPError:
            LOG.info('No Credentials available')
            pass

    def __load_calendars(self):
        cal_list = self.service.calendarList().list().execute()
        self.calendars = {format(cal['summary'].encode('utf-8')): cal
                          for cal in cal_list['items']}

        # Create mycroft reminders calendar if it doesn't exist
        if 'Mycroft Reminders' not in self.calendars:
            data = {
                'summary': 'Mycroft Reminders',
                'timeZone': 'UTC'
            }
            new_calendar = self.service.calendars().insert(body=data).execute()
            self.caledars[new_calendar['summary']] = new_calendar

    def __register_intents(self):
        LOG.info('Loading calendar intents')
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

    def __update_reminders(self):
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events = self.get_upcoming_events(now, calendar='Mycroft Reminders')
        self.gcal_reminders = [e for e in events if is_gcalendar_reminder(e)]
        LOG.info(self.gcal_reminders)

    def __check_reminder(self, message):
        now = time.time()
        handled_reminders = []
        for r in self.settings['reminders']:
            if now > r[1]:
                self.speak(r[0])
                handled_reminders.append(r)

        for r in handled_reminders:
            self.settings['reminders'].remove(r)

        # Check the gcalendar reminer events
        handled_events = []
        for event in self.gcal_reminders:
            LOG.info(event)
            start = event['start'].get('dateTime')
            if not start:
                continue
            d = datetime.strptime(remove_tz(start), '%Y-%m-%dT%H:%M:%S')
            since_epoch = time.mktime(d.timetuple())
            if now > since_epoch:
                self.speak(event['summary'])
                handled_events.append(event)

        for r in handled_events:
            self.gcal_reminders.remove(r)

    def initialize(self):
        LOG.info('GCALENDAR SKILL INITIALIzing!')
        self.schedule_event(self.__calendar_connect, datetime.now(),
                                      name='calendar_connect')
        self.schedule_repeating_event(self.__check_reminder, datetime.now(),
                                      120, name='reminder')
        LOG.info('GCALENDAR SKILL INITIALIZED!')

    def get_upcoming_events(self, utc_time, max_results=10, calendar=None):
        """Get upcoming events from the calendar.

        Args:
            utc_time: (somthing) Start time for retrieval
            max_results: (int) Maximum number of results, defaults to 10.
            calendar: (str) Name of calendar to fetch from, defaults to the
                primary calendar.
        Returns:
            (list) list of calendar events.
        """
        calendar = self.calendars[calendar]['id'] if calendar else 'primary'

        eventsResult = self.service.events().list(
            calendarId='primary', timeMin=utc_time, maxResults=max_results,
            singleEvents=True, orderBy='startTime').execute()
        return eventsResult.get('items', [])

    def get_next(self, msg=None):
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events = self.get_upcoming_events(now)
        if not events:
            self.speak_dialog('NoNextAppointments')
        else:
            event = events[0]
            LOG.debug(event)
            if not is_wholeday_event(event):
                start = event['start'].get('dateTime')
                d = datetime.strptime(remove_tz(start), '%Y-%m-%dT%H:%M:%S')
                starttime = nice_time(d, self.lang, True, self.use_24hour,
                                      True)
                startdate = d.strftime('%-d %B')
            else:
                start = event['start']['date']
                d = datetime.strptime(start, '%Y-%m-%d')
                startdate = d.strftime('%-d %B')
                starttime = None
            # Speak result
            if starttime is None:
                if d.date() == datetime.today().date():
                    data = {'appointment': event['summary']}
                    self.speak_dialog('NextAppointmentWholeToday', data)
                elif is_tomorrow(d):
                    data = {'appointment': event['summary']}
                    self.speak_dialog('NextAppointmentWholeTomorrow', data)
                else:
                    data = {'appointment': event['summary'],
                            'date': startdate}
                    self.speak_dialog('NextAppointmentWholeDay', data)
            elif d.date() == datetime.today().date():
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
            d = datetime.strptime(start.split('.')[0], '%Y-%m-%dT%H:%M:%SZ')
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
                    d = datetime.strptime(remove_tz(start),
                                             '%Y-%m-%dT%H:%M:%S')
                    starttime = nice_time(d, self.lang, True, self.use_24hour,
                                          True)
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

    def add_calendar_event(self, title, start_time, end_time, summary=None,
                           reminder=None):
        start_time = start_time.strftime('%Y-%m-%dT%H:%M:00')
        stop_time = end_time.strftime('%Y-%m-%dT%H:%M:00')
        cal_id = 'primary'
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
        if reminder:
            cal_id = self.calendars['Mycroft Reminders']['id']
            event['reminders'] = {
                'useDefault': False,
                'overrides': [
                    {
                        'method': 'popup',
                        'minutes': 15
                    }
                ]
            }
        data = {'appointment': title}
        try:
            self.service.events()\
                .insert(calendarId=cal_id, body=event).execute()
            self.speak_dialog('AddSucceeded', data)
        except Exception as e:
            LOG.exception(e)
            self.speak_dialog('AddFailed', data)

    @intent_file_handler('ReminderAt.intent')
    def add_new_reminder(self, msg=None):
        reminder = msg.data.get('reminder', None)
        reminder_time = extract_datetime(msg.data['utterance'])[0] # start time
        LOG.info(reminder_time)
        # convert to UTC
        self.speak_dialog('SavingReminder',
                          {'timedate': nice_time(reminder_time)})

        if not self.service:
            self.__save_reminder_local(reminder, reminder_time)
        else:
            self.__save_reminder_gcalendar(reminder, reminder_time)

    @intent_file_handler('ReminderIn.intent')
    def add__reminder_in(self, msg=None):
        reminder = msg.data.get('reminder', None)
        reminder_time = Calendar().parseDT(msg.data['timedate'])[0]
        LOG.info(reminder_time)
        # convert to UTC
        self.speak_dialog('SavingReminder',
                          {'timedate': nice_time(reminder_time)})
        if not self.service:
            self.__save_reminder_local(reminder, reminder_time)
        else:
            self.__save_reminder_gcalendar(reminder, reminder_time)

    def __save_reminder_local(self, reminder, reminder_time):
        since_epoch = time.mktime(reminder_time.timetuple())
        self.settings['reminders'].append((reminder, since_epoch))

    def __save_reminder_gcalendar(self, reminder, reminder_time):
        LOG.info('saving {} to gcalendar at {}'.format(reminder, reminder_time))
        tz_offset = self.location['timezone']['offset']
        utc_time = reminder_time - timedelta(seconds=tz_offset / 1000)
        self.add_calendar_event(reminder, utc_time,
                                utc_time + timedelta(minutes=30),
                                reminder=True)


def create_skill():
    return GoogleCalendarSkill()
