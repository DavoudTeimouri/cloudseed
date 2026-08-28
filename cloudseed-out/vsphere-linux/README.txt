CloudSeed generated configuration (NO ISO -- config files only)
================================================================
Platform : VMware vSphere
Guest OS : Linux (cloud-init)
Modules  : platform_ntp, packages, root, firstboot, platform_network, vsphere_scripts, bootcmd, final, locale, users, platform_hostname, files, vsphere_spec, ssh, disk

Files produced:
  user-data   - cloud-config customization
  meta-data   - instance identity
  cloudseed.json - this config (re-usable)

⚠️  Warnings:
  - Disk grow on /dev/sda1 — verify device exists on target image.
  - Package upgrade enabled but package list empty — upgrade runs but installs nothing extra.

Apply (no ISO) - see GUIDE.md for full steps:
  Linux : guestinfo/vApp OR drop into /etc/cloud/cloud.cfg.d/ on image.
  Windows: place .conf in Cloudbase-Init conf dir; run run-sysprep.bat
           BEFORE sealing the template.
