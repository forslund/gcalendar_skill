import sys
import httplib2
from googleapiclient import discovery
from datetime import datetime

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

    def add_event(self, title, start_time, end_time, info='', whole_day=False):
        """Add event to calendar.

        Arguments:
            title: Name of event
            start_time (datetime): UTC time for the start of the event
            end_time (datetime): UTC time for the end of the event
            info (str): Details about the event
            whole_day (bool): set to True if this is a whole day event.
                              Defaults to False

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

    def add_event(self, title, start_time, end_time, info='', whole_day=False):
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
        try:
            self.service.events()\
                .insert(calendarId='primary', body=event).execute()
        except Exception:
            return False  # An error occured
        else:
            return True  # Successfully added event to calendar
