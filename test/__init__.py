from mock import MagicMock

from test.integrationtests.skills.skill_tester import SkillTest


def create_mock_service():
   service = MagicMock()
   events = MagicMock()
   lister = MagicMock()
   events.list.return_value = lister
   lister.execute.return_value = {}
   service.events.return_value = events

   return service


def test_runner(skill, example, emitter, loader):
    s = [s for s in loader.skills if s and s.root_dir == skill][0]

    if example.endswith("001.whatsOnMyCalendarToday.json"):
        s.register_intents()
        s.service = create_mock_service()

    return SkillTest(skill, example, emitter).run(loader)
