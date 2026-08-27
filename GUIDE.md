# CloudSeed Guide — Create & Apply Configurations (No ISO)

CloudSeed produces **configuration files only** — no seed ISO is built. This
guide shows how to apply those files to new VMs on VMware vSphere and KVM, for
both Linux (cloud-init) and Windows (Cloudbase-Init + Sysprep).

---

## 1. What CloudSeed outputs

**Linux** (`out/`)
- `user-data` — the cloud-config customization
- `meta-data` — instance identity (hostname)
- `cloudseed.json` — the config itself (re-run or tweak later)
- `README.txt` — quick reference

**Windows** (`out/`)
- `cloudbase-init.conf` / `cloudbase-init-unattend.conf` — Cloudbase-Init service config
- `sysprep-unattend.xml` — Sysprep answer file (generates a **new SID**)
- `run-sysprep.bat` — runs Sysprep generalize
- `cloudseed.json`, `README.txt`

---

## 2. Linux on KVM (libvirt)

The cleanest path is `virt-install` / `virsh` injecting `user-data` + `meta-data`
directly (no ISO):

```bash
virt-install \
  --name web01 \
  --memory 2048 --vcpus 2 \
  --disk size=20 \
  --os-variant ubuntu22.04 \
  --cloud-init user-data=./out/user-data,meta-data=./out/meta-data
```

Or for an existing domain, copy into the image's cloud-init drop-in before first
boot (golden-image approach):

```bash
sudo install -D -m 0600 out/user-data /etc/cloud/cloud.cfg.d/99-cloudseed.cfg
# also drop meta-data-derived hostname, then:
sudo cloud-init clean --reboot
```

Verify after boot: `sudo cloud-init status --long`.

---

## 3. Linux on VMware vSphere

vSphere reads cloud-init via **guestinfo** (vApp properties) — no CD-ROM needed.

### Option A: vApp guestinfo (recommended)
Set these extra config keys on the VM (via `govc`, PowerCLI, or the UI
"VM Options → Advanced → Configuration Parameters"):

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

---

## 4. Windows — Cloudbase-Init

Install [Cloudbase-Init](https://cloudbase.it/cloudbase-init/) on the golden
image. Then place the generated configs:

```
C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf
C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init-unattend.conf
```

Cloudbase-Init pulls `user-data`/`meta-data` from a **config drive** (attached
ISO/VMDK) or, on vSphere, from guestinfo the same way as Linux. The user, SSH
keys, hostname, NTP and first-boot scripts are applied on first boot.

> SSH on Windows requires the OpenSSH Server feature + Cloudbase-Init's
> `SetUserSSHPublicKeysPlugin` (already enabled in the generated conf).

### Windows static IP (no config drive)

When `net_mode` is `static`, CloudSeed emits `netsh` commands as a first-boot
script so the IP is applied even without a config drive:

```bat
netsh interface ip set address "Ethernet" static 192.168.1.60 255.255.255.0 192.168.1.1
netsh interface ip add dns "Ethernet" 8.8.8.8 index=1
```

These run on first boot via Cloudbase-Init. DHCP is used when `net_mode`
is `dhcp` (the default).

---

## 5. Windows — Sysprep (CRITICAL: new SID)

**Never clone a Windows VM without generalizing it.** Duplicated SIDs break
domain join, GPO, WSUS, and file/registry ACLs. CloudSeed emits a ready
Sysprep answer file.

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

The VM **shuts down**. It now has a pending generalize — the **next power-on**
creates a fresh computer SID, new hostname (`WIN-*` random), resets the
activation grace, and runs Cloudbase-Init to apply CloudSeed config.

4. Now convert to template / clone. Every clone gets a unique SID.

> If you skip Sysprep and just clone, you will have duplicate SIDs — fix with
> `sysprep /generalize` (or `New-SID` tooling) before joining any domain.

---

## 6. Re-using a config

`cloudseed.json` is the full config. Re-apply without the menu:

```bash
cloudseed --json out/cloudseed.json --out out2
```

---

## 7. Portable binary

Build a single-file executable (no Python install needed on target):

```bash
pip install pyinstaller
python build_dist.py
# produces dist/cloudseed (Linux) / dist/cloudseed.exe (Windows)
```

The binary is fully self-contained and runs the same menu on Windows and Linux.
