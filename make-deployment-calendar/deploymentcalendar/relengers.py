#!/usr/bin/env python3

from collections import namedtuple

Relenger = namedtuple('Relenger', ['fullname', 'ircnick', 'schedule'])
DEFAULT = 'PHID-USER-5ewyncd6mpezaymyxfal'

RELENGERS = {
    'brennen': Relenger('Brennen', 'brennen', 'UTC-7'),
    'dancy': Relenger('Ahmon', 'dancy', 'UTC-7'),
    'dduvall': Relenger('Dan', 'dduvall', 'UTC-7'),
    'demon': Relenger('Chad', '^demon', 'UTC-7'),
    'hashar': Relenger('Antoine', 'hashar', 'UTC-0'),
    'jeena': Relenger('Jeena', 'jeena', 'UTC-7'),
    'jnuche': Relenger('Jaime', 'jnuche', 'UTC-0'),
    'thcipriani': Relenger('Tyler', 'thcipriani', 'UTC-7'),
}


def get(name, fallback=None):
    return RELENGERS.get(name, fallback)
