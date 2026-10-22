# CloudSeed Guide — Create & Apply Configurations

CloudSeed produces **configuration files** for VM templates. This guide shows how to apply those files to new VMs on VMware vSphere, KVM, and Physical/Other, for both Linux (cloud-init) and Windows (Cloudbase-Init + Sysprep).

---

## 1. What CloudSeed outputs

**Output directory structure** — files are organized into platform/OS specific subdirectories:

```
out/
├── vsphere-linux/
│   ├── user-data
│   ├── meta-data
│   ├── cloudseed.yaml
│   └── README.txt
├── kvm-windows/
│   ├── cloudbase-init.conf
│   ├── cloudbase-init-unattend.conf
│   ├── user-data
│   ├── sysprep-unattend.xml
│   ├── run-sysprep.bat
│   ├── cloudseed.yaml
│   └── README.txt
└── physical-linux/
    ├── user-data
    ├── meta-data
    ├── cloudseed.yaml
    └── README.txt
```

**Linux** (`out/<platform>-linux/`)
- `user-data` — the cloud-config customization
- `meta-data` — instance identity (hostname)
- `cloudseed.yaml` — the config itself (re-run or tweak later)
- `README.txt` — quick reference with warnings

**Windows** (`out/<platform>-windows/`)
- `cloudbase-init.conf` / `cloudbase-init-unattend.conf` — Cloudbase-Init service config
- `user-data` — the cloud-config customization (Cloudbase-Init reads the same dialect as cloud-init)
- `sysprep-unattend.xml` — Sysprep answer file (generates a **new SID**)
- `run-sysprep.bat` — runs Sysprep generalize
- `cloudseed.yaml`, `README.txt`

**vSphere extras** (when enabled, in `out/vsphere-<os>/`)
- `vsphere-customization-spec.xml` — vSphere Guest Customization Specification (XML)
- `vsphere-pre-script.sh/.bat` — Pre-customization script (runs before cloud-init/Cloudbase-Init)
- `vsphere-post-script.sh/.bat` — Post-customization script (runs after cloud-init/Cloudbase-Init)

**Template extras** (when `template_best_practices` is enabled)
- `template-cleanup.sh` / `template-cleanup.bat` — the golden-image cleanup script to run before sealing the VM

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
cloudseed detect-cloud-init
```

This checks the local system and prints the version and a compatibility verdict.

---  

## 11. Write directly to cloud-init config path (Linux)

For immediate testing on a running Linux VM:

```bash
cloudseed write-to-cloud-init-path --config config.yaml
```

This writes `user-data` to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` (requires root). Then:

```bash
sudo cloud-init clean --reboot
```

⚠️ **Warning:** This modifies the running system. Use on test VMs only.

---  

## 12. Re-using a config

`cloudseed.yaml` is the full config. Re-apply without the menu:

```bash
cloudseed generate --config out/cloudseed.yaml --output out2
```

---  

## 13. Portable binary

Build a single-file executable (no Rust install needed on target):

```bash
cargo build --release --package cloudseed-cli
# produces target/release/cloudseed (Linux) / cloudseed.exe (Windows)
```

Pre-built binaries for both platforms are published on the
[GitHub Releases](https://github.com/DavoudTeimouri/cloudseed/releases) page.

---  


Validate exported configurations **after generation** or on existing config directories:

```bash
cloudseed validate --config ./cloudseed-out
```

Checks:
- **Required fields**: `version`, `name`, `platform`, `os_type`
- **Known values**: platform, OS type and every module name are checked against the supported set
- **Credentials**: a plaintext password is reported; `--fix-it` replaces it with a real SHA-512 crypt hash
- **Reachability**: static networking without an address or gateway is reported
- **Windows**: a Windows target without `sysprep` is reported, because cloned VMs would share a SID

### Example: Validate a config directory

```bash
$ cloudseed validate --config ./cloudseed-out
./cloudseed-out/vsphere-linux/cloudseed.yaml: Validation failed with 1 issue(s):
  - password: password is stored in plaintext; hash it or set plaintext_password: true
./cloudseed-out/kvm-linux/cloudseed.yaml: Configuration is valid.

Checked 2 config(s), 1 with issues.
```

---


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

# 4. Clean for template (REQUIRED - run on the VM before converting to template)
ssh admin@<vm-ip> "sudo cloud-init clean --machine-id --logs && sudo rm -f /etc/machine-id /var/lib/dbus/machine-id && sudo shutdown -h now"

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

# 1. On the running VM, check the cloud-init version and its support status:
cloudseed detect-cloud-init

# 2. For CI/CD pipelines, validate the generated configs:
cloudseed validate --config ./cloudseed-out
# Checks that configs won't re-run unexpectedly after first boot

# 3. Validate a single config and auto-fix a plaintext password:
cloudseed validate --config ./cloudseed-out/vsphere-linux/cloudseed.yaml --fix-it
```

---

## 21. Template Best Practices

The `template_best_practices` module prepares a target image to become a golden
image. When it is enabled, CloudSeed writes a cleanup script next to the
configuration and explains in `README.txt` what to run before sealing the VM.

### Linux Best Practices
- **Log cleanup**: Truncate `/var/log/*.log`, vacuum the systemd journal
- **Temp files**: Clean `/tmp`, `/var/tmp`
- **SSH host keys**: Remove `/etc/ssh/ssh_host_*` (regenerated on first boot)
- **Machine-id**: Remove `/etc/machine-id` and `/var/lib/dbus/machine-id`
- **Package cache**: `apt clean`, `dnf clean all`, `zypper clean`, `yum clean all`
- **Cloud-init**: `cloud-init clean --machine-id --logs --seed`
- **Udev rules**: Remove persistent net rules (`/etc/udev/rules.d/70-persistent-net.rules`)

### Windows Best Practices
- **Event Logs**: Clear System, Security, Application logs via `wevtutil cl`
- **Windows Update cache**: Clean `C:\Windows\SoftwareDistribution\Download`
- **DriverStore**: Remove old drivers via `pnputil /delete-driver`

### Usage
1. Enable the `template_best_practices` module in the configuration
2. Generate the configuration
3. Copy `template-cleanup.sh` (or `template-cleanup.bat`) to the target
4. Run it on the target as root/Administrator, just before shutting the VM down
5. Convert the VM to a template

> **Note**: The module does not change the generated `user-data`/`meta-data`.
> It adds the cleanup script and the instructions that explain how to seal the
> image correctly, so every clone gets a fresh identity — a new machine-id, new
> SSH host keys, and on Windows a new SID.

---\n## 22. Command and TUI Overview

### Commands

CloudSeed is driven by subcommands. Every one of them exits `0` on success and
`1` on failure, so they can be chained in a pipeline or used as a CI gate.

| Command | Purpose |
|---------|---------|
| `generate` | Write the configuration files for a platform/OS pair |
| `validate` | Check a config file, or every config in a directory |
| `completion` | Emit a shell completion script |
| `timezone` | Interactively pick an IANA timezone and write it to the config |
| `tui` | Open the interactive terminal interface |
| `detect-cloud-init` | Report the local cloud-init version and its support status |
| `write-to-cloud-init-path` | Write the generated config to a running Linux host |

Global flags: `--verbose` (repeat for more), `--quiet`, `--json-logs`.

### Terminal User Interface

`cloudseed tui` opens a ratatui interface with four regions:

```
+--------------------------------------------------------------+
| Generate  Validate  Completion  Timezone                      |  <- menu bar
+----------------------+---------------------------------------+
| Run generate         |                                       |
|                      |   action panel: form, timezone        |
|                      |   picker, or command output           |
+----------------------+---------------------------------------+
```

| Key | Menu bar | Command list | Form | Timezone |
|-----|----------|---------------|------|----------|
| `←` `→` | move between entries | — | — | switch column |
| `↑` `↓` | — | move the highlight | move between fields | move within the column |
| `Enter` | open the menu | run the command | submit the form | pick the zone |
| `Esc` | quit | back to the menu bar | back to the menu bar | back to the command list |
| `q` | quit | — | — | — |
| `Ctrl+C` | quit | quit | quit | quit |

The timezone picker is hierarchical: the left column holds the IANA regions,
the right column the zones in the selected region. The last entry of the left
column is **Custom…**, which takes a free-form IANA zone.

The TUI and the CLI share the same command functions, so a command that works
in one works identically in the other.

### Modules

The `modules` list in the configuration selects what is generated. An empty
list means every module is enabled.

| Module | Effect |
|--------|--------|
| `hostname` | Set the hostname, and manage `/etc/hosts` |
| `users` | Create the primary user with its password, sudo and groups |
| `ssh` | Authorize SSH keys and set the password-authentication policy |
| `root` | Disable root SSH logins |
| `network` | Configure the interface (DHCP or static) and DNS |
| `packages` | Install packages and run the package upgrade |
| `locale` | Set the locale, keyboard layout and timezone |
| `disk` | Grow the root partition |
| `ntp` | Configure the NTP servers |
| `files` | Write files to the target |
| `bootcmd` | Run commands on every boot |
| `firstboot` | Run commands once, on the first boot |
| `final` | Print a final message when the boot completes |
| `template_best_practices` | Add the golden-image cleanup script and instructions |
| `platform_hostname` | Let the platform set the hostname (disables `hostname`) |
| `platform_network` | Let the platform configure the network (disables `network`) |
| `platform_ntp` | Let the platform configure NTP (disables `ntp`) |
| `vsphere_spec` | Export the vSphere Guest Customization Specification |
| `vsphere_scripts` | Emit the vSphere pre/post customization scripts |

A `platform_*` module and its cloud-init counterpart are mutually exclusive.
Setting `use_platform_hostname`, `let_platform_handle_network` or
`let_platform_handle_ntp` in the configuration disables the matching module
automatically, so cloud-init never fights the hypervisor over the same
concern.

---  

## 23. Graceful shutdown

Press `Ctrl+C` in the TUI to exit at any time. The terminal is restored to its
normal mode on the way out.

---

## License

MIT