#!/usr/bin/env bash
# nview installer: install, update or uninstall.
#
# Usage (from this folder):
#   bash install.sh                  -> opens a menu: Install / Update / Uninstall
#   bash install.sh --install        -> installs under ~/.local (no sudo needed)
#   bash install.sh --update         -> updates an existing install from this folder
#   bash install.sh --uninstall      -> removes nview (and asks about your settings)
#   bash install.sh --system         -> use /usr/local instead of ~/.local (asks for sudo)
#   bash install.sh --no-deps        -> does not try to install dependencies
#   bash install.sh --help
#
# Installed files:
#   <prefix>/share/nview/nview.py    the program itself
#   <prefix>/bin/nview               launcher
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP=nview
NVIEW_VERSION=0.6.0
NVIEW_NAME="Pocket GUI"
USER_PREFIX="$HOME/.local"
SYS_PREFIX=/usr/local
ACTION=""
SYSTEM=0
DEPS=1

usage() {
    sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
    case "$arg" in
        --install)   ACTION=install ;;
        --update)    ACTION=update ;;
        --uninstall) ACTION=uninstall ;;
        --system)    SYSTEM=1 ;;
        --no-deps)   DEPS=0 ;;
        -h|--help)   usage; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
    esac
done

# Colors: only on an interactive terminal (same purple as the app's splash screen)
if [[ -t 1 ]]; then
    C_HEAD=$'\033[1;38;5;141m'
    C_DIM=$'\033[38;5;244m'
    C_OK=$'\033[38;5;114m'
    C_WARN=$'\033[38;5;221m'
    C_SEL=$'\033[7;38;5;141m'
    C_RST=$'\033[0m'
else
    C_HEAD=""; C_DIM=""; C_OK=""; C_WARN=""; C_SEL=""; C_RST=""
fi

say()  { printf '%s>>%s %s\n' "$C_HEAD" "$C_RST" "$*"; }
ok()   { printf '%s ✓%s %s\n' "$C_OK" "$C_RST" "$*"; }
warn() { printf '%s!!%s %s\n' "$C_WARN" "$C_RST" "$*" >&2; }

banner() {
    printf '%s%s%s%s%s\n' "$C_HEAD" '██████    ██    ██  ██    ████    ██      ██  ' "$C_OK" '████' "$C_RST"
    printf '%s%s%s%s%s\n' "$C_HEAD" '██    ██  ██    ██      ██    ██  ██      ██  ' "$C_OK" '████' "$C_RST"
    printf '%s%s%s%s%s\n' "$C_HEAD" '██    ██  ██    ██  ██  ████████  ██  ██  ██  ' "$C_OK" '████' "$C_RST"
    printf '%s%s%s%s%s\n' "$C_HEAD" '██    ██  ██    ██  ██  ██        ██  ██  ██  ' "$C_OK" '████' "$C_RST"
    printf '%s%s%s%s%s\n' "$C_HEAD" '██    ██    ████    ██    ██████    ██  ██    ' "$C_OK" '████' "$C_RST"
    printf '%sA simple, fast and minimal text editor.%s\n' "$C_DIM" "$C_RST"
    printf '%s──────────────────────────────────────────────────%s\n' "$C_HEAD" "$C_RST"
    printf '%s  Installer  v%s "%s"%s\n\n' "$C_DIM" "$NVIEW_VERSION" "$NVIEW_NAME" "$C_RST"
}

# ---------------------------------------------------------------- uninstall



# ---------------------------------------------------------------- prefix helpers

# set_prefix <prefix>: points APP_DIR / BIN_DIR / BIN at a prefix and decides about sudo.
set_prefix() {
    PREFIX="$1"
    APP_DIR="$PREFIX/share/$APP"
    BIN_DIR="$PREFIX/bin"
    BIN="$BIN_DIR/$APP"
    SUDO=""
    if [[ "$PREFIX" == "$SYS_PREFIX" && $EUID -ne 0 ]]; then
        SUDO="sudo"
    fi
}

# installed_version <prefix>: prints the version line of an existing install (empty if none).
installed_version() {
    local f="$1/share/$APP/nview.py"
    [[ -f "$f" ]] || return 0
    python3 "$f" --version 2>/dev/null || echo "$APP (unknown version)"
}

# installed_prefixes: prints every prefix that has nview installed.
installed_prefixes() {
    local p
    for p in "$USER_PREFIX" "$SYS_PREFIX"; do
        [[ -f "$p/share/$APP/nview.py" ]] && echo "$p"
    done
    return 0
}

# ---------------------------------------------------------------- menu

menu() {
    local -a labels=("Install  (current user, ~/.local)"
                     "Install  (all users, /usr/local, sudo)"
                     "Update   (reinstall from this folder)"
                     "Uninstall"
                     "Quit")
    local -a actions=("install" "install-system" "update" "uninstall" "quit")
    local sel=0 n=${#labels[@]} i key rest

    echo "Installed:"
    local found=0 p v
    for p in "$USER_PREFIX" "$SYS_PREFIX"; do
        v="$(installed_version "$p")"
        if [[ -n "$v" ]]; then
            printf '  %s%s%s  %s\n' "$C_OK" "$v" "$C_RST" "($p)"
            found=1
        fi
    done
    [[ $found -eq 0 ]] && printf '  %snot installed%s\n' "$C_DIM" "$C_RST"
    echo
    printf '%sUse ↑ ↓ and Enter, or press 1-%d.%s\n\n' "$C_DIM" "$n" "$C_RST"

    draw() {
        for ((i = 0; i < n; i++)); do
            if [[ $i -eq $sel ]]; then
                printf '\r\033[K %s %d  %s %s\n' "$C_SEL" "$((i + 1))" "${labels[$i]}" "$C_RST"
            else
                printf '\r\033[K   %d  %s\n' "$((i + 1))" "${labels[$i]}"
            fi
        done
    }
    draw
    while true; do
        IFS= read -rsn1 key || { ACTION=quit; return; }
        case "$key" in
            $'\033')
                rest=""
                IFS= read -rsn2 -t 0.1 rest || true
                case "$rest" in
                    '[A') sel=$(( (sel + n - 1) % n )) ;;
                    '[B') sel=$(( (sel + 1) % n )) ;;
                    *) ;;
                esac ;;
            k) sel=$(( (sel + n - 1) % n )) ;;
            j) sel=$(( (sel + 1) % n )) ;;
            [1-9])
                if (( key >= 1 && key <= n )); then sel=$((key - 1)); key=""; fi ;;
            q|Q) sel=$((n - 1)); key="" ;;
        esac
        if [[ "$key" == "" ]]; then
            echo
            ACTION="${actions[$sel]}"
            return
        fi
        printf '\033[%dA' "$n"
        draw
    done
}

# ---------------------------------------------------------------- package manager

detect_pm() {
    if command -v dnf >/dev/null 2>&1; then echo dnf
    elif command -v apt-get >/dev/null 2>&1; then echo apt
    elif command -v pacman >/dev/null 2>&1; then echo pacman
    elif command -v zypper >/dev/null 2>&1; then echo zypper
    else echo none
    fi
}

install_packages() {
    local pm="$1"; shift
    case "$pm" in
        dnf)    sudo dnf install -y "$@" ;;
        apt)    sudo apt-get update -y && sudo apt-get install -y "$@" ;;
        pacman) sudo pacman -S --needed --noconfirm "$@" ;;
        zypper) sudo zypper -n install "$@" ;;
        *)      return 1 ;;
    esac
}

# ---------------------------------------------------------------- dependencies

check_deps() {
    # Python 3.8+ and the curses module are required. infocmp provides terminal definitions.
    command -v python3 >/dev/null 2>&1 || return 1
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || return 1
    python3 -c 'import curses' 2>/dev/null || return 1
    command -v infocmp >/dev/null 2>&1 || return 1
    return 0
}

ensure_deps() {
    if [[ $DEPS -eq 0 ]]; then
        say "--no-deps: dependency check skipped."
        return 0
    fi
    if check_deps; then
        say "Dependencies already installed (python3, curses, terminfo)."
        return 0
    fi
    local PM PKGS
    PM="$(detect_pm)"
    say "Installing missing dependencies (package manager: $PM)..."
    case "$PM" in
        dnf)    PKGS=(python3 python3-libs ncurses) ;;
        apt)    PKGS=(python3 libncurses6 ncurses-base ncurses-bin) ;;
        pacman) PKGS=(python ncurses) ;;
        zypper) PKGS=(python3 ncurses-utils) ;;
        *)      PKGS=() ;;
    esac
    if [[ ${#PKGS[@]} -eq 0 ]]; then
        warn "Unsupported package manager. Install Python 3.8+, curses and ncurses manually."
        exit 1
    fi
    if ! install_packages "$PM" "${PKGS[@]}"; then
        warn "Could not install dependencies. Install manually: ${PKGS[*]}"
        exit 1
    fi
    if ! check_deps; then
        warn "Dependency check still fails after installation."
        exit 1
    fi
    say "Dependencies installed."
}

# ---------------------------------------------------------------- actions

check_source() {
    if [[ ! -f "$SRC_DIR/nview.py" ]]; then
        warn "nview.py not found. Run install.sh from the same folder as nview.py."
        exit 1
    fi
}

copy_files() {
    say "Copying files: $APP_DIR"
    $SUDO mkdir -p "$APP_DIR" "$BIN_DIR"
    $SUDO install -m 0644 "$SRC_DIR/nview.py" "$APP_DIR/nview.py"

    local tmp
    tmp="$(mktemp)"
    cat > "$tmp" << LAUNCHER
#!/bin/sh
exec python3 "$APP_DIR/nview.py" "\$@"
LAUNCHER
    $SUDO install -m 0755 "$tmp" "$BIN"
    rm -f "$tmp"
    ok "Launcher created: $BIN"

    if ! python3 "$APP_DIR/nview.py" --version >/dev/null 2>&1; then
        warn "The installed program failed to run. Check the output of python3 --version."
        exit 1
    fi
}

path_and_clipboard_notes() {
    echo
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            warn "$BIN_DIR is not in PATH. Add this line to your ~/.bashrc:"
            echo "     export PATH=\"$BIN_DIR:\$PATH\""
            ;;
    esac
    if ! command -v wl-copy >/dev/null 2>&1 && ! command -v xclip >/dev/null 2>&1 && ! command -v xsel >/dev/null 2>&1; then
        echo "Note: optional, for copying to the system clipboard: sudo dnf install wl-clipboard  (Wayland)"
        echo "      or: sudo dnf install xclip  (X11)"
    fi
}

do_install() {
    check_source
    ensure_deps
    local before
    before="$(installed_version "$PREFIX")"
    [[ -n "$before" ]] && say "Already installed here: $before. Replacing it."
    copy_files
    path_and_clipboard_notes
    echo
    ok "nview installed: $("$BIN" --version)"
    print_usage
}

do_update() {
    check_source
    local ps p before after
    if [[ $SYSTEM -eq 1 ]]; then ps="$SYS_PREFIX"; else ps="$(installed_prefixes)"; fi
    if [[ -z "$ps" ]]; then
        warn "nview is not installed yet. Choose Install first (bash install.sh --install)."
        exit 1
    fi
    ensure_deps
    for p in $ps; do
        set_prefix "$p"
        before="$(installed_version "$PREFIX")"
        [[ -z "$before" ]] && before="(not installed)"
        say "Updating $PREFIX:  $before  ->  nview $NVIEW_VERSION ($NVIEW_NAME)"
        copy_files
        after="$("$BIN" --version)"
        ok "Updated: $after"
    done
    echo
    printf '%sYour settings in ~/.config/nview and your playground files were not touched.%s\n' "$C_DIM" "$C_RST"
}

do_uninstall() {
    local ps p answer
    if [[ $SYSTEM -eq 1 ]]; then ps="$SYS_PREFIX"; else ps="$(installed_prefixes)"; fi
    if [[ -z "$ps" ]]; then
        say "nview is not installed. Nothing to remove."
        return 0
    fi
    for p in $ps; do
        set_prefix "$p"
        say "Removing: $APP_DIR and $BIN"
        $SUDO rm -rf "$APP_DIR"
        $SUDO rm -f "$BIN"
    done
    local cfg="${XDG_CONFIG_HOME:-$HOME/.config}/nview"
    if [[ -d "$cfg" && -t 0 ]]; then
        printf 'Also delete your settings (%s)? [y/N] ' "$cfg"
        read -r answer || answer=""
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            rm -rf "$cfg"
            ok "Settings deleted."
        else
            say "Settings kept."
        fi
    fi
    echo
    say "Done, nview has been removed. Files in ~/nview-playground were kept."
}

print_usage() {
    echo
    printf '%sUsage%s\n' "$C_HEAD" "$C_RST"
    echo "  nview                   splash screen (Ctrl+O opens a file, + opens the Code + playground)"
    echo "  nview file.py           edit a file (i to insert, :w to save)"
    echo "  nview read file.py      print a file in color and exit"
    echo "  nview --theme dracula   pick a theme  (neon-mor, vscode, dracula, monokai, nord, ...)"
    echo "  nview --lang en         pick a language  (tr, en, de, es, fr)"
    echo "  Change settings from the splash screen (... key) or with :settings."
    echo
    echo "Update or remove later:  bash install.sh"
}

# ---------------------------------------------------------------- main

banner

if [[ -z "$ACTION" ]]; then
    if [[ -t 0 && -t 1 ]]; then
        menu
    else
        ACTION=install
    fi
fi

case "$ACTION" in
    install)         set_prefix "$([[ $SYSTEM -eq 1 ]] && echo "$SYS_PREFIX" || echo "$USER_PREFIX")"; do_install ;;
    install-system)  SYSTEM=1; set_prefix "$SYS_PREFIX"; do_install ;;
    update)          do_update ;;
    uninstall)       do_uninstall ;;
    quit)            echo "Bye." ;;
esac
