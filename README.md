## Google Calendar skill
A skill allowing Mycroft to access Google Calendar.

## Description 
Fetches scheduled events from Google Calendar and allows adding events to your calendar.

## Installation
Navigate to Mycroft's skills directory and clone this repository:

    $ cd /opt/mycroft/skills
    $ git clone https://github.com/forslund/gcalendar_skill.git

### Installing requirements
Navigate to gcalender_skill directory:

    $ cd /opt/mycroft/skills/gcalendar_skill

Install requirements as user (recommended):

    $ pip3 install -r requirements.txt --user

### How To Authorize Calendar Access
To authorize access to your calendar: 
- Go to home.mycroft.ai and click on skills.
- Scroll down to Google Calendar
- Click "Connect"
- Log into your Google account and authorize the skill 

## Examples 
* "what's next on my schedule"
* "what's on my calendar on friday"
* "add have fun to my calendar at 7 in the evening on saturday"

## Credits 
Mycroft AI
