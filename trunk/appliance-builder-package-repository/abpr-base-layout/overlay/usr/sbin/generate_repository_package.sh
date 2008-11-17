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

# TODO(mtp): Migrate this to an SRPM or something.

. "/usr/lib/repository.shlib"

wait_for_lock
trap "remove_lock; exit" EXIT INT TERM
create_lock

hostname=$(hostname -f)

cd "${REPOSITORY_PACKAGE_LOCATION}"

output=${REPOSITORY_PACKAGE_REPO_FILE%%.in}

sed "s/##HOSTNAME##/${hostname}/g" "${REPOSITORY_PACKAGE_REPO_FILE}" \
  > /usr/src/redhat/SOURCES/"${output}"

raw_mac_address=$(ifconfig eth0 | awk -F'HWaddr' '/HWaddr/ { print $2 }')
# Strip any whitespace.
read mac_address <<< "${raw_mac_address}";

raw_ip_address=$(ifconfig eth0 | awk -F'inet addr:' '/inet addr/ { print $2 }')
raw_ip_address=${raw_ip_address%%Bcast*}
read ip_address <<< "${raw_ip_address}";

cat <<EOF

The hostname ${hostname} will be used for the repository.

If this is incorrect or undesired, ...

 * Depress ^C now,
 * Give this machine a fully-qualified and accessible hostname
   and IP address with your local DNS;
 * Update this machine's hostname; and
 * Reboot.

REMEMBER: This hostname must be persistent between reboots and instance
          relocations.

Notes for DHCP Administrators:
 IP Address: ${ip_address}
 MAC Address: ${mac_address}

In 60 seconds, this will continue.

EOF

sleep 60

# Clean up any old ABPR outputs.
find "${RPM_OUTPUT_DIRECTORY}/" -name "${ABPR_VERSIONED_GLOB}" -exec rm '{}' ';'
find "${REPOSITORY_LOCATION}/${SYSTEM_VERSION}/noarch/" \
  -name "${ABPR_VERSIONED_GLOB}" -exec rm '{}' ';'

# Determine the symlink name for the latest package.
latest_symlink="${REPOSITORY_LOCATION}/${SYSTEM_VERSION}/noarch/abpr-latest.rpm"
rm -f "${latest_symlink}"

# Build the package.
rpmbuild -ba "${REPOSITORY_PACKAGE_REPO_SPEC}"

# Copy the package from the build location to the repository.
find "${RPM_OUTPUT_DIRECTORY}/" -name "${ABPR_VERSIONED_GLOB}" -exec cp '{}' \
  "${REPOSITORY_LOCATION}/${SYSTEM_VERSION}/noarch/" ';'

# Determine the latest version and symlink it.
latest_package=$(echo \
  "${REPOSITORY_LOCATION}/${SYSTEM_VERSION}/noarch"/${ABPR_VERSIONED_GLOB})
ln -s "${latest_package}" "${latest_symlink}"

regenerate_repository.sh
