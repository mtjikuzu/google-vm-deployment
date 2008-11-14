# Create repository directories and ensure permissions stay sane.
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

Name: abpr
Version: 1
Release: 1
Summary: The configuration package for the appliance builder package repository
Group: System Environment/Base
License: GPLv2
Source1: abpr.repo
BuildRoot: %{_builddir}/%{name}-%{version}-rpmroot
BuildArch: noarch
Requires: centos-release >= %{version}

%description
This package installs the repository GPG and YUM repository information for
the application builder.

%prep
%setup -c -T

%build

%install
rm -rf ${RPM_BUILD_ROOT}

install -dm 755 ${RPM_BUILD_ROOT}%{_sysconfdir}/yum.repos.d
install -pm 644 %{SOURCE1} \
  ${RPM_BUILD_ROOT}%{_sysconfdir}/yum.repos.d

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
%config %{_sysconfdir}/yum.repos.d

%changelog
* Thu Nov 13 2008 Matt Proud  1-1
- Initial creation.
