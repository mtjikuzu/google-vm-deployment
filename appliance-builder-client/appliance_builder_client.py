#!/usr/bin/python2.4

# VMware Studio auto-builder framework for Apache Ant.
# Copyright (C) 2008  Matt T. Proud (matt.proud@gmail.com)
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

# $Id$

"""Build an appliance from a set of specifications.

A detailed description of appliance_builder.
"""

__author__ = 'matt.proud@gmail.com (Matt Proud)'

import base64
import glob
import logging
import os
import subprocess
import sys
import tempfile
import time


SLEEP_CHECK_INTERVAL = 1

# TODO(mtp): Extend the list of appliance packages from what is found in the RPM
#            directory.


class ValidationError(RuntimeError):
  def __init__(self, message, throwable):
    RuntimeError.__init__(self, message)
    self._throwable = throwable
    self._message = message

  def __str__(self):
    if self._throwable:
      throwable_information = str(self._throwable)
    else:
      throwable_information = 'Unavailable.'
    message = '\n'.join(['A validation failed:',
                         '---',
                         'Validation: %s' % self._message,
                         '---',
                         'Throwable details: %s' % throwable_information])
    return message


class SubprocessError(RuntimeError):
  def __init__(self, bounded_subprocess, message):
    RuntimeError.__init__(self, message)
    self._bounded_subprocess = bounded_subprocess
    self._message = message

  def __str__(self):
    if self._bounded_subprocess.retry is None:
      retry_count = 0
    else:
      retry_count = self._bounded_subprocess.retry
    process_string = ' '.join(self._bounded_subprocess.command_and_arguments)
    message = '\n'.join([('A subprocess failed. '
                          'Consider running the command manually to see why:'),
                         '---',
                         'Command: %s' % process_string,
                         '---',
                         'Message: %s' % self._message,
                         '---',
                         'Retry attempts: %i' % retry_count,
                         '---'])
    return message


class ReturnValueError(SubprocessError):
  def __init__(self, bounded_subprocess, message=None):
    if not message:
      message = 'The return value of %i was expected but %i was received.' % (
          bounded_subprocess.expected_return, bounded_subprocess.return_value)
    SubprocessError.__init__(self, bounded_subprocess, message)


class TimeoutError(SubprocessError):
  def __init__(self, bounded_subprocess, message=None):
    if not message:
      message = 'The process was expected to finish in %i seconds.' % (
          bounded_subprocess.timeout)
    SubprocessError.__init__(self, bounded_subprocess, message)


class InvalidStateError(RuntimeError):
  pass


class Build(object):
  pass


class BoundedSubprocess(object):
  _DEFAULT_INITIALIZERS = {'timeout': 5, 'expected_return': 0,
                           'retry': None}

  def __init__(self, *command_and_arguments, **kwargs):
    options = dict(self._DEFAULT_INITIALIZERS)
    options.update(kwargs)

    for key, value in options.iteritems():
      if key == 'timeout':
        timeout = value
      elif key == 'expected_return':
        expected_return = value
      elif key == 'retry':
        retry = value
      else:
        raise ValueError('%s is unrecognized' % (key))

    self.command_and_arguments = list(command_and_arguments)
    self.timeout = timeout
    self.expected_return = expected_return
    self.retry = retry
    self.retry_attempts = 0
    self.return_value = None

  def _ExceededTimeout(self):
    if not self.timeout:
      return False
    else:
      return time.time() > (self._start_time + self.timeout)

  def _Finished(self):
    if not self._popen_instance:
      raise InvalidStateError('The process has not been started yet.')

    return self._popen_instance.poll() is not None

  def Invoke(self):
    logging.debug('Invoking %s ...' % ' '.join(self.command_and_arguments))
    self._start_time = time.time()
    self._popen_instance = subprocess.Popen(self.command_and_arguments,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            shell=False)
    while not self._ExceededTimeout():
      if self._Finished():
        break
      time.sleep(SLEEP_CHECK_INTERVAL)

    try:
      if self.timeout and not self._Finished():
        raise TimeoutError(self)

      self.return_value = self._popen_instance.wait()

      if (self.expected_return is not None and
          self.return_value != self.expected_return):
        raise ReturnValueError(self)

    except SubprocessError, e:
      if self.retry is None:
        raise e
      elif self.retry_attempts < self.retry:
        self.retry_attempts += 1
        self.Invoke()
      else:
        raise e


class VmwareStudio(object):
  _VENDOR_PACKAGES_DESTINATION = '/opt/vmware/www/ISV/appliancePackages'

  def __init__(self, host_name, ssh_key_file, packages_source,
               configuration_manager, user='root'):
    self._host_name = host_name
    self._ssh_key_file = ssh_key_file
    self._packages_source = packages_source
    self._configuration_manager = configuration_manager
    self._user = user

  def _DeriveHostSpec(self):
    return '%s@%s' % (self._user, self._host_name)

  def RemoteInvoke(self, *args, **kwargs):
    arguments = ['/usr/bin/ssh', '-i', self._ssh_key_file,
                 self._DeriveHostSpec()]
    arguments.extend(args)
    return BoundedSubprocess(*arguments, **kwargs)

  def Validate(self):
    logging.info('Checking if the SSH identity file exists ...')
    if not os.path.exists(self._ssh_key_file):
      raise ValidationError('The SSH key identity file "%s" does not exist.' % (
          self._ssh_key_file), None)

    logging.info(('Checking whether the SSH identity file is valid '
                  'and that remote commands may be executed on the Vmware '
                  'Studio host.'))
    true_instance = self.RemoteInvoke('/bin/true')
    try:
      true_instance.Invoke()
    except SubprocessError, e:
      raise ValidationError('A simple SSH command could not be run.', e)

    logging.info('Checking whether the vendor packages directory exists ...')
    if not os.path.isdir(self._packages_source):
      raise ValidationError('The vendor packages directory does not exist.',
                            None)

    logging.info('Validating whether RPMs exist ...')
    rpms = glob.glob(os.path.join(self._packages_source, '*.rpm'))
    if not rpms:
      raise ValidationError('No RPM files were found ...', None)

    logging.info('Checking whether rsync is available ....')
    # Notes(mtp): os.path.join is insufficient here.
    rsync_path_spec = '%s:%s/' % (self._DeriveHostSpec(),
                                  self._VENDOR_PACKAGES_DESTINATION)
    rsync_instance = BoundedSubprocess('/usr/bin/rsync', '-e',
                                       'ssh -i %s' % self._ssh_key_file,
                                       rsync_path_spec)
    try:
      rsync_instance.Invoke()
    except SubprocessError, e:
      raise ValidationError('A simple rsync operation could not be run.', e)

  def UpdatePackagesList(self):
    logging.info('Updating packages list ...')
    rpm_sanitizer = set([])
    rpms_from_filesystem = glob.glob(os.path.join(self._packages_source,
                                                  '*.rpm'))
    for rpm_file in rpms_from_filesystem:
      rpm_basename = os.path.basename(rpm_file)
      rpm_name = rpm_basename[:-4]
      rpm_sanitizer.add(rpm_name)

    rpm_sanitizer.update(
        self._configuration_manager.configuration['APPLIANCE_PACKAGES'])

    package_definitions = []
    for package in rpm_sanitizer:
      package_definition = ''.join(['<vadk:Package vadk:name="', package,
                                    '"/>'])
      package_definitions.append(package_definition)

    self._configuration_manager.configuration['APPLIANCE_PACKAGES'] = ''.join(
        package_definitions)

  def CopyVendorPackages(self):
    logging.info('Copying vendor packages ...')
    rsync_instance = BoundedSubprocess(
        '/usr/bin/rsync', '-rltzvc', '-e', 'ssh -i %s' % self._ssh_key_file,
        ''.join([self._packages_source, '/']), '%s:%s' % (
            self._DeriveHostSpec(), self._VENDOR_PACKAGES_DESTINATION))
    rsync_instance.Invoke()

    chmod_instance = self.RemoteInvoke('/bin/chmod', '-R', 'a+r',
                                       self._VENDOR_PACKAGES_DESTINATION)
    chmod_instance.Invoke()

    chmod_instance = self.RemoteInvoke('/bin/chmod', 'a+x',
                                       self._VENDOR_PACKAGES_DESTINATION)
    chmod_instance.Invoke()


class ConfigurationManager(object):
  _DEFAULT_CONFIGURATION = {'APPLIANCE_ROOT_PASSWORD': None,
                            'VMWARE_SERVER_HOST': None,
                            'VMWARE_SERVER_PORT': 902,
                            'VMWARE_SERVER_USERNAME': 'root',
                            'VMWARE_SERVER_PASSWORD': None,
                            'APPLIANCE_PACKAGES': []}

  def __init__(self, configuration_file):
    new_configuration = dict(self._DEFAULT_CONFIGURATION)

    if configuration_file.endswith('.py'):
      configuration_file = configuration_file[:-3]
    else:
      message = ('The configuration file must end in .py, be in the '
                 'local directory, follow Python dictionary standards, and the '
                 'master attribute must be a dictionary named CONFIGURATION '
                 'that holds the required keys. See: python -c "help(dict)"')
      raise ValueError(message)

    try:
      configuration_module = __import__(configuration_file)
    except ImportError:
      raise RuntimeError('%s could not be imported.' % configuration_file)

    new_configuration.update(configuration_module.CONFIGURATION)

    self.configuration = new_configuration
    self.configuration['APPLIANCE_ROOT_PASSWORD'] = base64.b64encode(
        self.configuration['APPLIANCE_ROOT_PASSWORD'])
    self.configuration['VMWARE_SERVER_PASSWORD'] = base64.b64encode(
        self.configuration['VMWARE_SERVER_PASSWORD'])

  def Validate(self):
    logging.info('Validating secure configuration ...')
    for key, value in self.configuration.iteritems():
      if value is None:
        message = 'Configuration key "%s" must be defined.' % key
        raise ValidationError(message, None)


class VmwareStudioTemplate(object):
  def __init__(self, studio_template_file, configuration_manager):
    self._studio_template_file = studio_template_file
    self._configuration_manager = configuration_manager
    self._generated_studio_file = tempfile.NamedTemporaryFile()
    os.chmod(self._generated_studio_file.name, 0600)

  def Validate(self):
    logging.info('Validating that the studio template file exists ...')
    if not os.path.exists(self._studio_template_file):
      message = 'The studio template %s does not exist.' % (
          self._studio_template_file)
      raise ValidationError(message, None)

    logging.info('Validating the studio template file ...')

    template_keys = self._configuration_manager.configuration.keys()
    not_found_keys = list(template_keys)
    logging.debug(template_keys)
    template_file_handle = open(self._studio_template_file)
    for line_number, line in enumerate(template_file_handle):
      for template_key in template_keys:
        if template_key in line:
          logging.debug('%i %s' % (line_number + 1, template_key))
          not_found_keys.remove(template_key)

    if not_found_keys:
      message = 'The following keys are unaddressed by the template: %s' % (
          ', '.join(not_found_keys))
      raise ValidationError(message, None)

  def GenerateBuildProfile(self):
    logging.info('Generating build profile from template to %s ...' % (
        self._generated_studio_file.name))

    template_file_handle = open(self._studio_template_file)
    for line in template_file_handle:
      for key, value in self._configuration_manager.configuration.iteritems():
        what_to_find = ''.join(['##', key, '##'])
        while what_to_find in line:
          left, right = line.split(what_to_find, 1)
          line = ''.join([left, str(value), right])
      self._generated_studio_file.write(line)
      self._generated_studio_file.file.flush()
    time.sleep(360)


def _SetupLogging():
  logging.basicConfig(level=logging.DEBUG,
                      format='%(levelname)s :: %(message)s')


def main(argv):
  _SetupLogging()

  secure_configuration_file = argv[1]
  vmware_studio_template = argv[2]
  vmware_studio_host = argv[3]
  identity_key = argv[4]
  packages_directory = argv[5]

  configuration_manager = ConfigurationManager(secure_configuration_file)
  try:
    configuration_manager.Validate()
  except ValidationError, e:
    logging.error(e)
    sys.exit(1)

  vmware_studio = VmwareStudio(vmware_studio_host, identity_key,
                               packages_directory, configuration_manager)
  try:
    vmware_studio.Validate()
  except ValidationError, e:
    logging.error(e)
    sys.exit(1)

  vmware_studio_template = VmwareStudioTemplate(vmware_studio_template,
                                                configuration_manager)
  try:
    vmware_studio_template.Validate()
  except ValidationError, e:
    logging.error(e)
    sys.exit(1)

  vmware_studio.CopyVendorPackages()
  vmware_studio.UpdatePackagesList()
  vmware_studio_template.GenerateBuildProfile()

if __name__ == '__main__':
  main(sys.argv)
