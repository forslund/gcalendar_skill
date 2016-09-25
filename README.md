# Google Calendar skill for Mycroft

This is a basic skill for interacting with google calendar that can either reside in `~/.mycroft/third_party_skills/` or `/opt/mycroft/third_party`.

Currently this only supports a few intents and are read-only

## Installation

Clone the git repository
```
  git clone https://github.com/forslund/gcalendar_skill.git
```

Install prerequisites into the mycroft environment
```
  workon mycroft
  cd gcalendar_skill
  pip install -r requirements.txt
```

Authorize access to google calendar.
```
python ./
```

Above will open a web-browser where you will have to approve access.

If the machine running the skill is headless instead run
```
python ./ --noauth_local_webserver
```

You will now be given a link. Paste this into a web browser to retreive an authoriation code to enter into the command line.

Finally(!) restart mycroft to load the skill.

## Stuff to try out:

*What's my next appointment?*

*What's scheduled for today?*
