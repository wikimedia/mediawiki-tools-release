#!/usr/bin/env python3

from collections import namedtuple

Relenger = namedtuple('Relenger', ['fullname', 'ircnick', 'schedule'])

RELENGERS = {
    'dancy': Relenger('Ahmon', 'dancy', 'American'),
    'hashar': Relenger('Antoine', 'hashar', 'European'),
    'brennen': Relenger('Brennen', 'brennen', 'American'),
    'dduvall': Relenger('Dan', 'dduvall', 'American'),
    'jeena': Relenger('Jeena', 'jeena', 'American'),
    'mmodell': Relenger('Mukunda', 'twentyafterfour', 'American'),
}


def get(name, fallback=None):
    return RELENGERS.get(name, fallback)
