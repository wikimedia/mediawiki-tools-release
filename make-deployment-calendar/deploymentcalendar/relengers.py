#!/usr/bin/env python3

from collections import namedtuple

Relenger = namedtuple('Relenger', ['fullname', 'ircnick', 'schedule'])

RELENGERS = {
    'dancy': Relenger('Ahmon', 'dancy', 'American'),
    'hashar': Relenger('Antoine', 'hashar', 'European'),
    'brennen': Relenger('Brennen', 'brennen', 'American'),
    'dduvall': Relenger('Dan', 'marxarelli', 'American'),
    'jeena': Relenger('Jeena', 'longma', 'American'),
    'LarsWirzenius': Relenger('Lars', 'liw', 'European'),
    'mmodell': Relenger('Mukunda', 'twentyafterfour', 'American'),
}


def get(name, fallback=None):
    return RELENGERS.get(name, fallback)
