# Copyright (C) 2008  Matt T. Proud <matt.proud@gmail.com>
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
#
# $Id$

all: srpm

abpr-base-layout-overlay.tar.gz:
	(cd overlay ; tar czvf ../abpr-base-layout-overlay.tar.gz \
	 --exclude=.svn .)

srpm: abpr-base-layout-overlay.tar.gz

clean:
	-rm *.rpm
	-rm *.tar.gz

install: srpm
	cp -f abpr-base-layout-overlay.tar.gz /usr/src/redhat/SOURCES
	cp -f abpr-base-layout.spec /usr/src/redhat/SPECS 

uninstall:
	rm -f /usr/src/redhat/SOURCES/abpr-base-layout-overlay.tar.gz
	rm -f /usr/src/redhat/SPECS/abpr-base-layout.spec
