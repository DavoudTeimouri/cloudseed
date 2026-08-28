# CloudSeed Guide — Create & Apply Configurations (No ISO)

CloudSeed produces **configuration files only** — no seed ISO is built. This guide shows how to apply those files to new VMs on VMware vSphere, KVM, and Physical/Other, for both Linux (cloud-init) and Windows (Cloudbase-Init + Sysprep).

---

## 1. What CloudSeed outputs

**Output directory structure** — files are organized into platform/OS specific subdirectories:

```
out/
├── vsphere-linux/
│   ├── user-data
│   ├── meta-data
│   ├── cloudseed.json
│   └── README.txt
├── kvm-windows/
│   ├── cloudbase-init.conf
│   ├── cloudbase-init-unattend.conf
│   ├── sysprep-unattend.xml
│   ├── run-sysprep.bat
│   ├── cloudseed.json
│   └── README.txt
└── physical-linux/
    ├── user-data
    ├── meta-data
    ├── cloudseed.json
    └── README.txt
```

**Linux** (`out/<platform>-linux/`)
- `user-data` — the cloud-config customization
- `meta-data` — instance identity (hostname)
- `cloudseed.json` — the config itself (re-run or tweak later)
- `README.txt` — quick reference with warnings

**Windows** (`out/<platform>-windows/`)
- `cloudbase-init.conf` / `cloudbase-init-unattend.conf` — Cloudbase-Init service config
- `sysprep-unattend.xml` — Sysprep answer file (generates a **new SID**)
- `run-sysprep.bat` — runs Sysprep generalize
- `cloudseed.json`, `README.txt`

**vSphere extras** (when enabled, in `out/vsphere-<os>/`)
- `vsphere-customization-spec.xml` — vSphere Guest Customization Specification (XML)
- `vsphere-pre-script.sh/.bat` — Pre-customization script (runs before cloud-init/Cloudbase-Init)
- `vsphere-post-script.sh/.bat` — Post-customization script (runs after cloud-init/Cloudbase-Init)

---

## 2. Platform Conflict Avoidance (Important!)

**By default, CloudSeed lets the platform (vSphere/KVM) handle hostname.** This avoids conflicts where both cloud-init and the platform try to set the hostname.

### Hostname Options
- **Platform sets hostname** (default): vSphere/KVM assigns the VM name. cloud-init receives it via guestinfo/metadata.
- **CloudSeed sets hostname**: Disable "Let Platform Set Hostname" module, provide prefix or explicit hostname.

### Network Options
- **Platform handles network** (enable "Let Platform Handle Network"): vSphere/KVM applies IP/DNS via guest customization. cloud-init skips network config.
- **cloud-init handles network** (default): cloud-init applies network config (v2 for Linux, netsh for Windows).

### NTP Options
- **Platform handles NTP** (enable "Let Platform Handle NTP"): vSphere/KVM syncs time. cloud-init skips NTP config.
- **cloud-init handles NTP** (default): cloud-init configures systemd-timesyncd/chrony (Linux) or Cloudbase-Init NTP plugin (Windows).

> **Note:** Platform modules (`platform_hostname`, `platform_network`, `platform_ntp`) are now available for **all platforms** (vSphere, KVM, Physical/Other). When a platform module is selected, its cloud-init equivalent is auto-disabled (and vice versa).

> **Recommendation for vSphere**: Enable all three "Let Platform Handle..." modules for a clean separation — vSphere Guest Customization handles identity/network/time, cloud-init handles user/packages/scripts.

---

## 3. Linux on KVM (libvirt)

The cleanest path is `virt-install` / `virsh` injecting `user-data` + `meta-data` directly (no ISO):

```bash
virt-install \
  --name web01 \
  --memory 2048 --vcpus 2 \
  --disk size=20 \
  --os-variant ubuntu22.04 \
  --cloud-init user-data=./out/user-data,meta-data=./out/meta-data
```

Or for an existing domain, copy into the image's cloud-init drop-in before first boot (golden-image approach):

```bash
sudo install -D -m 0600 out/user-data /etc/cloud/cloud.cfg.d/99-cloudseed.cfg
# also drop meta-data-derived hostname, then:
sudo cloud-init clean --reboot
```

Verify after boot: `sudo cloud-init status --long`.

---

## 4. Linux on VMware vSphere

vSphere reads cloud-init via **guestinfo** (vApp properties) — no CD-ROM needed.

### Option A: vApp guestinfo (recommended)

Set these extra config keys on the VM (via `govc`, PowerCLI, or the UI "VM Options → Advanced → Configuration Parameters"):

| Key | Value |
|-----|-------|
| `guestinfo.userdata` | contents of `out/user-data` |
| `guestinfo.userdata.encoding` | `text` |
| `guestinfo.metadata` | contents of `out/meta-data` |
| `guestinfo.metadata.encoding` | `text` |

```bash
govc vm.change -vm web01 \
  -e guestinfo.userdata="$(cat out/user-data)" \
  -e guestinfo.userdata.encoding=text \
  -e guestinfo.metadata="$(cat out/meta-data)" \
  -e guestinfo.metadata.encoding=text
```

### Option B: golden image drop-in

On the template VM before conversion to template:

```bash
sudo install -D -m 0600 out/user-data /etc/cloud/cloud.cfg.d/99-cloudseed.cfg
sudo cloud-init clean --machine-id   # clears per-instance state so next boot re-runs
sudo shutdown -h now
# convert to template
```

### Option C: vSphere Guest Customization Spec (NEW)

Use the exported `vsphere-customization-spec.xml` with vSphere Guest Customization:

1. In vCenter, go to **Policies and Profiles** → **Customization Specifications**
2. Import the XML file
3. When deploying a VM, select the customization spec
4. vSphere handles hostname, network, domain, time zone — cloud-init only handles user/packages/scripts

> **Note**: This requires "Let Platform Handle..." modules enabled for clean separation.

---

## 5. vSphere Pre/Post Customization Scripts (NEW)

CloudSeed generates sample scripts you can customize:

- **Pre-script** (`vsphere-pre-script.sh/.bat`): Runs during vSphere Guest Customization, **before** cloud-init/Cloudbase-Init. Use for: registering with Satellite/Foreman, installing agents, configuring repos, setting up SSH/WinRM.
- **Post-script** (`vsphere-post-script.sh/.bat`): Runs after cloud-init/Cloudbase-Init completes. Use for: joining AD domain, compliance checks, registering with monitoring, security hardening.

### Linux Usage
```bash
# Pre-script: place in guest customization or run via cloud-init bootcmd
# Post-script: add to cloud-init runcmd or systemd service
```

### Windows Usage
```bat
REM Pre-script: runs via vSphere Guest Customization "Run Once" command
REM Post-script: runs via Cloudbase-Init LocalScriptsPlugin or Task Scheduler
```

---

## 6. Windows — Cloudbase-Init

Install [Cloudbase-Init](https://cloudbase.it/cloudbase-init/) on the golden image. Then place the generated configs:

```
C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf
C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init-unattend.conf
```

Cloudbase-Init pulls `user-data`/`meta-data` from a **config drive** (attached ISO/VMDK) or, on vSphere, from guestinfo the same way as Linux. The user, SSH keys, hostname, NTP and first-boot scripts are applied on first boot.

> SSH on Windows requires the OpenSSH Server feature + Cloudbase-Init's `SetUserSSHPublicKeysPlugin` (already enabled in the generated conf).

### Windows static IP (no config drive)

When `net_mode` is `static`, CloudSeed emits `netsh` commands as a first-boot script so the IP is applied even without a config drive:

```bat
netsh interface ip set address "Ethernet" static 192.168.1.60 255.255.255.0 192.168.1.1
netsh interface ip add dns "Ethernet" 8.8.8.8 index=1
```

These run on first boot via Cloudbase-Init. DHCP is used when `net_mode` is `dhcp` (the default).

---

## 7. Windows — Sysprep (CRITICAL: new SID)

**Never clone a Windows VM without generalizing it.** Duplicated SIDs break domain join, GPO, WSUS, and file/registry ACLs. CloudSeed emits a ready Sysprep answer file.

1. On the prepared golden VM (Cloudbase-Init already installed + `.conf` files placed):
2. Copy `sysprep-unattend.xml` and `run-sysprep.bat` into the same folder.
3. Run **as Administrator**:

```bat
run-sysprep.bat
```

This runs:

```
C:\Windows\System32\sysprep\sysprep.exe /generalize /oobe /shutdown /unattend:sysprep-unattend.xml
```

The VM **shuts down**. It now has a pending generalize — the **next power-on** creates a fresh computer SID, new hostname (`WIN-*` random), resets the activation grace, and runs Cloudbase-Init to apply CloudSeed config.

4. Now convert to template / clone. Every clone gets a unique SID.

> If you skip Sysprep and just clone, you will have duplicate SIDs — fix with `sysprep /generalize` (or `New-SID` tooling) before joining any domain.

---

## 8. Physical / Other Platforms

For bare metal, PXE boot, config drive, or other provisioning:

1. Generate config with platform = "physical"
2. Use `user-data`/`meta-data` with your provisioning method:
   - **Config drive**: Place files in `openstack/latest/user_data` and `openstack/latest/meta_data.json`
   - **ISO**: Generate seed ISO with `cloud-localds` (not built by CloudSeed)
   - **PXE/HTTP**: Serve files via HTTP, pass URL via kernel cmdline (`ds=nocloud-net;s=http://server/`)
3. Windows: same Cloudbase-Init config files, deliver via config drive or Floppy/ISO

---

## 9. Module-specific application notes

### Network (static) — Linux
The generated `user-data` includes `network: {version: 2, ethernets: {eth0: {...}}}` — cloud-init applies this on first boot. Ensure the interface name (`eth0`, `ens192`, etc.) matches your target image.

### Network (static) — Windows
First-boot script runs `netsh` commands. If interface name differs from "Ethernet", edit `run-sysprep.bat` or the generated `firstboot` commands before sealing.

### Disk grow (growpart) — Linux
Requires `growpart` package on the target image (usually pre-installed on cloud images). CloudSeed configures `growpart: {mode: auto, devices: ["/dev/sda1"]}`. Verify device/partition matches your image.

### Packages — Linux
`package_upgrade: true` runs `apt upgrade` / `dnf upgrade` on first boot. List additional packages in `packages: ["nginx", "docker.io"]`.

### NTP — Linux + Windows
Linux: `ntp: {servers: ["pool.ntp.org"]}` configures systemd-timesyncd / chrony.
Windows: Cloudbase-Init `SetNtpClientPlugin` applies the same servers.

### Write files — Linux + Windows
Arbitrary files written to target. Linux uses `write_files:` in cloud-config. Windows uses Cloudbase-Init `LocalScriptsPlugin` — files placed in `C:\Program Files\Cloudbase Solutions\Cloudbase-Init\LocalScripts\`.

### First-boot commands — Linux + Windows
Linux: `runcmd:` in cloud-config. Windows: `LocalScriptsPlugin` runs `.bat`/`.ps1` from LocalScripts folder.

---

## 10. Detect cloud-init version on target

Run on your golden image or running VM:

```bash
cloud-init --version
```

CloudSeed also provides:

```bash
cloudseed --detect-cloud-init
```

This checks the local system and prints compatibility table.

---

## 11. Write directly to cloud-init config path (Linux)

For immediate testing on a running Linux VM:

```bash
cloudseed --write-to-cloud-init-path --json config.json
```

This writes `user-data` to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` (requires root). Then:

```bash
sudo cloud-init clean --reboot
```

⚠️ **Warning:** This modifies the running system. Use on test VMs only.

---

## 12. Re-using a config

`cloudseed.json` is the full config. Re-apply without the menu:

```bash
cloudseed --json out/cloudseed.json --out out2
```

---

## 13. Portable binary

Build a single-file executable (no Python install needed on target):

```bash
pip install pyinstaller
python build_dist.py
# produces dist/cloudseed (Linux) / dist/cloudseed.exe (Windows)
```

The binary is fully self-contained and runs the same menu on Windows and Linux.

---

## 14. Toolbox — External Tools (v1.1.0+)

### Windows SID Change without Sysprep

Alternative to Sysprep for already-cloned Windows VMs:

```bash
cloudseed  # Main Menu → Toolbox → Download SID Changer
```

- Downloads `sidchanger.exe` (from stratus/sidchanger)
- Copy to target Windows VM
- Run as Administrator: `sidchanger.exe`
- Reboot — Machine SID changed without full Sysprep

**Warning**: Only use on cloned VMs that were NOT sysprepped. This is a workaround, not a replacement for proper image preparation.

---

## 15. Config Validator (v1.1.0+)

Validate exported configurations **after generation** or on existing config directories:

```bash
cloudseed  # Main Menu → Config Validator → Validate a config directory
```

Checks:
- **No persistent runs**: `runcmd` (per-instance), `bootcmd` (every boot), `phone_home`, package update/upgrade
- **cloudseed.json consistency**: required fields, module/file matching
- **Windows**: sysprep-unattend.xml (generalize/specialize/oobe passes), Cloudbase-Init configs

### Example: Validate a config directory

```bash
$ cloudseed
# Select: Config Validator
# Select: Validate a config directory
# Enter path: ./cloudseed-out

Validating: ./cloudseed-out
==========================
DIAGNOSIS SUMMARY
==========================
Cloud-init: 24.1 (✅ Fully supported (all modules))
Status: done
Errors: 0
Warnings: 2
==========================
⚠️  WARNINGS:
  - [cloud_init] runcmd present - commands run on first boot only (per-instance). Verify they are idempotent.
  - [cloud_init] NTP configured in cloud-init - may conflict with platform/OS NTP. Consider 'Let Platform Handle NTP'.
```

---

## 16. Cloud-Init Doctor (v1.1.0+)

Diagnose cloud-init issues on a **running system** (requires cloud-init installed locally):

```bash
cloudseed  # Main Menu → Cloud-Init Doctor → Full Diagnosis
```

Checks:
- **Cloud-init status**: version, enabled, running, stage completion (generator, local, network, config, final)
- **Configuration**: merged config query, config file locations
- **Boot & services**: systemd status for all cloud-init services, failed units
- **Network**: netplan, networkd, current interfaces
- **Disk space**: df output with low-space warnings
- **Save report**: JSON output for CI/CD integration

### Example: Full diagnosis output

```bash
$ cloudseed
# Select: Cloud-Init Doctor
# Select: Full Diagnosis

Running comprehensive cloud-init health check...
============================================================
DIAGNOSIS SUMMARY
============================================================
Timestamp: 2026-08-28T10:30:45.123456
Platform: Linux-6.8.0-138-generic-x86_64-with-glibc2.39
Cloud-init: 24.1 (✅ Fully supported (all modules))
Status: done
Errors: 0
Warnings: 1
============================================================
⚠️  WARNINGS:
  - [cloud_init] cloud-init analyze show failed: cloud-init analyze not available
```

### Save diagnosis report for CI/CD

```bash
# Select: Save Diagnosis Report (JSON)
# Output: cloudseed-doctor-20260828-103045.json
```

The JSON report contains all checks for automated processing.

---

## 17. Complete workflow: Create a template VM (Linux)

```bash
# 1. Generate config
cloudseed
# ... select KVM, Linux, modules, output to ./cloudseed-out

# 2. Create VM from cloud image
virt-install \
  --name ubuntu-template \
  --memory 4096 --vcpus 2 \
  --disk size=30,bus=virtio \
  --os-variant ubuntu22.04 \
  --cloud-init user-data=./cloudseed-out/user-data,meta-data=./cloudseed-out/meta-data

# 3. Wait for first boot, verify
ssh admin@<vm-ip> "cloud-init status --long"

# 4. Clean for template
ssh admin@<vm-ip> "sudo cloud-init clean --machine-id && sudo shutdown -h now"

# 5. Convert to template (virsh, virt-manager, or vSphere)
```

---

## 18. Complete workflow: Create a template VM (Windows)

```bash
# 1. Generate config
cloudseed
# ... select vSphere, Windows, modules (include sysprep), output to ./cloudseed-out

# 2. Install Windows + Cloudbase-Init on a VM

# 3. Copy generated files:
#    cloudbase-init.conf, cloudbase-init-unattend.conf → C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\
#    sysprep-unattend.xml, run-sysprep.bat → C:\Temp\ (or any folder)

# 4. Run as Administrator:
#    C:\Temp\run-sysprep.bat

# 5. VM shuts down. Convert to template in vSphere.

# 6. Deploy from template — each clone gets unique SID + CloudSeed config
```

---

## 19. Complete workflow: vSphere with Guest Customization Spec (NEW)

```bash
# 1. Generate config with vSphere modules:
cloudseed
# ... select vSphere, Linux/Windows
# ... enable: platform_hostname, platform_network, platform_ntp
# ... enable: vsphere_spec, vsphere_scripts
# ... customize pre/post scripts if needed
# ... output to ./cloudseed-out

# 2. Import Customization Spec in vCenter:
#    Policies and Profiles → Customization Specifications → Import
#    Select: ./cloudseed-out/vsphere-customization-spec.xml

# 3. Deploy VM from template:
#    Right-click template → Deploy VM → Customize using existing spec
#    Select: CloudSeed-Spec (or your custom name)

# 4. (Optional) Use pre/post scripts:
#    Pre-script: runs during Guest Customization "Run Once"
#    Post-script: add to cloud-init runcmd (Linux) or LocalScripts (Windows)

# 5. Each deployed VM gets: unique hostname, correct network, synced time,
#    plus cloud-init user/packages/scripts
```

---

## 20. Complete workflow: Validate and diagnose after deployment

```bash
# After deploying VMs, validate the generated config was applied correctly:

# 1. On the running VM, run Cloud-Init Doctor:
cloudseed  # Main Menu → Cloud-Init Doctor → Full Diagnosis

# 2. Or save report for centralized monitoring:
#    Main Menu → Cloud-Init Doctor → Save Diagnosis Report (JSON)
#    Upload cloudseed-doctor-*.json to your monitoring system

# 3. For CI/CD pipelines, run validator on generated configs:
cloudseed  # Main Menu → Config Validator → Validate a config directory
# Checks that configs won't re-run unexpectedly after first boot
```

---

## 21. Banner and Menu Overview (v1.1.0+)

All menus display a consistent banner:

```
============================================================
  CloudSeed v1.5.0
  cloud-init / Cloudbase-Init VM Template Generator
  Main Menu
============================================================

  1) Generate Configuration
  2) Toolbox (External Tools)
  3) Config Validator
  4) Cloud-Init Doctor
  5) Template Maker
  6) Guide Help (Configuration Reference)
  7) Exit
```

Each sub-menu shows:
- **Title** in colored section header (e.g., "Module Selection", "Network Configuration")
- **Description** of what the menu does
- **Default values** in [brackets]
- **Numbered options** for easy selection
- **0) ← Back** to return to previous menu

### Module Selection (Generate Configuration → Platform → OS)

The module selection screen now shows **all available modules** with real-time toggle:

```
============================================================
  CloudSeed v1.5.0
  Module Selection (Linux / vSphere)
============================================================

Available modules (toggle by number, 'c' to configure selected, 'a'=all, 'n'=none):

  [ ] 1) hostname              - Set hostname via cloud-init
  [✓] 2) platform_hostname    - Let platform set VM hostname
  [ ] 3) users                - Create admin user + password
  [ ] 4) ssh                  - SSH authorized keys + password auth
  [ ] 5) root                 - Harden root (disable root SSH login)
  [ ] 6) network              - Network (DHCP / static IP)
  [✓] 7) platform_network     - Let platform handle network
  [ ] 8) packages             - Install OS packages / upgrade
  [ ] 9) locale               - Locale + keyboard + timezone
  [ ] 10) disk                - Grow root filesystem (growpart)
  [ ] 11) ntp                 - NTP time servers
  [✓] 12) platform_ntp        - Let platform handle NTP
  [ ] 13) files               - Write arbitrary files
  [ ] 14) bootcmd             - Early boot commands
  [ ] 15) firstboot           - First-boot commands (runcmd)
  [ ] 16) final               - Final status message
  [ ] 17) vsphere_spec        - vSphere Customization Spec (XML)
  [ ] 18) vsphere_scripts     - vSphere Pre/Post Scripts

Commands: [number] toggle | c=configure | a=all | n=none | 0=back
```

**Key behaviors:**
- **Platform modules always visible** — `platform_hostname`, `platform_network`, `platform_ntp` shown for vSphere, KVM, and Physical/Other
- **Real-time conflict resolution** — selecting a platform module auto-disables its cloud-init equivalent (and vice versa) with info message
- **Defaults**: platform modules ON, cloud-init equivalents OFF
- Press `c` to enter per-module configuration flow (each selected module configured one-by-one)
- Press `0` to go back to OS selection

### Per-Module Configuration Flow

After pressing `c`, each selected module is configured sequentially with its own sub-menu. Example for Network module:

```
============================================================
  CloudSeed v1.5.0
  Network Configuration
============================================================

Configure network for the target VM.

  1) Mode: DHCP (default) or Static
  2) Interface: eth0
  3) Address: (static only)
  4) Netmask: 255.255.255.0 (static only)
  5) Gateway: (static only)
  6) DNS: 8.8.8.8,1.1.1.1
  7) Search domains: 

Press Enter for default [value], type to override. 0=back to module selection.
```

Each module's configuration applies defaults if you press Enter. You can go back to module selection from any sub-menu.

---

## 22. Graceful shutdown

Press `Ctrl+C` at any prompt to exit cleanly:

```
[CloudSeed] Interrupted. Shutting down gracefully...
```

---

## License

MIT