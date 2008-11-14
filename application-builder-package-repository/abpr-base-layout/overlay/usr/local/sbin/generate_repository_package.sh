#!/bin/sh
#
# Generate an RPM file for the given host repository.
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

. "/usr/local/lib/repository.shlib"

hostname=$(hostname -f)

cd "${REPOSITORY_PACKAGE_LOCATION}"

output=${REPOSITORY_PACKAGE_REPO_FILE%%.in}

sed "s/##HOSTNAME##/${hostname}/g" "${REPOSITORY_PACKAGE_REPO_FILE}" \
  > /usr/src/redhat/SOURCES/"${output}"

cat <<EOF

The hostname ${hostname} will be used for the repository.

If this is incorrect, ...

 * Depress ^C now,
 * Give this machine a fully-qualified and accessible hostname
   and IP address with your local DNS;
 * Update this machine's hostname; and
 * Reboot.

REMEMBER: This hostname must be persistent between reboots and instance
          relocations.

In 30 seconds this will continue.

EOF

sleep 30

rpmbuild -ba "${REPOSITORY_PACKAGE_REPO_SPEC}"

find /usr/src/redhat/RPMS/ -name 'abpr*noarch*.rpm' -exec cp '{}' \
  "${REPOSITORY_LOCATION}/${SYSTEM_VERSION}/noarch/" ';'
