/*
 * VMware Studio auto-builder framework for Apache Ant.
 * Copyright (C) 2008  Matt T. Proud (matt.proud@gmail.com)
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
 * USA.
 *
 * $Id$
 */

package com.google.vmdeployment;

import org.apache.tools.ant.BuildException;
import org.apache.tools.ant.Project;
import org.apache.tools.ant.Task;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.Map;
import java.util.HashMap;

/*
 * TODO(mtp): It would be nice add a sub-rule to grab RPMs by wildcard globbing to push them into
 *            the appliance.
 */

/**
 * A build task for Apache Ant that creates a VMware Studio appliance.
 *
 * @author matt.proud@gmail.com (Matt T. Proud)
 * @see org.apache.tools.ant.Task
 *
 */
public final class ApplianceBuilderTask extends Task {
  private static Integer EXPECTED_RETURN_VALUE = 0;

  private Boolean overwriteLastProduct = false;

  private String applianceBuilderUtility;
  private String vmwareStudioHost;
  private String vmwareStudioSshIdentityKeyFile;
  private String vmwareStudioTemplateFile;
  private String yumRepositoryHost;
  private String yumRepositorySshIdentityKeyFile;
  private String secureConfigurationFile;
  private String packagesDirectory;
  private String applianceSaveZipFile;

  public void setOverwriteLastProduct(boolean overWriteLastProduct) {
    this.overwriteLastProduct = overwriteLastProduct;
  }

  public void setApplianceBuilderUtility(String applianceBuilderUtility) {
    this.applianceBuilderUtility = applianceBuilderUtility;
  }

  public void setVmwareStudioHost(String vmwareStudioHost) {
    this.vmwareStudioHost = vmwareStudioHost;
  }

  public void setVmwareStudioSshIdentityKeyFile(String vmwareStudioSshIdentityKeyFile) {
    this.vmwareStudioSshIdentityKeyFile = vmwareStudioSshIdentityKeyFile;
  }

  public void setVmwareStudioTemplateFile(String vmwareStudioTemplateFile) {
    this.vmwareStudioTemplateFile = vmwareStudioTemplateFile;
  }

  public void setYumRepositoryHost(String yumRepositoryHost) {
    this.yumRepositoryHost = yumRepositoryHost;
  }

  public void setYumRepositorySshIdentityKeyFile(String yumRepositorySshIdentityKeyFile) {
    this.yumRepositorySshIdentityKeyFile = yumRepositorySshIdentityKeyFile;
  }

  public void setSecureConfigurationFile(String secureConfigurationFile) {
    this.secureConfigurationFile = secureConfigurationFile;
  }

  public void setPackagesDirectory(String packagesDirectory) {
    this.packagesDirectory = packagesDirectory;
  }

  public void setApplianceSaveZipFile(String applianceSaveZipFile) {
    this.applianceSaveZipFile = applianceSaveZipFile;
  }

  /**
   * Determine whether validate preconditions are met before the build can proceed.
   * 
   * @throws IllegalStateException if a critical parameter is unset or some other operational mode
   *                               expectation is in contravention with internal logic.
   */
  private void validate() throws IllegalStateException {
    Map<String, String> attributeObjectAndNameMapping = new HashMap<String, String>();

    attributeObjectAndNameMapping.put("applianceBuilderUtility", applianceBuilderUtility);
    attributeObjectAndNameMapping.put("vmwareStudioHost", vmwareStudioHost);
    attributeObjectAndNameMapping.put("vmwareStudioSshIdentityKeyFile", vmwareStudioSshIdentityKeyFile);
    attributeObjectAndNameMapping.put("vmwareStudioTemplateFile", vmwareStudioTemplateFile);
    attributeObjectAndNameMapping.put("yumRepositoryHost", yumRepositoryHost);
    attributeObjectAndNameMapping.put("yumRepositorySshIdentityKeyFile", yumRepositorySshIdentityKeyFile);
    attributeObjectAndNameMapping.put("secureConfigurationFile", secureConfigurationFile);
    attributeObjectAndNameMapping.put("packagesDirectory", packagesDirectory);
    attributeObjectAndNameMapping.put("applianceSaveZipFile", applianceSaveZipFile);

    for (String key : attributeObjectAndNameMapping.keySet()) {
      if (attributeObjectAndNameMapping.get(key) == null) {
        throw new IllegalStateException("'" + key + "' must be set.");
      }
    }

    if (new File(applianceSaveZipFile).exists() &&  !overwriteLastProduct) {
      throw new IllegalStateException("'" + applianceSaveZipFile
          + "' exists and the build is instructed not to overwrite.");
    }
  }

  /**
   * The entry-point for Apache Ant tasks, this method does the real work for the build.
   *
   * @throws BuildException
   */
  @Override
  public void execute() throws BuildException {
    log("Examining build environment and rules ...", Project.MSG_INFO);
    try {
      validate();
    } catch (IllegalStateException e) {
      throw new BuildException(e);
    }

    log("Starting the appliance builder ...", Project.MSG_INFO);

    ProcessBuilder processBuilder = new ProcessBuilder(applianceBuilderUtility,
        vmwareStudioHost, vmwareStudioSshIdentityKeyFile, vmwareStudioTemplateFile,
        yumRepositoryHost, yumRepositorySshIdentityKeyFile, secureConfigurationFile,
        packagesDirectory, applianceSaveZipFile);
    processBuilder.directory(new File("."));
    try {
      Process applianceBuilder = processBuilder.start();
      log("The build is running; it will likely take more than 15 minutes to finish ...",
          Project.MSG_INFO);
      if (applianceBuilder.waitFor() != EXPECTED_RETURN_VALUE) {
        log("Build log:", Project.MSG_ERR);
        log("---", Project.MSG_ERR);
        for (InputStream output : new InputStream[] {applianceBuilder.getInputStream(), applianceBuilder.getErrorStream()}) {
          BufferedReader builderOutput = new BufferedReader(new InputStreamReader(output));
          String line;
          while ((line = builderOutput.readLine()) != null) {
            log(line, Project.MSG_ERR);
          }

        }
        log("---", Project.MSG_ERR);
        throw new BuildException("Appliance build failed.");
      }
    } catch (IOException e) {
      throw new BuildException(e);
    } catch (InterruptedException e) {
      throw new BuildException(e);
    }
    log("Done building ...", Project.MSG_INFO);
  }
}
