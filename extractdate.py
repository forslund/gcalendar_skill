from collections import OrderedDict
from parsedatetime import Calendar

cal = Calendar()

date_texts = OrderedDict([
    ('tenth', 10),
    ('ten', 10),
    ('eleventh', 11),
    ('eleven', 11),
    ('twelfth', 12),
    ('twelve', 12),
    ('thirteenth', 13),
    ('thirteen', 13),
    ('fourteenth', 14),
    ('fourteen', 14),
    ('fifteenth', 15),
    ('fifteen', 15),
    ('sixteenth', 16),
    ('sixteen', 16),
    ('seventeenth', 17),
    ('seventeen', 17),
    ('eigthteenth', 18),
    ('eigthteen', 18),
    ('nineteenth', 19),
    ('nineteen', 19),
    ('twenty one', 21),
    ('twenty first', 21),
    ('twenty two', 22),
    ('twenty second', 22),
    ('twenty three', 23),
    ('twenty third', 23),
    ('twenty four', 24),
    ('twenty fourth', 24),
    ('twenty five', 25),
    ('twenty fifth', 25),
    ('twenty six', 26),
    ('twenty sixth', 26),
    ('twenty seven', 27),
    ('twenty seventh', 27),
    ('twenty eight', 28),
    ('twenty eighth', 28),
    ('twenty nine', 29),
    ('twenty ninth', 29),
    ('twenty', 20),
    ('twentieth', 20),
    ('thirty', 30),
    ('thirtieth', 30),
    ('first', 1),
    ('one', 1),
    ('second', 2),
    ('two', 2),
    ('third', 3),
    ('three', 3),
    ('fourth', 4),
    ('four', 4),
    ('fifth', 5),
    ('five', 5),
    ('sixth', 6),
    ('six', 6),
    ('seventh', 7),
    ('seven', 7),
    ('eighth', 8),
    ('eight', 8),
    ('ninth', 9),
    ('nine', 9)
    ])


def _num_replace(string):
    for key in date_texts:
        string = string.replace(key, str(date_texts[key]))
    return string

minor_list = [' of ', ' the ']


def _remove_minors(string):
    for w in minor_list:
        string = string.replace(w, ' ')
    return string


def extractdate(string):
    string = _num_replace(string)
    string = _remove_minors(string)
    return cal.parseDT(string)[0]
