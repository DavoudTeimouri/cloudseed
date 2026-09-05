"""CloudSeed data model: config dataclass, module catalog, interactive collector.

No third-party dependencies (Python 3 standard library only).
"""

from __future__ import annotations

import json
import signal
import sys
from dataclasses import asdict, dataclass, field
from typing import List

# Global flag for graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print("\n\n[CloudSeed] Interrupted. Shutting down gracefully...")
    sys.exit(130)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def check_shutdown():
    """Check if shutdown was requested."""
    global _shutdown_requested
    if _shutdown_requested:
        print("\n[CloudSeed] Shutdown requested. Exiting...")
        sys.exit(130)


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BG_BLUE = '\033[44m'
    BG_GRAY = '\033[100m'


def colorize(text: str, color: str) -> str:
    """Apply color if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


def _getch() -> str:
    """Read a single character from stdin without Enter (cross-platform)."""
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch
    except ImportError:
        # Windows fallback
        try:
            import msvcrt
            return msvcrt.getwch()
        except ImportError:
            # Last resort: line-buffered input
            return sys.stdin.read(1)


# Box-drawing characters
BOX = {
    'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝',
    'h': '═', 'v': '║',
    'l': '╠', 'r': '╣', 't': '╦', 'b': '╩', 'x': '╬',
    'lt': '┌', 'rt': '┐', 'lb': '└', 'rb': '┘',
    'lh': '─', 'lv': '│',
    'll': '├', 'rl': '┤', 'tl2': '┬', 'bl2': '┴', 'xl': '┼',
}


def _box_width() -> int:
    """Get terminal width, fallback to 78."""
    import shutil
    try:
        return min(shutil.get_terminal_size().columns, 80)
    except Exception:
        return 78


def _center_text(text: str, width: int) -> str:
    """Center text in given width."""
    visible_len = len(text)
    pad = (width - visible_len) // 2
    return ' ' * max(0, pad) + text


def _plain_len(text: str) -> int:
    """Return visible-ish length after stripping ANSI escape sequences."""
    import re
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


def _fit(text: str, width: int) -> str:
    """Pad/truncate plain text to fit the frame width."""
    raw_len = _plain_len(text)
    if raw_len > width:
        return text[:max(0, width - 1)] + "…"
    return text + " " * (width - raw_len)


def _center_line(text: str, width: int) -> str:
    raw_len = _plain_len(text)
    if raw_len >= width:
        return _fit(text, width)
    left = (width - raw_len) // 2
    right = width - raw_len - left
    return " " * left + text + " " * right


def _frame_line(text: str, width: int, color: str = Colors.BLUE, center: bool = False) -> None:
    body = _center_line(text, width) if center else _fit(text, width)
    print(f"  {colorize(BOX['v'], color)} {body} {colorize(BOX['v'], color)}")


def print_banner(title: str = "", platform: str = "", os_type: str = "", modules_count: int = 0) -> None:
    """Print CloudSeed banner with clean logo, tagline, and status."""
    from . import __version__

    inner_w = min(_box_width() - 4, 76)
    logo = [
        "   _____ _                 _ _____              _ ",
        "  / ____| |               | / ____|            | |",
        " | |    | | ___  _   _  __| | (___   ___  ___  __| |",
        " | |    | |/ _ \\| | | |/ _` |\\___ \\ / _ \\/ _ \\/ _` |",
        " | |____| | (_) | |_| | (_| |____) |  __/  __/ (_| |",
        "  \\_____|_|\\___/ \\__,_|\\__,_|_____/ \\___|\\___|\\__,_|",
    ]
    tagline = f"cloud-init / Cloudbase-Init VM Template Generator  v{__version__}"
    platforms = "vSphere  •  KVM  •  Physical  •  zero runtime deps"

    print()
    print(f"  {colorize(BOX['tl'] + BOX['h'] * (inner_w + 2) + BOX['tr'], Colors.CYAN)}")
    for line in logo:
        _frame_line(line, inner_w, Colors.CYAN, center=True)
    _frame_line("", inner_w, Colors.CYAN)
    _frame_line(tagline, inner_w, Colors.CYAN, center=True)
    _frame_line(platforms, inner_w, Colors.CYAN, center=True)
    print(f"  {colorize(BOX['l'] + BOX['h'] * (inner_w + 2) + BOX['r'], Colors.CYAN)}")

    if platform or os_type or modules_count:
        status_parts = []
        if platform:
            status_parts.append(f"Platform: {platform.capitalize()}")
        if os_type:
            status_parts.append(f"OS: {os_type.capitalize()}")
        status_parts.append(f"Modules: {modules_count}")
        _frame_line("  ".join(status_parts), inner_w, Colors.CYAN)
    elif title:
        _frame_line(title, inner_w, Colors.CYAN, center=True)
    else:
        _frame_line("", inner_w, Colors.CYAN)
    print(f"  {colorize(BOX['bl'] + BOX['h'] * (inner_w + 2) + BOX['br'], Colors.CYAN)}")
    print()


def print_frame(title: str, description: str = "", lines: list = None, footer: str = "", width: int = None) -> None:
    """Print compact framed section. No empty middle row when there is no body."""
    if width is None:
        width = min(_box_width() - 4, 76)
    inner_w = width
    title_display = f" {title} "
    title_len = _plain_len(title_display)
    if title_len > inner_w:
        title_display = title_display[:inner_w - 1] + "…"
        title_len = inner_w
    left = max(0, (inner_w - title_len) // 2)
    right = max(0, inner_w - title_len - left)

    print()
    print(f"  {colorize(BOX['lt'] + BOX['lh'] * left + title_display + BOX['lh'] * right + BOX['rt'], Colors.BLUE)}")
    if description:
        _frame_line(description, inner_w, Colors.BLUE)
    if lines:
        print(f"  {colorize(BOX['ll'] + BOX['lh'] * inner_w + BOX['rl'], Colors.BLUE)}")
        for line in lines:
            prefix = ""
            if line.startswith("▸ "):
                prefix = colorize("▸ ", Colors.BOLD + Colors.GREEN)
                line = line[2:]
            elif line.startswith("☑ "):
                prefix = colorize("☑ ", Colors.GREEN)
                line = line[2:]
            elif line.startswith("☐ "):
                prefix = colorize("☐ ", Colors.GRAY)
                line = line[2:]
            elif line.startswith("  "):
                prefix = "  "
                line = line[2:]
            _frame_line(prefix + line, inner_w, Colors.BLUE)
    if footer:
        print(f"  {colorize(BOX['ll'] + BOX['lh'] * inner_w + BOX['rl'], Colors.BLUE)}")
        _frame_line(footer, inner_w, Colors.BLUE)
    print(f"  {colorize(BOX['lb'] + BOX['lh'] * inner_w + BOX['rb'], Colors.BLUE)}")


def print_section(title: str, description: str = "") -> None:
    """Print a compact framed section header."""
    print_frame(title, description)


def print_info(msg: str) -> None:
    """Print info message."""
    print(f"  {colorize('ℹ', Colors.CYAN)} {msg}")


def print_warn(msg: str) -> None:
    """Print warning message."""
    print(f"  {colorize('⚠', Colors.YELLOW)} {colorize(msg, Colors.YELLOW)}")


def print_error(msg: str) -> None:
    """Print error message."""
    print(f"  {colorize('✗', Colors.RED)} {colorize(msg, Colors.RED)}")


def print_success(msg: str) -> None:
    """Print success message."""
    print(f"  {colorize('✓', Colors.GREEN)} {colorize(msg, Colors.GREEN)}")


@dataclass
class TemplateConfig:
    # selection
    platform: str = "vsphere"          # "vsphere" | "kvm" | "physical"
    os_type: str = "linux"             # "linux" | "windows"
    modules: List[str] = field(default_factory=list)

    # --- identity ---
    hostname: str = ""  # Empty = auto-generate from platform/prefix
    hostname_prefix: str = "vm"        # Prefix for auto-generated hostname
    use_platform_hostname: bool = True  # Let platform (vSphere/KVM) set hostname

    # --- users ---
    username: str = "admin"
    password: str = "ChangeMe!123"
    plaintext_password: bool = False    # emit plaintext instead of hashed (discouraged)
    password_rounds: int = 5000
    sudo: bool = True
    lock_password: bool = False
    ssh_pwauth: bool = False
    disable_root: bool = True

    # --- ssh ---
    ssh_keys: List[str] = field(default_factory=list)

    # --- network ---
    net_mode: str = "dhcp"             # "dhcp" | "static"
    net_interface: str = "eth0"
    net_address: str = ""
    net_netmask: str = "255.255.255.0"
    net_gateway: str = ""
    net_dns: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    net_search: List[str] = field(default_factory=list)
    # Platform-specific: let platform handle network (avoid conflicts)
    let_platform_handle_network: bool = False

    # --- packages ---
    package_upgrade: bool = True
    package_reboot_if_required: bool = False
    packages: List[str] = field(default_factory=list)

    # --- locale / timezone ---
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    keyboard_layout: str = "us"

    # --- disk ---
    grow_device: str = "/dev/sda"
    grow_partition: str = "1"

    # --- ntp ---
    ntp_servers: List[str] = field(default_factory=lambda: ["pool.ntp.org"])
    ntp_pools: List[str] = field(default_factory=list)
    # Platform-specific: let platform handle NTP
    let_platform_handle_ntp: bool = False

    # --- files / commands ---
    write_files: List[dict] = field(default_factory=list)   # {"path","content","permissions"}
    bootcmd: List[str] = field(default_factory=list)
    firstboot: List[str] = field(default_factory=list)     # runcmd
    final_message: str = "CloudSeed: system ready."

    # --- windows sysprep ---
    sysprep: bool = True
    sysprep_organization: str = "MyOrg"
    sysprep_owner: str = "Administrator"
    sysprep_computer_prefix: str = "WIN"
    sysprep_timezone: str = "W. Europe Standard Time"
    sysprep_locale: str = "en-US"
    sysprep_product_key: str = ""
    sysprep_unattended: bool = True   # Fully unattended like vSphere Guest Customization

    # --- vSphere Customization Spec export ---
    export_vsphere_spec: bool = False
    vsphere_spec_name: str = "CloudSeed-Spec"

    # --- vSphere Pre/Post Customization Scripts ---
    vsphere_pre_script: str = ""
    vsphere_post_script: str = ""
    use_sample_scripts: bool = False

    def has(self, mod: str) -> bool:
        return mod in self.modules

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> TemplateConfig:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


# --- interactive prompt helpers -------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    check_shutdown()
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    val = input(prompt).strip()
    check_shutdown()
    return val or default


def _ask_bool(prompt: str, default: bool = False) -> bool:
    check_shutdown()
    d = "Y/n" if default else "y/N"
    val = input(f"{prompt} ({d}): ").strip().lower()
    check_shutdown()
    if not val:
        return default
    return val in ("y", "yes", "true", "1")


def _ask_list(prompt: str) -> List[str]:
    check_shutdown()
    print(f"{prompt} (one per line, blank line to finish):")
    items: List[str] = []
    while True:
        check_shutdown()
        line = input(f"  {len(items) + 1}> ").strip()
        if not line:
            break
        items.append(line)
    return items


def _ask_overwrite(filepath: str) -> str:
    """Ask user what to do when file exists. Returns 'overwrite', 'suffix', 'skip', or 'overwrite_all'."""
    check_shutdown()
    while True:
        print(f"\n[CloudSeed] File already exists: {filepath}")
        print("  1) Overwrite")
        print("  2) Add suffix (e.g., _1, _2)")
        print("  3) Skip this file")
        print("  4) Overwrite ALL remaining files")
        choice = input("Select [1]: ").strip() or "1"
        check_shutdown()
        if choice == "1":
            return "overwrite"
        elif choice == "2":
            return "suffix"
        elif choice == "3":
            return "skip"
        elif choice == "4":
            return "overwrite_all"
        print("Invalid selection, try again.")


# Module-level state for overwrite-all
_overwrite_all_action = None


def _get_unique_path(out_dir: str, filename: str) -> str | None:
    """Get a unique path, asking user if file exists. Returns None if skip."""
    global _overwrite_all_action
    from pathlib import Path
    filepath = Path(out_dir) / filename
    if not filepath.exists():
        return str(filepath)

    # Check if overwrite-all is active
    if _overwrite_all_action == "overwrite":
        return str(filepath)
    elif _overwrite_all_action == "skip":
        return None

    action = _ask_overwrite(str(filepath))
    if action == "overwrite":
        return str(filepath)
    elif action == "suffix":
        base = filepath.stem
        ext = filepath.suffix
        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            new_path = filepath.parent / new_name
            if not new_path.exists():
                return str(new_path)
            counter += 1
    elif action == "skip":
        return None
    elif action == "overwrite_all":
        _overwrite_all_action = "overwrite"
        return str(filepath)



def _is_valid_ip(ip: str) -> bool:
    """Return True if ip is a valid IPv4 address."""
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255:
            return False
    return True


def _is_valid_netmask(mask: str) -> bool:
    """Return True if mask is a valid IPv4 netmask (contiguous 1s then 0s)."""
    if not _is_valid_ip(mask):
        return False
    parts = mask.split('.')
    binary = ''.join(f'{int(p):08b}' for p in parts)
    # No zero after one has been seen (i.e., no '01' pattern)
    return '01' not in binary


def _ask_ip(prompt: str, default: str = "") -> str:
    """Ask for an IPv4 address, validating input. Returns empty string if user enters empty (to keep default)."""
    while True:
        check_shutdown()
        if default:
            prompt_text = f"{prompt} [{default}]: "
        else:
            prompt_text = f"{prompt}: "
        val = input(prompt_text).strip()
        if not val:
            # User entered empty -> keep default (could be empty)
            return default
        if _is_valid_ip(val):
            return val
        print_error("Invalid IP address. Example: 192.168.1.100")


def _ask_netmask(prompt: str, default: str = "") -> str:
    """Ask for an IPv4 netmask, validating input. Returns empty string if user enters empty."""
    while True:
        check_shutdown()
        if default:
            prompt_text = f"{prompt} [{default}]: "
        else:
            prompt_text = f"{prompt}: "
        val = input(prompt_text).strip()
        if not val:
            return default
        if _is_valid_netmask(val):
            return val
        print_error("Invalid netmask. Example: 255.255.255.0")


def _ask_gateway(prompt: str, default: str = "") -> str:
    """Ask for a gateway IP, validating input. Returns empty string if user enters empty."""
    while True:
        check_shutdown()
        if default:
            prompt_text = f"{prompt} [{default}]: "
        else:
            prompt_text = f"{prompt}: "
        val = input(prompt_text).strip()
        if not val:
            return default
        if _is_valid_ip(val):
            return val
        print_error("Invalid gateway IP. Example: 192.168.1.1")


def _ask_dns(prompt: str, default: str = "") -> str:
    """Ask for a DNS server IP, validating input. Returns empty string if user enters empty."""
    while True:
        check_shutdown()
        if default:
            prompt_text = f"{prompt} [{default}]: "
        else:
            prompt_text = f"{prompt}: "
        val = input(prompt_text).strip()
        if not val:
            return default
        if _is_valid_ip(val):
            return val
        print_error("Invalid DNS IP. Example: 8.8.8.8")



# Common timezones for Linux (IANA tz database)
LINUX_TIMEZONES = [
    "UTC",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Paris",
    "Europe/Moscow",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Toronto",
    "America/Vancouver",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Singapore",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Australia/Perth",
    "Pacific/Auckland",
]

# Common timezones for Windows (Windows time zone IDs)
WINDOWS_TIMEZONES = [
    "UTC",
    "GMT Standard Time",
    "W. Europe Standard Time",
    "Central Europe Standard Time",
    "Romance Standard Time",
    "Russian Standard Time",
    "Eastern Standard Time",
    "Central Standard Time",
    "Mountain Standard Time",
    "Pacific Standard Time",
    "Eastern Standard Time (Mexico)",
    "Canada Central Standard Time",
    "Pacific Standard Time (Mexico)",
    "Tokyo Standard Time",
    "China Standard Time",
    "Singapore Standard Time",
    "Arabian Standard Time",
    "India Standard Time",
    "AUS Eastern Standard Time",
    "AUS Central Standard Time",
    "W. Australia Standard Time",
    "New Zealand Standard Time",
]

# Common locales (Linux)
LINUX_LOCALES = [
    "en_US.UTF-8",
    "en_GB.UTF-8",
    "de_DE.UTF-8",
    "fr_FR.UTF-8",
    "es_ES.UTF-8",
    "it_IT.UTF-8",
    "pt_PT.UTF-8",
    "ru_RU.UTF-8",
    "zh_CN.UTF-8",
    "ja_JP.UTF-8",
    "ko_KR.UTF-8",
    "ar_SA.UTF-8",
    "hi_IN.UTF-8",
    "pt_BR.UTF-8",
    "nl_NL.UTF-8",
    "pl_PL.UTF-8",
    "tr_TR.UTF-8",
    "sv_SE.UTF-8",
    "da_DK.UTF-8",
    "fi_FI.UTF-8",
    "nb_NO.UTF-8",
    "cs_CZ.UTF-8",
    "hu_HU.UTF-8",
    "ro_RO.UTF-8",
    "el_GR.UTF-8",
    "he_IL.UTF-8",
    "th_TH.UTF-8",
    "vi_VN.UTF-8",
    "id_ID.UTF-8",
    "ms_MY.UTF-8",
]

# Common keyboard layouts (Linux)
KEYBOARD_LAYOUTS = [
    "us",
    "uk",
    "de",
    "fr",
    "es",
    "it",
    "pt",
    "ru",
    "cn",
    "jp",
    "kr",
    "ar",
    "in",
    "br",
    "nl",
    "pl",
    "tr",
    "se",
    "dk",
    "fi",
    "no",
    "cz",
    "hu",
    "ro",
    "gr",
    "il",
    "th",
    "vn",
    "id",
    "my",
]

# Common grow devices (Linux)
GROW_DEVICES = [
    "/dev/sda",
    "/dev/vda",
    "/dev/nvme0n1",
    "/dev/xvda",
    "/dev/sdb",
    "/dev/vdb",
    "/dev/nvme1n1",
]

# Common Windows locales (Sysprep)
WINDOWS_LOCALES = [
    "en-US",
    "en-GB",
    "de-DE",
    "fr-FR",
    "es-ES",
    "it-IT",
    "pt-PT",
    "ru-RU",
    "zh-CN",
    "ja-JP",
    "ko-KR",
    "ar-SA",
    "hi-IN",
    "pt-BR",
    "nl-NL",
    "pl-PL",
    "tr-TR",
    "sv-SE",
    "da-DK",
    "fi-FI",
    "nb-NO",
    "cs-CZ",
    "hu-HU",
    "ro-RO",
    "el-GR",
    "he-IL",
    "th-TH",
    "vi-VN",
    "id-ID",
    "ms-MY",
]


def _ask_from_list(prompt: str, default: str, options: list, allow_custom: bool = True) -> str:
    """Selector with compact list, filtering, paging, and custom values."""
    filter_text = ""
    page = 0
    page_size = 12

    def visible() -> list:
        if filter_text:
            f = filter_text.lower()
            return [opt for opt in options if f in opt.lower()]
        return list(options)

    while True:
        check_shutdown()
        matches = visible()
        max_page = max(0, (len(matches) - 1) // page_size)
        page = min(page, max_page)
        shown = matches[page * page_size:(page + 1) * page_size]
        lines = []
        for i, opt in enumerate(shown, 1):
            absolute = page * page_size + i
            marker = "✓" if opt == default else " "
            lines.append(f"{marker} {absolute:>2}) {opt}")
        if not shown:
            lines.append("  No matches")
        if len(matches) > page_size:
            lines.append(f"  ... {len(matches) - len(shown)} total matches, page {page + 1}/{max_page + 1}")

        footer_parts = [f"Enter={default or 'default'}"]
        if allow_custom:
            footer_parts.append("0=custom")
        footer_parts.extend(["/=filter", "n/p=page", "b=back"])
        desc = f"Filter: {filter_text or '-'}  Matches: {len(matches)}"
        print_frame(prompt, desc, lines, "  ".join(footer_parts))

        raw = input(f"  {colorize('Select', Colors.BOLD)}: ").strip()
        if not raw:
            return default
        low = raw.lower()
        if low in ("b", "back", "esc"):
            return default
        if low == "n":
            page = min(max_page, page + 1)
            continue
        if low == "p":
            page = max(0, page - 1)
            continue
        if low.startswith("/"):
            filter_text = low[1:]
            page = 0
            continue
        if allow_custom and raw == "0":
            custom = input(f"  {colorize('Custom value', Colors.BOLD)}: ").strip()
            if custom:
                return custom
            continue
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(matches):
                return matches[idx - 1]
        # Treat any non-command text as filter input.
        filter_text = raw
        page = 0


def _ask_timezone(prompt: str, default: str = "", os_type: str = "linux") -> str:
    """Ask for a timezone, showing a selectable list."""
    zones = LINUX_TIMEZONES if os_type == "linux" else WINDOWS_TIMEZONES
    return _ask_from_list(prompt, default, zones)


def _ask_locale(prompt: str, default: str = "") -> str:
    return _ask_from_list(prompt, default, LINUX_LOCALES)


def _ask_keyboard_layout(prompt: str, default: str = "") -> str:
    return _ask_from_list(prompt, default, KEYBOARD_LAYOUTS)


def _ask_grow_device(prompt: str, default: str = "") -> str:
    return _ask_from_list(prompt, default, GROW_DEVICES)


def _ask_partition_number(prompt: str, default: str = "") -> str:
    options = ["1", "2", "3", "4", "5"]
    return _ask_from_list(prompt, default, options)


def _ask_windows_locale(prompt: str, default: str = "") -> str:
    return _ask_from_list(prompt, default, WINDOWS_LOCALES)


def _choose(prompt: str, options: List[str], allow_back: bool = False) -> str:
    """Choose from options. Returns selected option or 'BACK' if back selected."""
    check_shutdown()
    print_section(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {colorize(str(i), Colors.CYAN)}) {opt}")
    if allow_back:
        print(f"  {colorize('0', Colors.GRAY)}) ← Back")
    while True:
        check_shutdown()
        if allow_back:
            raw = input(f"  {colorize('Select', Colors.BOLD)} [1]: ").strip()
        else:
            raw = input(f"  {colorize('Select', Colors.BOLD)} [1]: ").strip()
        if not raw:
            return options[0]
        if allow_back and raw == "0":
            return "BACK"
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print_error("Invalid selection, try again.")


def _choose_module_multi(prompt: str, available: List[tuple], defaults: List[str], platform: str = "", os_type: str = "") -> List[str]:
    """Multi-select for modules with ability to configure after selection.
    Returns list of selected module IDs, or 'BACK' to go back.
    """
    check_shutdown()
    module_ids = [mid for (mid, lbl) in available]
    module_labels = [lbl for (mid, lbl) in available]
    selected = set(defaults)

    # Conflict pairs
    conflicts = {
        "platform_hostname": "hostname",
        "platform_network": "network",
        "platform_ntp": "ntp",
        "hostname": "platform_hostname",
        "network": "platform_network",
        "ntp": "platform_ntp",
    }

    while True:
        check_shutdown()
        # Build framed module list
        lines = []
        for i, (mid, lbl) in enumerate(available, 1):
            is_selected = mid in selected
            has_conflict = conflicts.get(mid) in selected
            if is_selected:
                prefix = "☑ "
                if has_conflict:
                    lbl = f"{lbl}  {colorize('(conflict!)', Colors.RED)}"
            else:
                prefix = "☐ "
                if has_conflict:
                    lbl = f"{lbl}  {colorize('(conflict!)', Colors.YELLOW)}"
            lines.append(f"{prefix}{lbl}")

        footer = "[Space] Toggle  [c] Configure selected  [a] All  [n] None  [Enter] Confirm  [Esc] Back"
        print_frame("MODULE SELECTION", f"Platform: {platform}  OS: {os_type}  [{len(selected)}/{len(available)} modules selected]", lines, footer)

        ch = _getch()
        if not ch:
            continue
        ch = ch.lower()
        if ch in ("0", "\x1b"):  # 0 or ESC
            return "BACK"
        if ch == "a":
            selected = set(module_ids)
            continue
        if ch == "n":
            selected = set()
            continue
        if ch == "c":
            if not selected:
                print_warn("No modules selected. Select at least one module.")
                continue
            return list(selected)
        if ch in (" ", "\r", "\n"):  # Space or Enter
            # If Space, toggle first item? Actually Enter confirms, Space toggles.
            # We'll handle number keys below for toggling specific items
            if ch in ("\r", "\n"):  # Enter - confirm
                if not selected:
                    print_warn("No modules selected. Select at least one module.")
                    continue
                return list(selected)
            # Space - just redraw, let number keys handle toggling
            continue
        if ch.isdigit():
            idx = int(ch)
            if 1 <= idx <= len(module_ids):
                mid = module_ids[idx - 1]
                if mid in selected:
                    selected.remove(mid)
                else:
                    selected.add(mid)
                    # Handle platform module priority: auto-disable cloud-init equivalent
                    if mid == "platform_hostname" and "hostname" in selected:
                        selected.remove("hostname")
                        print_info("Platform Hostname selected -> Hostname module auto-disabled (platform has priority)")
                    elif mid == "platform_network" and "network" in selected:
                        selected.remove("network")
                        print_info("Platform Network selected -> Network module auto-disabled (platform has priority)")
                    elif mid == "platform_ntp" and "ntp" in selected:
                        selected.remove("ntp")
                        print_info("Platform NTP selected -> NTP module auto-disabled (platform has priority)")
                    elif mid == "hostname" and "platform_hostname" in selected:
                        selected.remove("platform_hostname")
                        print_info("Hostname selected -> Platform Hostname auto-disabled")
                    elif mid == "network" and "platform_network" in selected:
                        selected.remove("platform_network")
                        print_info("Network selected -> Platform Network auto-disabled")
                    elif mid == "ntp" and "platform_ntp" in selected:
                        selected.remove("platform_ntp")
                        print_info("NTP selected -> Platform NTP auto-disabled")
            continue
        # ignore other keys


def collect_interactive() -> TemplateConfig:
    from .modules import MODULES

    setup_signal_handlers()

    # Detect cloud-init availability
    from .cli import detect_cloud_init_version
    cloud_init_version = detect_cloud_init_version()
    cloud_init_available = cloud_init_version != "not found"

    cfg = TemplateConfig()

    while True:  # Main loop - allows returning to main menu
        print_banner("Main Menu", cfg.platform, cfg.os_type, len(cfg.modules))

        # Main action menu
        main_actions = [
            "Generate Configuration",
            "Toolbox (External Tools)",
            "Config Validator",
            "Cloud-Init Doctor",
            "Template Maker (Prepare Current Machine as Template)",
            "Guide Help (Configuration Reference)",
            "Exit",
        ]
        action = _choose("Select action:", main_actions)

        if action == "Toolbox (External Tools)":
            from .toolbox import toolbox_menu
            toolbox_menu()
            continue  # Return to main menu
        elif action == "Config Validator":
            from .validator import validator_menu
            validator_menu()
            continue
        elif action == "Cloud-Init Doctor":
            from .doctor import doctor_menu
            doctor_menu()
            continue
        elif action == "Template Maker (Prepare Current Machine as Template)":
            from .templatemaker import template_maker_menu
            template_maker_menu()
            continue
        elif action == "Guide Help (Configuration Reference)":
            from .model import show_guide_help
            show_guide_help()
            continue
        elif action == "Exit":
            print("Goodbye!")
            sys.exit(0)

        # Generate Configuration flow with back navigation
        while True:
            print_section("Platform Selection", "Choose your target virtualization platform")
            platform_choice = _choose("Target platform:", ["vSphere (VMware)", "KVM (libvirt)", "Physical / Other"], allow_back=True)
            if platform_choice == "BACK":
                break  # Back to main menu
            cfg.platform = platform_choice.split()[0].lower()
            if cfg.platform == "physical / other":
                cfg.platform = "physical"

            print_section("OS Selection", "Choose the guest operating system")
            os_choice = _choose("Guest OS:", ["Linux", "Windows"], allow_back=True)
            if os_choice == "BACK":
                continue  # Back to platform selection
            cfg.os_type = os_choice.split()[0].lower()

            # Module selection with back
            available = [(mid, lbl) for (mid, lbl, oses) in MODULES if cfg.os_type in oses and (mid not in ("vsphere_spec", "vsphere_scripts") or cfg.platform == "vsphere")]

            # Warn if cloud-init not available but Linux selected
            if cfg.os_type == "linux" and not cloud_init_available:
                print(f"\n{colorize('WARNING', Colors.YELLOW)}: cloud-init not found on this system!")
                print("  Generated configs require cloud-init on the TARGET VM, not this build machine.")
                print("  This is OK if you're building configs for another VM.")
                print("  Some features (Config Validator, Cloud-Init Doctor) need cloud-init locally.")
                print()

            # Default platform modules ON, cloud-init equivalents OFF when platform module selected
            module_ids = [mid for (mid, lbl) in available]
            defaults = []
            for mid in module_ids:
                if mid in ("platform_hostname", "platform_network", "platform_ntp"):
                    defaults.append(mid)  # Platform modules default ON
                elif mid in ("hostname", "network", "ntp"):
                    # Cloud-init equivalents default OFF (platform modules have priority)
                    pass
                else:
                    defaults.append(mid)  # Other modules default ON

            while True:
                selected_modules = _choose_module_multi("Module Selection", available, defaults, cfg.platform, cfg.os_type)
                if selected_modules == "BACK":
                    break  # Back to OS selection

                cfg.modules = selected_modules

                # Now configure each module one by one
                if _configure_modules(cfg, available):
                    return cfg  # Success - exit the function
                else:
                    # User chose to go back from module configuration
                    continue

        # If we get here, user went back to main menu
        continue


def _configure_modules(cfg: TemplateConfig, available: List[tuple]) -> bool:
    """Configure all selected modules. Returns True if complete, False if user wants to go back."""

    # Hostname settings - only configure cloud-init hostname if platform not handling it
    if cfg.has("platform_hostname"):
        # Platform handles hostname - skip cloud-init hostname config
        pass
    elif cfg.has("hostname"):
        if not _configure_hostname(cfg):
            return False

    if cfg.has("users"):
        if not _configure_users(cfg):
            return False

    if cfg.has("ssh"):
        if not _configure_ssh(cfg):
            return False

    if cfg.has("root"):
        if not _configure_root(cfg):
            return False

    # Network - only configure cloud-init network if platform not handling it
    if cfg.has("platform_network"):
        pass
    elif cfg.has("network"):
        if not _configure_network(cfg):
            return False

    if cfg.has("packages"):
        if not _configure_packages(cfg):
            return False

    if cfg.has("locale"):
        if not _configure_locale(cfg):
            return False

    if cfg.has("disk"):
        if not _configure_disk(cfg):
            return False

    # NTP - only configure cloud-init NTP if platform not handling it
    if cfg.has("platform_ntp"):
        pass
    elif cfg.has("ntp"):
        if not _configure_ntp(cfg):
            return False

    if cfg.has("files"):
        if not _configure_files(cfg):
            return False

    if cfg.has("bootcmd"):
        if not _configure_bootcmd(cfg):
            return False

    if cfg.has("firstboot"):
        if not _configure_firstboot(cfg):
            return False

    if cfg.has("final"):
        if not _configure_final(cfg):
            return False

    if cfg.has("sysprep"):
        if not _configure_sysprep(cfg):
            return False

    # vSphere Customization Spec
    if cfg.has("vsphere_spec") and cfg.platform == "vsphere":
        if not _configure_vsphere_spec(cfg):
            return False

    # vSphere Pre/Post Customization Scripts
    if cfg.has("vsphere_scripts") and cfg.platform == "vsphere":
        if not _configure_vsphere_scripts(cfg):
            return False

    return True


def _configure_hostname(cfg: TemplateConfig) -> bool:
    print_section("Hostname Configuration", "Configure how the VM hostname is set")
    # If platform_hostname module is selected, platform handles it - skip this config
    if cfg.has("platform_hostname"):
        print_info("Platform module 'platform_hostname' selected -> platform will set hostname")
        return True
    cfg.use_platform_hostname = _ask_bool("Let platform (vSphere/KVM) set hostname", cfg.use_platform_hostname)
    if not cfg.use_platform_hostname:
        cfg.hostname_prefix = _ask("Hostname prefix", cfg.hostname_prefix)
        cfg.hostname = _ask("Hostname (blank = auto-generate from prefix)", cfg.hostname)
    return True


def _configure_users(cfg: TemplateConfig) -> bool:
    print_section("User Configuration", "Create admin user with password and sudo/Administrators access")
    cfg.username = _ask("Username", cfg.username)
    cfg.password = _ask("Password (plaintext; document risk!)", cfg.password)
    cfg.sudo = _ask_bool("Grant sudo (Linux) / Administrators (Windows)", cfg.sudo)
    cfg.lock_password = _ask_bool("Lock password (key-only login)", cfg.lock_password)
    cfg.ssh_pwauth = _ask_bool("Allow SSH password auth", cfg.ssh_pwauth)
    return True


def _configure_ssh(cfg: TemplateConfig) -> bool:
    print_section("SSH Configuration", "Add SSH authorized keys (one per line)")
    cfg.ssh_keys = _ask_list("SSH public keys (ssh-rsa / ssh-ed25519 ...)")
    return True


def _configure_root(cfg: TemplateConfig) -> bool:
    print_section("Root Hardening", "Disable root SSH login")
    cfg.disable_root = _ask_bool("Disable root SSH login", cfg.disable_root)
    return True


def _configure_network(cfg: TemplateConfig) -> bool:
    print_section("Network Configuration", "Configure network - DHCP or static IP with DNS")
    # If platform_network module is selected, platform handles it - skip this config
    if cfg.has("platform_network"):
        print_info("Platform module 'platform_network' selected -> platform will configure network")
        return True
    cfg.let_platform_handle_network = _ask_bool("Let platform handle network (avoid conflicts with cloud-init)", cfg.let_platform_handle_network)
    if not cfg.let_platform_handle_network:
        cfg.net_mode = _choose("Network mode:", ["dhcp", "static"], allow_back=False).split()[0]
        if cfg.net_mode == "static":
            cfg.net_interface = _ask("Interface name", cfg.net_interface)
            cfg.net_address = _ask_ip("IP address", cfg.net_address)
            cfg.net_netmask = _ask_netmask("Netmask", cfg.net_netmask)
            cfg.net_gateway = _ask_gateway("Gateway", cfg.net_gateway)
            cfg.net_dns = _ask_list("DNS servers")
            cfg.net_search = _ask_list("DNS search domains (blank=none)")
    return True


def _configure_packages(cfg: TemplateConfig) -> bool:
    print_section("Package Configuration", "Install packages and optionally upgrade on first boot")
    cfg.package_upgrade = _ask_bool("Upgrade packages on first boot", cfg.package_upgrade)
    cfg.packages = _ask_list("Packages to install (blank=none)")
    return True


def _configure_locale(cfg: TemplateConfig) -> bool:
    print_section("Locale & Timezone", "Set timezone, locale, and keyboard layout")
    cfg.timezone = _ask_timezone("Timezone", cfg.timezone, os_type="linux")
    cfg.locale = _ask_locale("Locale", cfg.locale)
    cfg.keyboard_layout = _ask_keyboard_layout("Keyboard layout", cfg.keyboard_layout)
    return True


def _configure_disk(cfg: TemplateConfig) -> bool:
    print_section("Disk Configuration", "Grow root filesystem on first boot")
    cfg.grow_device = _ask_grow_device("Grow device", cfg.grow_device)
    cfg.grow_partition = _ask_partition_number("Partition number", cfg.grow_partition)
    return True


def _configure_ntp(cfg: TemplateConfig) -> bool:
    print_section("NTP Configuration", "Configure NTP time synchronization")
    # If platform_ntp module is selected, platform handles it - skip this config
    if cfg.has("platform_ntp"):
        print_info("Platform module 'platform_ntp' selected -> platform will configure NTP")
        return True
    cfg.let_platform_handle_ntp = _ask_bool("Let platform handle NTP", cfg.let_platform_handle_ntp)
    if not cfg.let_platform_handle_ntp:
        cfg.ntp_servers = _ask_list("NTP servers")
        if not cfg.ntp_servers:
            cfg.ntp_servers = ["pool.ntp.org"]
    return True


def _configure_files(cfg: TemplateConfig) -> bool:
    print_section("Write Files", "Write arbitrary files to the target system (blank path to finish)")
    while True:
        check_shutdown()
        p = input("  file path (blank to stop): ").strip()
        if not p:
            break
        c = input("  file content: ").strip()
        perm = input("  permissions [0644]: ").strip() or "0644"
        cfg.write_files.append({"path": p, "content": c, "permissions": perm})
    return True


def _configure_bootcmd(cfg: TemplateConfig) -> bool:
    print_section("Early Boot Commands", "Commands that run early in boot (bootcmd)")
    cfg.bootcmd = _ask_list("bootcmd (early boot commands)")
    return True


def _configure_firstboot(cfg: TemplateConfig) -> bool:
    print_section("First-Boot Commands", "Commands that run on first boot (runcmd)")
    cfg.firstboot = _ask_list("First-boot commands (runcmd)")
    return True


def _configure_final(cfg: TemplateConfig) -> bool:
    print_section("Final Message", "Message displayed when cloud-init completes")
    cfg.final_message = _ask("Final message", cfg.final_message)
    return True


def _configure_sysprep(cfg: TemplateConfig) -> bool:
    print_section("Windows Sysprep", "Generalize Windows for cloning (creates new SID)")
    cfg.sysprep = _ask_bool("Run Sysprep generalize (new SID)", cfg.sysprep)
    if cfg.sysprep:
        cfg.sysprep_unattended = _ask_bool("Fully unattended (like vSphere Guest Customization)", cfg.sysprep_unattended)
        cfg.sysprep_organization = _ask("Organization", cfg.sysprep_organization)
        cfg.sysprep_owner = _ask("Owner", cfg.sysprep_owner)
        cfg.sysprep_computer_prefix = _ask("Computer-name prefix", cfg.sysprep_computer_prefix)
        cfg.sysprep_timezone = _ask_timezone("Timezone", cfg.sysprep_timezone, os_type="windows")
        cfg.sysprep_locale = _ask_windows_locale("Locale (UI)", cfg.sysprep_locale)
        cfg.sysprep_product_key = input("Product key (blank=skip): ").strip()
        check_shutdown()
    return True


def _configure_vsphere_spec(cfg: TemplateConfig) -> bool:
    print_section("vSphere Customization Spec Export", "Export vSphere Guest Customization Specification (XML)")
    cfg.export_vsphere_spec = _ask_bool("Export vSphere Customization Spec (XML)", cfg.export_vsphere_spec)
    if cfg.export_vsphere_spec:
        cfg.vsphere_spec_name = _ask("Spec name", cfg.vsphere_spec_name)
    return True


def _configure_vsphere_scripts(cfg: TemplateConfig) -> bool:
    print_section("vSphere Pre/Post Customization Scripts", "Scripts that run before/after cloud-init during vSphere Guest Customization")
    cfg.use_sample_scripts = _ask_bool("Use sample scripts (customizable)", cfg.use_sample_scripts)
    if cfg.use_sample_scripts:
        # Ask if user wants to customize the sample scripts or use them as-is
        customize = _ask_bool("Customize sample scripts? (No = use samples as-is)", False)
        if customize:
            print("\nSample Pre-customization script (runs before cloud-init):")
            print("# Example: Register with Satellite, install agents, etc.")
            cfg.vsphere_pre_script = _ask("Pre-customization script (blank to skip)", "")
            print("\nSample Post-customization script (runs after cloud-init):")
            print("# Example: Join domain, run compliance checks, etc.")
            cfg.vsphere_post_script = _ask("Post-customization script (blank to skip)", "")
        else:
            # Use samples as-is, no custom input
            cfg.vsphere_pre_script = ""
            cfg.vsphere_post_script = ""
    return True


def show_guide_help() -> None:
    """Show configuration reference guide with all modules, sub-items, defaults, and platform applicability."""
    print_section("Guide Help: Configuration Reference", "All CloudSeed modules, sub-items, defaults, and platform/OS applicability")
    print()

    print_info("Platform Modules (priority: platform > cloud-init)")
    print(f"  {colorize('platform_hostname', Colors.CYAN):<25} Let Platform Set Hostname (vSphere/KVM)")
    print("    Default: ON  |  OS: Linux, Windows  |  Platforms: vSphere, KVM")
    print("    When ON: hostname/hostname_prefix ignored, platform assigns hostname")
    print()
    print(f"  {colorize('platform_network', Colors.CYAN):<25} Let Platform Handle Network")
    print("    Default: ON  |  OS: Linux, Windows  |  Platforms: vSphere, KVM")
    print("    When ON: network/net_mode/net_* ignored, platform configures network")
    print()
    print(f"  {colorize('platform_ntp', Colors.CYAN):<25} Let Platform Handle NTP")
    print("    Default: ON  |  OS: Linux, Windows  |  Platforms: vSphere, KVM")
    print("    When ON: ntp/ntp_servers ignored, platform configures NTP")
    print()

    print_info("Core Modules (Linux)")
    print(f"  {colorize('hostname', Colors.CYAN):<25} Set Hostname")
    print("    Sub-items: hostname_prefix (default: 'vm'), hostname (default: auto)")
    print("    OS: Linux, Windows  |  Ignored if platform_hostname=ON")
    print()
    print(f"  {colorize('users', Colors.CYAN):<25} Create Admin User")
    print("    Sub-items: username (default: 'admin'), password (default: 'ChangeMe!123'), sudo (default: true), lock_password (default: false), ssh_pwauth (default: false)")
    print("    OS: Linux, Windows  |  Password hashed by default ($6$ SHA-512)")
    print()
    print(f"  {colorize('ssh', Colors.CYAN):<25} SSH Authorized Keys")
    print("    Sub-items: ssh_keys (list of ssh-rsa/ssh-ed25519 keys)")
    print("    OS: Linux, Windows")
    print()
    print(f"  {colorize('root', Colors.CYAN):<25} Harden Root")
    print("    Sub-items: disable_root (default: true)")
    print("    OS: Linux only")
    print()
    print(f"  {colorize('network', Colors.CYAN):<25} Network Configuration")
    print("    Sub-items: net_mode (default: 'dhcp' | 'static'), net_interface (default: 'eth0'), net_address, net_netmask, net_gateway, net_dns (default: ['8.8.8.8','1.1.1.1']), net_search")
    print("    OS: Linux, Windows  |  Ignored if platform_network=ON")
    print()
    print(f"  {colorize('packages', Colors.CYAN):<25} Install Packages")
    print("    Sub-items: package_upgrade (default: true), packages (list)")
    print("    OS: Linux only")
    print()
    print(f"  {colorize('locale', Colors.CYAN):<25} Locale & Timezone")
    print("    Sub-items: timezone (default: 'UTC'), locale (default: 'en_US.UTF-8'), keyboard_layout (default: 'us')")
    print("    OS: Linux only")
    print()
    print(f"  {colorize('disk', Colors.CYAN):<25} Grow Root Filesystem")
    print("    Sub-items: grow_device (default: '/dev/sda'), grow_partition (default: '1')")
    print("    OS: Linux only")
    print()
    print(f"  {colorize('ntp', Colors.CYAN):<25} NTP Time Servers")
    print("    Sub-items: ntp_servers (default: ['pool.ntp.org'])")
    print("    OS: Linux, Windows  |  Ignored if platform_ntp=ON")
    print()
    print(f"  {colorize('files', Colors.CYAN):<25} Write Arbitrary Files")
    print("    Sub-items: path, content, permissions (default: '0644'), owner (default: 'root:root')")
    print("    OS: Linux, Windows")
    print()
    print(f"  {colorize('bootcmd', Colors.CYAN):<25} Early Boot Commands")
    print("    Sub-items: list of commands (run every boot, early)")
    print("    OS: Linux only")
    print()
    print(f"  {colorize('firstboot', Colors.CYAN):<25} First-Boot Commands")
    print("    Sub-items: list of commands (run once on first boot via runcmd)")
    print("    OS: Linux, Windows")
    print()
    print(f"  {colorize('final', Colors.CYAN):<25} Final Message")
    print("    Sub-items: final_message (default: 'CloudSeed: system ready.')")
    print("    OS: Linux only")
    print()

    print_info("Windows Modules")
    print(f"  {colorize('sysprep', Colors.CYAN):<25} Windows Sysprep Generalize")
    print("    Sub-items: sysprep (default: true), sysprep_unattended (default: true), sysprep_organization, sysprep_owner, sysprep_computer_prefix (default: 'WIN'), sysprep_timezone, sysprep_locale, sysprep_product_key")
    print("    OS: Windows only  |  Runs sysprep /generalize /oobe /shutdown /unattend:...")
    print()

    print_info("vSphere Modules (only on vSphere platform)")
    print(f"  {colorize('vsphere_spec', Colors.CYAN):<25} Export vSphere Customization Spec (XML)")
    print("    Sub-items: export_vsphere_spec (default: false), vsphere_spec_name (default: 'CloudSeed-Spec')")
    print("    OS: Linux, Windows  |  Platform: vSphere only")
    print()
    print(f"  {colorize('vsphere_scripts', Colors.CYAN):<25} vSphere Pre/Post Scripts")
    print("    Sub-items: use_sample_scripts (default: false), vsphere_pre_script, vsphere_post_script")
    print("    OS: Linux, Windows  |  Platform: vSphere only")
    print()

    print_info("Global Settings")
    print("  Platform: vsphere | kvm | physical")
    print("  OS Type: linux | windows")
    print("  Output Dir: ./cloudseed-out (in current working directory)")
    print("  Password Hashing: $6$ SHA-512 (default), --plaintext-password to disable")
    print("  Config File: cloudseed.json (written alongside output for re-use)")
    print()

    print_info("Priority Rules")
    print("  - platform_hostname ON -> hostname module ignored")
    print("  - platform_network ON -> network module ignored")
    print("  - platform_ntp ON -> ntp module ignored")
    print("  - vSphere modules only appear when platform = vSphere")
    print("  - Linux modules hidden on Windows, Windows modules hidden on Linux")
    print()

    input(f"  {colorize('Press Enter to return to Main Menu', Colors.BOLD)}")


def load_json(path: str) -> TemplateConfig:
    with open(path, encoding="utf-8") as fh:
        return TemplateConfig.from_dict(json.load(fh))
