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

Name: abpr-base-layout
Version: 2
Release: 1
Summary: The base environment configuration for the repository appliance.
Group: System Environment/Base
License: GPLv2
Source0: abpr-base-layout-overlay.tar.gz
BuildRoot: %{_builddir}/%{name}-%{version}-rpmroot
BuildArch: noarch
Requires: centos-release >= %{version}, vixie-cron, rpm-build, createrepo, findutils, httpd

%description
This package provides a variety of management tools and configurations for the repository appliance.

%prep
%setup -c -T

%build

%install
mkdir -vp "${RPM_BUILD_ROOT}"
tar xzvf "%{SOURCE0}" -C "${RPM_BUILD_ROOT}"

%clean
rm -rf "${RPM_BUILD_ROOT}"

%files
%defattr(-,root,root,-)
/*
%config %{_sysconfdir}/cron.d/normalize
%config %{_sysconfdir}/cron.d/regenerate

%changelog
* Fri Nov 14 2008 Matt Proud  2-1
- Fix CRON definition problems.
- Migrate binaries to Linux FHS-compatible locations.

* Thu Nov 13 2008 Matt Proud  1-1
- Initial creation.
