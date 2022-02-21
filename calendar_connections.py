from datetime import datetime
from dateutil.rrule import *
import httplib2
import sys

from caldav import DAVClient
from googleapiclient import discovery
import icalendar


UTC_TZ = u'+00:00'


class Event:
    """Event object. Contains information of a calendar event."""
    def __init__(self, title, start_time, end_time=None, info=''):
        self.start_time = start_time
        self.end_time = end_time
        self.title = title
        self.info = info

    @property
    def is_whole_day(self):
        return self.end_time is None


class CalendarBase:
    """Base class for calendar interfaces."""
    def get_events(self, start_time, end_time=None, max_results=10):
        """Get a series of events from the calendar.

        Arguments:
            start_time (datetime): fetch events after this time
            end_time (datetime): optional last start time for events to fetch
            max_results (int): Maximum number of events to fetch

        Returns:
            List of Events.
        """
        raise NotImplementedError

    def add_event(self, event):
        """Add event to calendar.

        Arguments:
            event (Event): Calendar event entry to add

        Returns:
            (bool) True if event was successfully added.
        """
        raise NotImplementedError


def remove_tz(string):
    return string[:-6]


class GoogleCalendar(CalendarBase):
    """Calendar interface for Google Calendar."""
    def __init__(self, credentials):
        self.credentials = credentials
        argv = sys.argv
        sys.argv = []
        http = self.credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)
        sys.argv = argv

    @staticmethod
    def to_event(event):
        """Converter from google calendar event structure to generic."""
        start_dt = end_dt = None
        start = event['start'].get('dateTime')
        end = event['end'].get('dateTime')
        if start:
            start_dt = datetime.strptime(remove_tz(start),
                                         '%Y-%m-%dT%H:%M:%S')
        if end:
            end_dt = datetime.strptime(remove_tz(end),
                                       '%Y-%m-%dT%H:%M:%S')
        title = event['summary']
        return Event(title, start_dt, end_dt)

    def get_events(self, start_time, end_time=None, max_results=10):
        """Add event to the calendar.

        Arguments:
            start_time (datetime): start time for first event
            end_time (datetime): limit for events to fetch
            max_results (int): result limit

        Returns:
            list of Event
        """
        start_time = start_time.isoformat() + 'Z'
        if end_time:
            end_time = end_time.isoformat() + 'Z'

        events_result = self.service.events().list(
            calendarId='primary', timeMin=start_time, timeMax=end_time,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime').execute()
        return [GoogleCalendar.to_event(e)
                for e in events_result.get('items', [])]

    def add_event(self, event):
        start_time = event.start_time.strftime('%Y-%m-%dT%H:%M:00')
        if not event.is_whole_day:
            stop_time = event.end_time.strftime('%Y-%m-%dT%H:%M:00')
        stop_time += UTC_TZ
        event = {}
        event['summary'] = event.title
        event['start'] = {
            'dateTime': start_time,
            'timeZone': 'UTC'
        }
        event['end'] = {
            'dateTime': stop_time,
            'timeZone': 'UTC'
        }
        try:
            self.service.events().insert(calendarId='primary',
                                         body=event).execute()
        except Exception:
            return False  # An error occured
        else:
            return True  # Successfully added event to calendar


VCAL_TEMPLATE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Mycroft Skill//Calendar//EN
BEGIN:VEVENT
UID:1234567890
DTSTAMP:{dtstamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{title}
END:VEVENT
END:VCALENDAR
"""


class DavCalendar(CalendarBase):
    def __init__(self, url, user, password, auth=None):
        self.client = DAVClient(url, username=user, password=password,
                                auth=auth)
        self.principal = self.client.principal()
        calendars = self.principal.calendars()

        if len(calendars) > 0:
            # No calendars exists
            self.calendar = calendars[0]
            print('Using calendar {}'.format(self.calendar))
        else:
            # TODO: Create calendar
            pass

    @staticmethod
    def to_event(vcal):
        entry = icalendar.Event.from_ical(vcal)
        for component in entry.walk():
            if component.name == "VEVENT":
                summary = component.get('summary')
                description = component.get('description')
                location = component.get('location')
                startdt = component.get('dtstart').dt
                enddt = component.get('dtend').dt
                exdate = component.get('exdate')
                if component.get('rrule'):
                    reoccur = component.get('rrule').to_ical().decode('utf-8')
                    for item in parse_recurrences(reoccur, startdt, exdate):
                        print('{0} {1}: {2} - {3}\n'.format(item, summary,
                                                            description, location))
                else:
                    print('{0}-{1} {2}: {3} '
                          '- {4}\n'.format(startdt.strftime("%D %H:%M UTC"),
                                           enddt.strftime("%D %H:%M UTC"),
                                           summary, description, location))
        return Event(summary, startdt, enddt)

    @staticmethod
    def to_vcal(event):
        start_time = event.start_time.strftime('%Y%m%dT%H%M00')
        end_time = event.end_time.strftime('%Y%m%dT%H%M00')
        return VCAL_TEMPLATE.format({'dt_stamp': start_time,
                                     'dt_start': start_time,
                                     'dt_end': end_time,
                                     'title': event.title})

    def get_events(self, start_time, end_time=None, max_results=10):
        """Get a series of events from the calendar.

        Arguments:
            start_time (datetime): fetch events after this time
            end_time (datetime): optional last start time for events to fetch
            max_results (int): Maximum number of events to fetch

        Returns:
            List of Events.
        """
        events = self.calendar.date_search(start_time, end_time)
        return [DavCalendar.to_event(e.data) for e in events
                if e.start_time > start_time]

    def add_event(self, event):
        """Add event to calendar.

        Arguments:
            event (Event): Calendar event entry to add

        Returns:
            (bool) True if event was successfully added.
        """
        vcal = DavCalendar.to_vcal(event)
        self.calendar.add_event(vcal)
