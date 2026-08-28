CloudSeed generated configuration (NO ISO -- config files only)
================================================================
Platform : VMware vSphere
Guest OS : Windows (Cloudbase-Init + Sysprep)
Modules  : firstboot, vsphere_spec, sysprep, vsphere_scripts, users, ssh, platform_hostname, platform_network, files, platform_ntp

Files produced:
  cloudbase-init.conf            - main service config
  cloudbase-init-unattend.conf   - unattend-phase config
  sysprep-unattend.xml           - Sysprep answer file (new SID)
  run-sysprep.bat                - launch Sysprep generalize
  cloudseed.json                 - this config (re-usable)

Apply (no ISO) - see GUIDE.md for full steps:
  Linux : guestinfo/vApp OR drop into /etc/cloud/cloud.cfg.d/ on image.
  Windows: place .conf in Cloudbase-Init conf dir; run run-sysprep.bat
           BEFORE sealing the template.
