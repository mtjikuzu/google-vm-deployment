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
__version__ = '$Revision$'

import base64
import glob
import logging
import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib


SLEEP_CHECK_INTERVAL = 1

# TODO(mtp): Constantize more strings.
# TODO(mtp): Parameterize more aspects of operation.


def CreateCommandFromItems(*command_pieces):
  """Create a command  for a shell interpreter from components.

  Args:
    command_pieces: An iterable of components to be combined together into a
                    shell interpreter command.

  Returns:
    A string of the command.
  """
  string_generator = (str(piece) for piece in command_pieces)
  line = ' '.join(string_generator)
  return line


def GenerateCommandOrFailDefinition(command):
  """Create a line for a shell interpreter to run that exits on failure.

  Arguments:
    command: A string of a command to run.

  Returns:
    A string of the new command for the shell interpreter.
  """
  line_composition = [command, '||', 'exit 1']
  line = CreateCommandFromItems(*line_composition)
  return line


def GenerateInstallPackageWithYumDefinition(package):
  """Create a package installation command with YUM for a shell interpreter.

  Arguments:
    package: A string of the package name to be installed.

  Returns:
    A string of the package installation command.
  """
  line_composition = ['yum', '-yv', 'install', package]
  line = CreateCommandFromItems(*line_composition)
  return line


def CreateStringFrom(*components):
  """Create a string from a variety of components.

  Arguments:
    components: An iterable of things that shall be put together into a final
                string. Each component, regardless of its type, shall be
                converted to a string.
  Returns:
    A string of the final stuffs.
  """
  string_generator = (str(piece) for piece in components)
  end_string = ''.join(string_generator)
  return end_string


class ValidationError(RuntimeError):
  """Raised if a build pre-condition cannot be satisfied."""

  def __init__(self, message, throwable=None):
    """Instantiate the exception.

    Args:
      message: A string of the message to be associated with the validation
               error.
      throwable: An instance of an exception that can be included to provide
                 information to the end-user.
    """
    RuntimeError.__init__(self, message)
    self._throwable = throwable
    self._message = message

  def __str__(self):
    """Provide a beautiful representation of the validation problem."""
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
  """A generic error associated with subprocesses."""

  def __init__(self, bounded_subprocess, message):
    """Instantiate the exception.

    Args:
      bounded_subprocess: An instance of BoundedSubprocess.
      message: A human-readable message about what occurred.
    """
    RuntimeError.__init__(self, message)
    self._bounded_subprocess = bounded_subprocess
    self._message = message

  def __str__(self):
    """Produce a beautiful representation of the error."""
    if self._bounded_subprocess.retry is None:
      retry_count = 0
    else:
      retry_count = self._bounded_subprocess.retry
    process_string = CreateCommandFromItems(
        self._bounded_subprocess.command_and_arguments)
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
  """Raised if a BoundedSubprocess instance return an unexpected value."""

  def __init__(self, bounded_subprocess, message=None):
    """Instantiate the exception.

    Args:
      bounded_subprocess: An instance of BoundedSubprocess.
      message: A string of an optional error message that can provide more
               failure information.
    """
    if not message:
      message = 'The return value of %i was expected but %i was received.' % (
          bounded_subprocess.expected_return, bounded_subprocess.return_value)
    SubprocessError.__init__(self, bounded_subprocess, message)


class TimeoutError(SubprocessError):
  """Raised if a BoundedSubprocess instance runs longer than expected."""

  def __init__(self, bounded_subprocess, message=None):
    """Instantiate the exception.

    Args:
      bounded_subprocess: An instance of BoundedSubprocess.
      message: A string of an optional error message that can provide more
               failure information.
    """
    if not message:
      message = 'The process was expected to finish in %i seconds.' % (
          bounded_subprocess.timeout)
    SubprocessError.__init__(self, bounded_subprocess, message)


class InvalidStateError(RuntimeError):
  """Used to indicate that something was in an unexpected state."""
  pass


class BoundedSubprocess(object):
  """A subprocess manager that cares about return value and runtime duration.

  Example Usage:

  ls_instance = BoundedSubprocess('/bin/ls', '/tmp')
  ls_instance.Invoke()
  """
  _DEFAULT_INITIALIZERS = {'timeout': 30, 'expected_return': 0,
                           'retry': 1, 'stdin': subprocess.PIPE,
                           'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}

  def __init__(self, *command_and_arguments, **kwargs):
    """Instantiate a BoundedSubprocess.

    This command runs without the environment, so no wildcards are processed.

    Args:
      command_and_arguments: An array of strings of the command to be passed.
      kwargs: A dictionary of operating parameters

    Raises:
      ValueError: If an unknown operating parameter is provided.
    """
    # TODO(mtp): Document the operating parameters in-depth.
    options = dict(self._DEFAULT_INITIALIZERS)
    options.update(kwargs)

    for key, value in options.iteritems():
      if key == 'timeout':
        timeout = value
      elif key == 'expected_return':
        expected_return = value
      elif key == 'retry':
        retry = value
      elif key == 'stdin':
        stdin = value
      elif key == 'stdout':
        stdout = value
      elif key == 'stderr':
        stderr = value
      else:
        raise ValueError('%s is unrecognized' % (key))

    self.command_and_arguments = list(command_and_arguments)
    self.timeout = timeout
    self.expected_return = expected_return
    self.retry = retry
    self.retry_attempts = 0
    self.return_value = None
    self.stdin = stdin
    self.stdout = stdout
    self.stderr = stderr

  def _ExceededTimeout(self):
    """Determines whether the subprocess exceeded its expected duration.

    Returns:
      A boolean indicating whether the timeout has been exceeded.
    """
    if not self.timeout:
      return False
    else:
      return time.time() > (self._start_time + self.timeout)

  def _Finished(self):
    """Determines whether the subprocess has finished running.

    Returns:
      A boolean indicating whether the subprocess has finished.

    Raises:
      InvalidStateError: If the process has not been started yet.
    """
    if not self.popen_instance:
      raise InvalidStateError('The process has not been started yet.')

    return self.popen_instance.poll() is not None

  def Invoke(self):
    """Start the process.

    Raises:
      ReturnValueError: If the process returns an unexpected return value.
      TimeoutError: If the process runs longer than expected.
    """
    logging.debug('Invoking %s ...' % (
        CreateCommandFromItems(self.command_and_arguments)))
    self._start_time = time.time()
    self.popen_instance = subprocess.Popen(self.command_and_arguments,
                                           stdin=self.stdin,
                                           stdout=self.stdout,
                                           stderr=self.stderr,
                                           shell=False)
    while not self._ExceededTimeout():
      if self._Finished():
        break
      time.sleep(SLEEP_CHECK_INTERVAL)

    try:
      if self.timeout and not self._Finished():
        raise TimeoutError(self)

      self.return_value = self.popen_instance.wait()

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


class ServiceMediator(object):
  """A class that works with services provided on remote hosts.

  This class is used to run command that are tailored to be invoked on remote
  hosts only.

  It works under the assumption that the remote host runs SSH and authentication
  occurs through SSH authorized keys.
  """

  def __init__(self, host_name, ssh_key_file, user='root'):
    """Instantiate a ServiceMediator.

    Args:
      host_name: A string of the fully-qualified domain name of the remote host
                 where the commands will be run.
      ssh_key_file: A string of the fully-qualified file path of the SSH
                    private key.
      user: An optional string of the username of the user who shall
            authenticate with the remote host.
    """
    self._host_name = host_name
    self._ssh_key_file = ssh_key_file
    self._user = user

  def _DeriveHostSpec(self):
    """Create the designator for the remote host and username.

    Example with username 'matt' and hostname 'planwirtschaft':
    => matt@planwirtschaft

    Where matt@planwirtschaft is used in 'ssh matt@planwirtschaft /bin/ls'

    Returns:
      A string of the user and host spec. for SSH sessions.
    """
    return CreateStringFrom(self._user, '@', self._host_name)

  def RemoteInvoke(self, *args, **kwargs):
    """Invoke a  BoundedSubprocess on a remote host.

    This essentially produces a BoundedSubprocess that is invoked on a remote
    host through SSH. See BoundedSubprocess' initializer for parameter
    information.

    Most importantly, this automatically handles wrapping subcommands into SSH.

    Args:
      args: An array of arguments to be passed to BoundedSubprocess'
            initializer.
      kwargs: A dictionary of arguments to be passed to BoundedSubprocess'
              initializer.

    Returns:
      An instance of BoundedSubprocess that is designed to run against a remote
      host.
    """
    arguments = ['/usr/bin/ssh', '-i', self._ssh_key_file,
                 self._DeriveHostSpec()]
    arguments.extend(args)
    return BoundedSubprocess(*arguments, **kwargs)


class YumRepository(ServiceMediator):
  """A resource to deal with Yum repositories.

  It performs such tasks as pushing files to the Yum server, regenerating
  repository metadata, and normalizing permissions.
  """
  _HTTP_LOCATION = 'repository/5'
  _PACKAGES_BASE_DESTINATION = os.path.join('/var/www/html', _HTTP_LOCATION)

  def __init__(self, host_name, ssh_key_file, packages_source,
               configuration_manager, user='root'):
    """Instantiate a YumRepository.

    Args:
      host_name: A string of the fully-qualified domain name of the remote host
                 where the commands will be run.
      ssh_key_file: A string of the fully-qualified file path of the SSH
                    private key.
      packages_source: A string of the fully-qualified file path of the
                      directory that contains vendor packages.
      configuration_manager: An instance of ConfigurationManager.
      user: An optional string of the username of the user who shall
            authenticate with the remote host.
    """
    ServiceMediator.__init__(self, host_name, ssh_key_file, user=user)
    self._packages_source = packages_source
    self._configuration_manager = configuration_manager

  def Validate(self):
    """Determine whether the operating environment is sufficient to work.

    Raises:
      ValidationError: If several operating expectations cannot be successfully
                       met.
    """
    logging.info('Checking whether the vendor packages directory exists ...')
    if not os.path.isdir(self._packages_source):
      raise ValidationError('The vendor packages directory does not exist.')

    logging.info('Validating whether RPMs exist ...')
    rpms = glob.glob(os.path.join(self._packages_source, '*.rpm'))
    if not rpms:
      raise ValidationError('No RPM files were found ...')

    logging.info('Checking whether rsync is available ....')
    # Notes(mtp): os.path.join is insufficient here.
    rsync_path_spec = CreateStringFrom(self._DeriveHostSpec(), ':',
                                       self._PACKAGES_BASE_DESTINATION, '/')
    rsync_instance = BoundedSubprocess('/usr/bin/rsync', '-e',
                                       'ssh -i %s' % self._ssh_key_file,
                                       rsync_path_spec)
    try:
      rsync_instance.Invoke()
    except SubprocessError, e:
      raise ValidationError('A simple rsync operation could not be run.',
                            throwable=e)

  def CopyVendorPackages(self, remove_builder_repository):
    """Copies vendor packages onto the Yum repository.

    Args:
      remove_builder_repository: A boolean whose value indicates indicates
                                 whether the builder repository information
                                 is to be removed post-build.
    """
    logging.info('Copying vendor packages ...')

    # RPM file names do not always correspond to the actual package name.
    # rpm_instance below fetches the actual package name by examining the
    # metadata.

    # Take the list of packages as defined in the secure operating parameters
    # and remove duplicates by using the set data type.
    packages = set(
        self._configuration_manager.configuration['APPLIANCE_PACKAGES'])

    # Operating on vendor RPM files.
    for rpm in glob.glob(os.path.join(self._packages_source, '*.rpm')):
      logging.info('Copying %s ...' % rpm)

      rpm_basename = os.path.basename(rpm)
      # RPMs are temporarily copied to the /tmp directory, where
      # bits of metadata are extracted from them that will ultimately determine
      # their final destination.
      remote_temporary_destination = os.path.join('/tmp', rpm_basename)
      # rsync is used for speed reasons, because it can verify checksums,
      # and only copy the files if absolutely necessary.
      # The main reason that recopying the same file is required is that
      # housecleaning services reap the contents of temporary directories
      # periodically.
      rsync_instance = BoundedSubprocess(
          '/usr/bin/rsync', '-rltzvc', '-e', 'ssh -i %s' % self._ssh_key_file,
          rpm, '%s:%s' % (self._DeriveHostSpec(), remote_temporary_destination),
          retry=3, timeout=300)
      rsync_instance.Invoke()

      logging.info('Determining RPM information ...')
      # Due to the fact that expecting vendors to include rpm in their
      # development environments is too high, we need to use the actual
      # yum repository and rpm on that to get several bits of metadata.
      # This is also because not all vendors can be expected to have
      # a Python module that interacts with RPM files directly.
      rpm_instance = self.RemoteInvoke('/bin/rpm', '-q',
                                       '--queryformat',
                                       '"%{NAME} %{ARCH} %{VERSION}"',
                                       '-p', remote_temporary_destination)
      rpm_instance.Invoke()

      rpm_information = rpm_instance.popen_instance.stdout.read().strip()
      rpm_name, architecture, version = rpm_information.split()

      # ARCH field for SRPMS appears incorrectly, so we will try to guess based
      # upon the file name.
      if rpm_basename.split('.')[-2] == 'src':
        architecture = 'SRPMS'

      logging.info('Moving package to its final location ...')
      remote_final_destination = os.path.join(self._PACKAGES_BASE_DESTINATION,
                                              architecture)
      cp_instance = self.RemoteInvoke('/bin/cp', '-fpv',
                                      remote_temporary_destination,
                                      remote_final_destination)
      cp_instance.Invoke()
      # The Yum manual states that packages may be installed through a variety
      # of names. One is ${package_name}-${version}. This method is used here
      # to install vendor packages if they want a specific version.
      specific_name = CreateStringFrom(rpm_name, '-', version)
      packages.add(specific_name)

    package_commands = []
    for package in packages:
      install_command = GenerateInstallPackageWithYumDefinition(package)
      fail_command = GenerateCommandOrFailDefinition(install_command)
      package_commands.append(fail_command)

    commands = '\n'.join(package_commands)
    self._configuration_manager.configuration['APPLIANCE_PACKAGES'] = commands

    logging.info('Normalizing permissions ...')
    chmod_instance = self.RemoteInvoke('/bin/chmod', '-R', 'a+r',
                                       self._PACKAGES_BASE_DESTINATION)
    chmod_instance.Invoke()

    chmod_instance = self.RemoteInvoke('/bin/chmod', 'a+x',
                                       self._PACKAGES_BASE_DESTINATION)
    chmod_instance.Invoke()

    logging.info('Regenerating repository meta data ...')
    repository_regenerator = self.RemoteInvoke(
        '/usr/sbin/regenerate_repository.sh', retry=3, timeout=300)
    repository_regenerator.Invoke()

    repository_package_url = CreateStringFrom(
        'http://', self._host_name, '/', self._HTTP_LOCATION, '/', 'noarch',
        '/', 'abpr-latest.rpm')
    repository_registration_command_partial = CreateCommandFromItems(
        'rpm', '-Uvh', repository_package_url)
    repository_registration_command = GenerateCommandOrFailDefinition(
        repository_registration_command_partial)
    key = 'APPLIANCE_PACKAGE_PREPARATION'
    # TODO(mtp): Add a conditional to allow the repository registration package
    # to be removed when done.
    self._configuration_manager.configuration[key] = (
        repository_registration_command)
    if remove_builder_repository:
      key = 'APPLIANCE_PACKAGES_POST'
      repository_unregistration_command_partial = CreateCommandFromItems(
          'yum', '-yv', 'remove', 'abpr')
      repository_unregistration_command = GenerateCommandOrFailDefinition(
          repository_unregistration_command_partial)
      self._configuration_manager.configuration[key] = (
          repository_unregistration_command)


class VmwareStudio(ServiceMediator):
  """A resource to deal with VMware Studio instances.

  It is responsible for checking build status, starting the build, and copying
  the result back to the target.
  """
  _BUILD_PROFILE_PATH = '/opt/vmware/var/lib/build/profiles'
  _ACCEPTABLE_STATES = ['finished', 'failed']
  # TODO(mtp): Copy the build result back to the requester.

  def __init__(self, host_name, ssh_key_file,
               configuration_manager, appliance_zip_file_save_path,
               user='root'):
    """Instantiate a VmwareStudio.

    Args:
      host_name: A string of the fully-qualified domain name of the remote host
                 where the commands will be run.
      ssh_key_file: A string of the fully-qualified file path of the SSH
                    private key.
      configuration_manager: An instance of ConfigurationManager.
      appliance_zip_file_save_path: A string of the fully-qualified path to
                                    where the appliance will be saved.
      user: An optional string of the username of the user who shall
            authenticate with the remote host.
    """
    ServiceMediator.__init__(self, host_name, ssh_key_file, user=user)
    self._configuration_manager = configuration_manager
    self._appliance_zip_file_save_path = appliance_zip_file_save_path

  def Validate(self):
    """Determine whether the operating environment is sufficient to work.

    Raises:
      ValidationError: If several operating expectations cannot be successfully
                       met.
    """
    logging.info('Checking if the SSH identity file exists ...')
    if not os.path.exists(self._ssh_key_file):
      raise ValidationError('The SSH key identity file "%s" does not exist.' % (
          self._ssh_key_file))

    logging.info(('Checking whether the SSH identity file is valid '
                  'and that remote commands may be executed on the VMware '
                  'Studio host.'))
    true_instance = self.RemoteInvoke('/bin/true')
    try:
      true_instance.Invoke()
    except SubprocessError, e:
      raise ValidationError('A simple SSH command could not be run.',
                            throwable=e)

    logging.info('Checking build state ...')
    studiocli_instance = self.RemoteInvoke('/opt/vmware/bin/studiocli',
                                           '--buildstatus',
                                           stdout=subprocess.PIPE)
    studiocli_instance.Invoke()
    for line in studiocli_instance.popen_instance.stdout:
      if 'State:' in line:
        state = line.split()[1].strip()
        if state not in self._ACCEPTABLE_STATES:
          message = CreateStringFrom('VMware Studio is busy;',
                                     ' its state is "', state, '" right now.')
          raise ValidationError(message)
        break

  def CopyTemplate(self, template_path):
    """Copy the generated VMware Studio template to the VMware Studio."""
    logging.info('Copying template ...')

    rsync_instance = BoundedSubprocess(
        '/usr/bin/rsync', '-rltzvc', '-e', 'ssh -i %s' % self._ssh_key_file,
        template_path, '%s:%s' % (self._DeriveHostSpec(),
                                  self._BUILD_PROFILE_PATH),
        retry=3, timeout=300)
    rsync_instance.Invoke()
    # TODO(mtp): Refactor out this nastiness.
    self._build_profile_path = os.path.join(self._BUILD_PROFILE_PATH,
                                            os.path.basename(template_path))

  def BuildAppliance(self):
    """Start the appliance build process."""
    logging.info('Validating profile ...')
    validate_instance = self.RemoteInvoke('/opt/vmware/bin/studiocli',
                                          '--validateprofile', '-p',
                                          self._build_profile_path, timeout=120)

    validate_instance.Invoke()

    logging.info('Building profile ...')
    build_instance = self.RemoteInvoke('/opt/vmware/bin/studiocli',
                                       '--createbuild', '-p',
                                       self._build_profile_path,
                                       timeout=(60 * 60))
    build_instance.Invoke()

  def CopyAppliance(self):
    """Copy the appliance from the VMware Studio to the local machine."""
    logging.info('Getting the location of the build ...')
    studiocli_instance = self.RemoteInvoke('/opt/vmware/bin/studiocli',
                                           '--buildstatus',
                                           stdout=subprocess.PIPE)
    studiocli_instance.Invoke()
    save_location = None
    for line in studiocli_instance.popen_instance.stdout:
      if 'VA ZIP URL:' in line:
        line_content = line.split('VA ZIP URL:')
        save_location = line_content.pop().strip()
        break

    logging.info('Copying built appliance to local machine ...')
    urllib.urlretrieve(save_location, self._appliance_zip_file_save_path)


class ConfigurationManager(object):
  """A resource to deal with various aspects of configuration."""

  _DEFAULT_SUBSTITUTIONS = {'APPLIANCE_ROOT_PASSWORD': None,
                            'VMWARE_SERVER_HOST': None,
                            'VMWARE_SERVER_PORT': 902,
                            'VMWARE_SERVER_USERNAME': 'root',
                            'VMWARE_SERVER_PASSWORD': None,
                            'APPLIANCE_PACKAGE_PREPARATION': '',
                            'APPLIANCE_PACKAGES': [],
                            'APPLIANCE_PACKAGES_POST': ''}

  def __init__(self, configuration_file):
    """Instantiate a Configuration manager.

    Args:
      configuration_file: A string of the name of the secure configuration file.

    Raises:
      ValueError: If the configuration file is invalid.
      RuntimeError: If there is a syntax error in the configuration file or
                    if it does not follow the expected module structure.
    """
    new_configuration = dict(self._DEFAULT_SUBSTITUTIONS)

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

    try:
      new_configuration.update(configuration_module.CONFIGURATION)
    except AttributeError:
      raise RuntimeError('%s lacks the CONFIGURATION top-level attribute.' % (
          configuration_file))

    self.configuration = new_configuration

    # VMware Studio stores passwords encoded in base64.
    self.configuration['APPLIANCE_ROOT_PASSWORD'] = base64.b64encode(
        self.configuration['APPLIANCE_ROOT_PASSWORD'])
    self.configuration['VMWARE_SERVER_PASSWORD'] = base64.b64encode(
        self.configuration['VMWARE_SERVER_PASSWORD'])

  def Validate(self):
    """Determine whether the operating environment is sufficient to work.

    Raises:
      ValidationError: If several operating expectations cannot be successfully
                       met.
    """
    logging.info('Validating secure configuration ...')
    for key, value in self.configuration.iteritems():
      if value is None:
        message = 'Configuration key "%s" must be defined.' % key
        raise ValidationError(message)


class VmwareStudioTemplate(object):
  """A resource to deal with VMware Studio appliance template files."""

  def __init__(self, studio_template_file, configuration_manager):
    """Instantiate a VmwareStudioTemplate.

    Args:
      studio_template_file: A string of the fully-qualified path of the input
                            template file.
      configuration_manager: An instance of ConfigurationManager.
    """
    self._studio_template_file = studio_template_file
    self._configuration_manager = configuration_manager
    self._generated_studio_file = tempfile.NamedTemporaryFile()
    # There are passwords in this file, so it should have restrictive
    # permissions.
    os.chmod(self._generated_studio_file.name, 0600)
    # Notes(mtp): tempfile.NamedTemporaryFile automatically unlinks itself
    # upon final dereferencing, so that necessitates final_studio_file_path.
    self.final_studio_file_path = None

  def Validate(self):
    """Determine whether the operating environment is sufficient to work.

    Raises:
      ValidationError: If several operating expectations cannot be successfully
                       met.
    """
    logging.info('Validating that the studio template file exists ...')
    if not os.path.exists(self._studio_template_file):
      message = 'The studio template %s does not exist.' % (
          self._studio_template_file)
      raise ValidationError(message)

    logging.info('Validating the studio template file ...')

    configuration = self._configuration_manager.configuration
    not_found_keys = list(configuration)

    template_file_handle = open(self._studio_template_file)
    for line_number, line in enumerate(template_file_handle):
      for template_key_basis in configuration:
        template_key = CreateStringFrom('##', template_key_basis, '##')
        if template_key in line:
          logging.debug('%i %s' % (line_number + 1, template_key_basis))
          not_found_keys.remove(template_key_basis)

    if not_found_keys:
      message = 'The following keys are unaddressed by the template: %s' % (
          ', '.join(not_found_keys))
      raise ValidationError(message)

  def GenerateBuildProfile(self):
    """Create the build profile from the template."""
    logging.info('Generating build profile from template to %s ...' % (
        self._generated_studio_file.name))

    template_file_handle = open(self._studio_template_file)
    for line in template_file_handle:
      for key, value in self._configuration_manager.configuration.iteritems():
        what_to_find = CreateStringFrom('##', key, '##')
        while what_to_find in line:
          left, right = line.split(what_to_find, 1)
          line = CreateStringFrom(left, str(value), right)
      self._generated_studio_file.write(line)
      # Notes(mtp): Flushing is done explicitly, due to some wonky behavior in
      # tempfile module.
      self._generated_studio_file.file.flush()

    destination_file = os.path.join(
        '/tmp', os.path.basename(self._studio_template_file))

    try:
      os.unlink(destination_file)
    except OSError:
      pass

    # TODO(mtp): Wrap this in a try-except block.
    # Notes(mtp): shutil.copy2 preserves permissions, etc.
    shutil.copy2(self._generated_studio_file.name, destination_file)
    self._generated_studio_file.close()
    self.final_studio_file_path = destination_file


def _SetupLogging(verbose):
  """Configure the character of logging for the utility.

  Args:
    verbose: A boolean of whether the builder is to operate verbosely.
  """
  level = logging.INFO
  if verbose:
    level = logging.DEBUG
  logging.basicConfig(level=level,
                      format='%(levelname)s :: %(message)s')


class Runner(object):
  """The resource that deals with running the build in its totality."""

  def __init__(self, arguments):
    """Instantiate a Runner.

    Args:
      arguments: A list of strings provided from the command line.
    """
    self._arguments = arguments
    self._SetupOptions()

  def _SetupOptions(self):
    """Configure the options and argument processor."""
    usage = ('%prog [options] '
             '<vmware studio host> '
             '<vmware studio ssh identity key file> '
             '<vmware studio template file> '
             '<yum repository host> '
             '<yum repository ssh identity key file> '
             '<secure configuration file> '
             '<packages directory> '
             '<appliance save ZIP file>')

    version = '%prog $Revision$'

    self._option_parser = optparse.OptionParser(usage=usage, version=version)

    self._option_parser.add_option('-v', '--verbose', action='store_true',
                                   dest='verbose')
    self._option_parser.add_option('-r', '--remove-builder-repository',
                                   action='store_false',
                                   dest='remove_builder_repository',
                                   help=('remove the builder repository from '
                                         'the appliance after its creation'))

    self._option_parser.set_defaults(verbose=False,
                                     remove_builder_repository=True)

  def Run(self):
    """Start the whole build process."""
    self._ProcessOptions()

    _SetupLogging(self._verbose)

    configuration_manager = None
    vmware_studio = None
    vmware_studio_template = None
    yum_repository = None

    try:
      configuration_manager = ConfigurationManager(
          self._secure_configuration_file)
      configuration_manager.Validate()

      vmware_studio = VmwareStudio(self._vmware_studio_host,
                                   self._vmware_studio_ssh_identity_key_file,
                                   configuration_manager,
                                   self._appliance_save_zip_file)
      vmware_studio.Validate()

      vmware_studio_template = VmwareStudioTemplate(
          self._vmware_studio_template_file,
          configuration_manager)
      vmware_studio_template.Validate()
      yum_repository = YumRepository(self._yum_repository_host,
                                     self._yum_repository_ssh_identity_key_file,
                                     self._packages_directory,
                                     configuration_manager)
      yum_repository.Validate()
    except ValidationError, validation_error:
      logging.error(validation_error)
      sys.exit(1)

    yum_repository.CopyVendorPackages(self._remove_builder_repository)
    vmware_studio_template.GenerateBuildProfile()
    vmware_studio.CopyTemplate(vmware_studio_template.final_studio_file_path)
    vmware_studio.BuildAppliance()
    vmware_studio.CopyAppliance()

  def _ProcessOptions(self):
    """Process the command-line arguments and options."""
    options, arguments = self._option_parser.parse_args(self._arguments)

    if len(arguments) != 8:
      self._option_parser.error('Incorrect arguments.')

    if '' in arguments or None in arguments:
      self._option_parser.error('Blank values may not be provided.')

    argument_names = ['vmware_studio_host',
                      'vmware_studio_ssh_identity_key_file',
                      'vmware_studio_template_file', 'yum_repository_host',
                      'yum_repository_ssh_identity_key_file',
                      'secure_configuration_file', 'packages_directory',
                      'appliance_save_zip_file']
    argument_names = [CreateStringFrom('_', name) for name in argument_names]
    argument_name_and_values = zip(argument_names, arguments)

    mappings = dict(argument_name_and_values)
    self.__dict__.update(mappings)

    self._remove_builder_repository = options.remove_builder_repository
    self._verbose = options.verbose


def main(arguments):
  runner = Runner(arguments)
  runner.Run()

if __name__ == '__main__':
  main(sys.argv[1:])
