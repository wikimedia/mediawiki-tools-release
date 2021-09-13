#!/usr/bin/env python3

from collections import namedtuple

Relenger = namedtuple('Relenger', ['fullname', 'ircnick', 'schedule'])

RELENGERS = {
    'dancy': Relenger('Ahmon', 'dancy', 'UTC-7'),
    'hashar': Relenger('Antoine', 'hashar', 'UTC-0'),
    'brennen': Relenger('Brennen', 'brennen', 'UTC-7'),
    'dduvall': Relenger('Dan', 'dduvall', 'UTC-7'),
    'jeena': Relenger('Jeena', 'jeena', 'UTC-7'),
    'mmodell': Relenger('Mukunda', 'twentyafterfour', 'UTC-7'),
}


def get(name, fallback=None):
    return RELENGERS.get(name, fallback)
