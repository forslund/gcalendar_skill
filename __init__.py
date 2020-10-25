from datetime import datetime, timedelta
from mycroft.util.parse import extract_datetime
from requests import HTTPError
from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_file_handler
from mycroft.util.log import LOG
from mycroft.util.format import nice_time, nice_date
from mycroft.util.time import to_utc

from .mycroft_token_cred import MycroftTokenCredentials
from .calendar_connections import Event, GoogleCalendar, DavCalendar


def is_today(d):
    return d.date() == datetime.today().date()


def is_tomorrow(d):
    return d.date() == datetime.today().date() + timedelta(days=1)


class CalendarSkill(MycroftSkill):
    @property
    def use_24hour(self):
        return self.config_core.get('time_format') == 'full'

    def __calendar_connect(self, msg=None):
        if self.settings.get('username'):
            self.log.info('Setting up CalDav Calendar')
            self.calendar = DavCalendar(self.settings['url'],
                                        self.settings['username'],
                                        self.settings['password'])
            self.register_intents()
        else:
            try:
                # Get token for this skill (id 4)
                self.credentials = MycroftTokenCredentials(4)
                LOG.info('Credentials: {}'.format(self.credentials))
                self.calendar = GoogleCalendar(self.credentials)
                self.register_intents()
                self.cancel_scheduled_event('calendar_connect')
            except HTTPError:
                LOG.info('No Credentials available')
                pass

    def register_intents(self):
        intent = IntentBuilder('GetNextAppointmentIntent')\
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
        self.schedule_event(self.__calendar_connect, datetime.now(),
                            name='calendar_connect')

    def get_next(self, msg=None):
        now = datetime.utcnow()
        events = self.calendar.get_events(now)
        if not events:
            self.speak_dialog('NoNextAppointments')
        else:
            event = events[0]
            LOG.debug(event)
            if not event.is_whole_day:
                starttime = nice_time(event.start_time, self.lang, True,
                                      self.use_24hour, True)
                startdate = nice_date(event.start_time.date())
            else:
                startdate = nice_date(event.start_time.date())
                starttime = None
            # Speak result
            if event.is_whole_day:
                if startdate == datetime.today().date():
                    data = {'appointment': event.title}
                    self.speak_dialog('NextAppointmentWholeToday', data)
                elif is_tomorrow(event.start_time):
                    data = {'appointment': event.title}
                    self.speak_dialog('NextAppointmentWholeTomorrow', data)
                else:
                    data = {'appointment': event.title,
                            'date': startdate}
                    self.speak_dialog('NextAppointmentWholeDay', data)
            elif event.start_time.date() == datetime.today().date():
                data = {'appointment': event.title,
                        'time': starttime}
                self.speak_dialog('NextAppointment', data)
            elif is_tomorrow(event.start_time):
                data = {'appointment': event.title,
                        'time': starttime}
                self.speak_dialog('NextAppointmentTomorrow', data)
            else:
                data = {'appointment': event.title,
                        'time': starttime,
                        'date': startdate}
                self.log.info(data)
                self.speak_dialog('NextAppointmentDate', data)

    def speak_interval(self, start, stop, max_results=None):
        events = self.calendar.get_events(start, stop, max_results)
        if not events:
            LOG.debug(start)
            if is_today(start):
                self.speak_dialog('NoAppointmentsToday')
            elif is_tomorrow(start):
                self.speak_dialog('NoAppointmentsTomorrow')
            else:
                self.speak_dialog('NoAppointments')
        else:
            for e in events:
                if e.is_whole_day:
                    data = {'appointment': e.title}
                    self.speak_dialog('WholedayAppointment', data)
                else:
                    starttime = nice_time(e.start_time, self.lang, True,
                                          self.use_24hour, True)
                    if is_today(e.start_time) or is_tomorrow(e.start_time):
                        data = {'appointment': e.title,
                                'time': starttime}
                        self.speak_dialog('NextAppointment', data)

    def get_day(self, msg=None):
        d = extract_datetime(msg.data['utterance'])[0]
        d = d.replace(hour=0, minute=0, second=1, tzinfo=None)
        d_end = d.replace(hour=23, minute=59, second=59, tzinfo=None)
        self.speak_interval(d, d_end)
        return

    def get_first(self, msg=None):
        d = extract_datetime(msg.data['utterance'])[0]
        d = d.replace(hour=0, minute=0, second=1, tzinfo=None)
        d_end = d.replace(hour=23, minute=59, second=59, tzinfo=None)
        self.speak_interval(d, d_end, max_results=1)

    @property
    def utc_offset(self):
        return timedelta(seconds=self.location['timezone']['offset'] / 1000)

    @intent_file_handler('Schedule.intent')
    def add_new(self, message=None):
        title = self.get_response('whatsTheNewEvent')
        start = self.get_response('whenDoesItStart')
        end = self.get_response('whenDoesItEnd')
        if title and start and end:
            st = extract_datetime(start)
            et = extract_datetime(end)
            if st and et:
                st = to_utc(st[0])
                et = to_utc(et[0])
                data = {'appointment': title}
                event = Event(title, st, et)
                if self.calendar.add_event(event):
                    self.speak_dialog('AddSucceeded', data)
                else:
                    self.speak_dialog('AddFailed', data)

    @intent_file_handler('ScheduleAt.intent')
    def add_new_quick(self, msg=None):
        title = msg.data.get('appointmenttitle', None)
        if title is None:
            self.log.debug("NO TITLE")
            return

        st = extract_datetime(msg.data['utterance'])[0]  # start time
        # convert to UTC
        st = to_utc(st)
        et = st + timedelta(hours=1)

        data = {'appointment': title}
        if self.calendar.add_event(title, st, et):
            self.speak_dialog('AddSucceeded', data)
        else:
            self.speak_dialog('AddFailed', data)


def create_skill():
    return CalendarSkill()
