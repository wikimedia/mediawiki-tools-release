#-*-tab-width: 4; fill-column: 68; whitespace-line-column: 69 -*-
# vi:shiftwidth=4 tabstop=4 textwidth=68

# Copyright (C) 2019  Wikimedia Foundation, Inc.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Makefile help based on
# https://github.com/ianstormtaylor/makefile-help

.PHONY: help
# Show this help prompt.
help:
	@ echo
	@ echo '  Usage:'
	@ echo ''
	@ echo '    make <target> [flags...]'
	@ echo ''
	@ echo '  Targets:'
	@ echo ''
	@ awk '/^#/{ comment = substr($$0,3) } comment							\
		 && /^[a-zA-Z][a-zA-Z0-9_-]+ ?: *[^=]*$$/ {							\
			 print "   ", $$1, comment										\
		}' $(MAKEFILE_LIST) | column -t -s ':' | sort
	@ echo ''
	@ echo '  Flags: (Defaults in parenthesis)'
	@ echo ''
	@ awk '/^#/{ comment = substr($$0,3) } comment							\
		 && /^[a-zA-Z][a-zA-Z0-9_-]+ ?\?= *([^=].*)$$/ {					\
			print "   ", $$1, $$2, comment, 								\
			"(" ENVIRON[$$1] ")"									\
		}' $(MAKEFILE_LIST) | column -t -s '?=' | sort
	@ echo ''

# Show more targets and flags
morehelp:
	@ echo
	@ echo '  More Targets:'
	@ echo ''
	@ awk '/^#$$/ { if( lastline == comment ) { more=1 } }					\
			/^#$$/ { if( lastline != comment ) { more=0 } }					\
			/^[a-zA-Z][a-zA-Z0-9_-]+ ?: *[^=]*$$/ {							\
				if ( more == 1) {											\
					print "   ", $$1, comment								\
				}															\
			}																\
			/^# / { comment = substr($$0,3) }								\
				{ lastline = substr($$0,3) } '								\
			$(MAKEFILE_LIST) | column -t -s ':' | sort
	@ echo ''
	@ echo '  More Flags:'
	@ echo ''
	@ awk '/^#$$/ { if( lastline == comment ) { more=1 } }					\
			/^#$$/ { if( lastline != comment ) { more=0 } }					\
			/^[a-zA-Z][a-zA-Z0-9_-]+ ?\?= *([^=].*)$$/ {					\
				if ( more == 1) {											\
					print "   ", $$1, $$2, comment, 						\
						"(" ENVIRON[$$1] ")"								\
				}															\
			}																\
			/^# / { comment = substr($$0,3) }								\
				{ lastline = substr($$0,3) } '								\
			$(MAKEFILE_LIST) | column -t -s '?=' | sort
	@ echo ''
