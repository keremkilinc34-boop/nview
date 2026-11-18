# nview
Minimal Neovim-style terminal text editor with installer and documentation.

# nview 0.6.0 "Pocket GUI"

A colorful, minimal, Neovim-style text editor and viewer.

## Install

    bash install.sh               # menu: Install / Update / Uninstall
    bash install.sh --install     # installs under ~/.local
    bash install.sh --update      # updates an existing install from this folder
    bash install.sh --uninstall   # removes nview (asks before deleting your settings)
    bash install.sh --system      # use /usr/local instead of ~/.local (sudo)

Run `bash install.sh` without options in a terminal to get the menu (arrow keys or 1-5). It shows
which versions are installed. **Update** reinstalls from the current folder and keeps your
settings and your playground files. **Uninstall** removes the program and asks whether to delete
`~/.config/nview`; `~/nview-playground` is never deleted.
Missing dependencies (Python 3.8+, curses, terminfo) are installed with dnf/apt/pacman/zypper.

## Usage

    nview                       splash screen
    nview open                  file browser (navigate folders)
    nview open file.py          open a file directly
    nview open dir/             start the file browser in that folder
    nview file.py               edit a file (opened as a new file if it does not exist)
    nview a.py b.md             several files (switch with gt / gT)
    nview read file.py          print a file in color to the terminal and exit
    nview read --plain x.txt    print without color or line numbers (for pipes)
    nview --theme okyanus       start with a theme
    nview --lang de             start with a language

## What's new in 0.6.0 "Pocket GUI"

- **Menu bar, command palette and mouse support** (see the GUI layer section).
- Version name is now `nview --version` -> `nview 0.6.0 (Pocket GUI)`.

## Earlier in 0.5.0 "Command Deck"

- **130 new commands** for editing, code, files/project and info. See the command pack below.

## Earlier in 0.4.0 "Neon Playground"

- **Version name.** Releases now have a name. `nview --version` prints `nview 0.6.0 (Pocket GUI)`.
- **Installer menu** with Install, Update and Uninstall.

- **English by default.** The interface language is now English unless your saved
  settings say otherwise. Turkish stays available.
- **New languages:** Deutsch (`de`), Español (`es`), Français (`fr`), next to
  Türkçe (`tr`) and English (`en`). Switch in Settings, with `:lang de`, or `--lang de`.
  The main screens, settings and the whole N box flow are translated; strings that
  are not translated yet fall back to English.
- **Seven new themes** (vscode, dracula, monokai, nord, gunes, gece-mavisi, kiraz).
- **Code + playground** in its own framed window with an IDE layout: tabs, explorer, completion popup, terminal panel and a richer
  status bar (see below). F5 now also works with relative file paths.
- **N box shows your boxes.** See which distributions are installed and whether
  each box is running.
- **GUI package install.** Pick a `.deb` or `.rpm` in the file browser and install
  it into the matching box.
- **One box per distribution.** Fedora, Ubuntu, Debian and Arch each get their own
  box (`nbox-fedora`, `nbox-ubuntu`, ...), so you can have Debian and Fedora side by side.

## N box (distrobox)

Open **N box** from the splash screen (or type `:box`):

    N box > Install              choose a distribution: Fedora (rpm), Ubuntu 24.04 (deb),
                                 Debian 12 (deb), Arch Linux. Already installed ones are
                                 marked with a check mark.
    N box > Boxes                lists every distrobox box on the system: name, image,
                                 state (● running, ○ stopped) and package type.
                                 Enter on a box opens the package picker for that box.
    N box > Install package      opens the package picker (also `:pkg`)

### Installing a distribution

1. distrobox is downloaded with the official install script into `~/.local`
   (no admin rights needed). The script is saved to a file first, then run.
2. If there is no container engine (podman or docker), one is installed with your
   package manager. This step needs admin rights; without them the console shows an error.
3. A box named `nbox-<distro>` is created and prepared (skipped if it already exists).
4. `distrobox --version` verifies the setup.

Progress and a live console are shown on the setup screen. Esc leaves the screen;
the job keeps running in the background.

### Installing a package from the GUI

1. Open **N box > Install package** (or press Enter on a box in **N box > Boxes**).
2. The file browser opens in `~/Downloads` and shows only folders and `.deb` / `.rpm`
   files. If you started from a specific box, only the type that fits it is shown.
3. Move with `j` / `k`, enter folders with Enter, go up with `-`, and press Enter on
   a package to install it.

    .deb  ->  a Debian or Ubuntu box   (apt-get update, then apt-get install)
    .rpm  ->  a Fedora box             (dnf install)

When you do not pick a box yourself, nview chooses one that matches the package
type, preferring a running box. The package must be inside your home directory,
because distrobox shares it with the box.

Shortcut: in the regular file browser (Ctrl-o), select a `.deb` / `.rpm` and press `b`.

## File browser

Opened with Ctrl-o, `:open` or `nview open`.

    j k            select (arrow keys work too)
    Enter / l      enter a folder or open a file
    - / h          parent folder
    /  or  :       type a path (OPEN >_ prompt) and press Enter
    .              show / hide hidden files
    Tab            switch to the SETTINGS tab
    Esc / q        go back

## Settings

Switch with Tab to the SETTINGS tab or type `:settings`. Groups: VIEW, CODE AREA,
EDITING, APP. A description of the selected option is shown at the bottom.
Values are saved to `~/.config/nview/config.json`.

    j k            select
    Enter / l      change (next value)
    h              previous value
    Tab            switch to the OPEN FILE tab
    Esc / q        go back

Code area options: column ruler (off, 80, 100, 120), show whitespace, indent guides,
bracket matching, auto-close brackets, auto indent, tab width (2/4/8), trim trailing
spaces on save, final newline on save.

Themes: `neon-mor` (default), `mor-tonlar`, `okyanus`, `orman`, and new in 0.4.0: `vscode`,
`dracula`, `monokai`, `nord`, `gunes` (Solarized), `gece-mavisi` (Tokyo Night), `kiraz`.
Languages: `en` (default), `tr`, `de`, `es`, `fr`.
Commands: `:theme okyanus`, `:lang de`, `:settings`.

## Features that Nvim, Vim and Nano do not have

    Focus mode           Settings > VIEW. Text outside the cursor paragraph is dimmed.
    Word counter         Live word count in the status bar.
    Word goal            :goal 500 sets a session goal; progress bar in the status bar.
    Timeline             A snapshot is taken on every save. :timeline lists them with
                         line deltas; Enter restores one (undoable).
    Clip history         The last 10 cuts/copies are kept. Ctrl-p or :clip picks one.

## Code + playground (IDE layout)

**Code +** opens a playground folder, `~/nview-playground` (change it with the `NVIEW_PLAYGROUND`
environment variable). New files from Code + are created there, so you can try code without
touching your projects. Files in the playground open in their own rounded window (a framed box with
a title bar) with a VS Code style layout, when the terminal is at least 70 columns by 16 rows.
Files opened anywhere else keep the classic full-screen editor view.
Use `:play` to browse the playground folder.

    Title bar        file name and folder
    Tab bar          one tab per open buffer, with a language badge and a ● when modified
    Breadcrumb       folder > file > ƒ current function or class
    Explorer         left side: files of the current folder (F2 show/hide, F3 focus)
    Completion       a popup while you type: words from your open buffers plus language
                     keywords. Up/Down choose, Tab or Enter accept, Esc dismisses
    Terminal panel   F5 / Ctrl-r runs the file. A DONE or FAIL badge shows the time or exit code
    Status bar       mode, git branch, ✖ errors, ▲ warnings, Ln/Col, Spaces, UTF-8, LF, language

Explorer keys (after F3): j k select, Enter or l open a file or enter a folder, h or - parent folder,
Esc or F3 back to the editor.

Errors are real syntax errors for Python and JSON files. Warnings count lines with trailing
spaces. Turn the layout off with `:ide` or in Settings > CODE AREA (IDE layout, File explorer).

## Code workspace

Choose **Code +** on the splash screen (or press `+`) to pick a language; a new file
opens with a matching template. To run code:

    Ctrl-r or F5       save and run (insert and navigation mode)
    F6                 toggle the output panel
    :run               run
    :panel             output panel

Runners: Python (python3), JavaScript (node), Bash, Go, C (cc), C++ (c++),
Rust (rustc), Java (javac/java). Runs time out after 10 seconds.

Extra shortcuts (insert mode): Ctrl-k delete line (goes to the clipboard), Ctrl-d duplicate line.

## Editing

You can type right after opening a file. Ctrl shortcuts:

    Ctrl-s        save            Ctrl-q  quit
    Ctrl-f        find            Ctrl-/  find
    Ctrl-g        go to line      Ctrl-o  open file
    Ctrl-n        new buffer      Ctrl-l  redraw screen

Esc switches to navigation mode (NAV) where Vim keys work. Press i to go back.

    i a I A       back to insert mode
    o O           new line below / above
    x  dd  3dd    delete character and lines
    yy 3yy p P    copy and paste lines
    u             undo
    :w  :wq  :q  :q!  :qa!     commands
    :e file  :e!               open a file / reload from disk

Tabs are converted to four spaces on save.

## Navigation

    h j k l, arrows        cursor (count prefix: 5j)
    w b e  ^ 0 $           word, start of line, end of line
    { }                    paragraph
    gg G 42G               start of file, end of file, line
    H M L                  top, middle, bottom of the screen
    Ctrl-d/u  Ctrl-f/b     half and full page scroll
    Ctrl-e/y  zz zt zb     scroll by line, position the screen
    ma  'a                 set a mark, jump to a mark
    /pattern  ?pattern  n N  * #   search
    gt gT  :bn :bp :ls     switch buffers
    F1  or  :help          help

## Commands

    :N                     go to line N
    :set nu rnu wrap ic hls syn cul
                           turn an option on; prefix no to turn off, suffix ! to toggle, ? to query
    :noh                   clear highlighting
    :box  :pkg             N box and package picker
    :play                  browse the Code + playground
    :ide                   toggle the IDE layout
    :version               version

## GUI layer: menu bar, palette and mouse

nview now behaves more like a desktop editor while staying in the terminal.

    Menu bar         row 1: File, Edit, Format, Insert, Code, Go, View, Tools, Help.
                     98 menu items. Open with F10 or a click; Left/Right switch menus, Up/Down
                     select, Enter runs, Esc closes. Items with "..." open the command line
                     pre-filled so you only type the argument.
    Command palette  F4 (or Go > Command palette). Type to filter menu items and all 130 commands,
                     Up/Down choose, Enter runs. Click a row to run it.
    Mouse            click to place the cursor, click menu titles and menu items, click tabs to
                     switch buffers, click explorer entries to open files or enter folders, and
                     scroll with the wheel. It works inside the Code + window too.
    Toggles          `:menubar` hides the menu bar, `:mouse` turns mouse support off so your
                     terminal can select text again (or hold Shift while selecting).

## Command pack (130 commands)

Version 0.5.0 adds 130 commands. Run `:commands` for a searchable list (Enter on an entry shows its
description), `:features` for a summary and `:cmdhelp NAME` for one command. Line commands take a range:
`:%sort` (whole file, the default), `:3,9upper`, `:.,$indent 4`. Every command can be undone with `u`.
A bad regex or bad input shows a message and never crashes the editor.

### Editing (72)

    :align        Align lines on a separator (default =)
    :base64dec    Base64-decode each line
    :base64enc    Base64-encode each line
    :bullet       Prefix lines with "- "
    :camel        Convert identifiers to camelCase
    :capitalize   Capitalize the first letter of each line
    :center       Center lines in a width (default 80)
    :commas       Join lines with commas
    :constant     Convert identifiers to UPPER_SNAKE
    :csv2md       Turn CSV lines into a Markdown table
    :date         Insert today's date
    :datetime     Insert date and time  (also :now)
    :dedent       Remove up to N leading spaces (default 4)
    :dedupe       Remove all duplicate lines (keep first)
    :delblank     Delete blank lines
    :dup          Duplicate the lines
    :filter       Keep only lines matching a regex  (also :keep)
    :hexdec       Hex-decode each line
    :hexenc       Hex-encode each line
    :htmlesc      Escape HTML characters
    :htmlunesc    Unescape HTML entities
    :incr         Add N (default 1) to every number
    :indent       Indent lines (default 4 spaces)
    :join         Join all lines into one (space separated)
    :json         Pretty-print JSON
    :jsonmin      Minify JSON
    :jsonsort     Pretty-print JSON with sorted keys
    :kebab        Convert identifiers to kebab-case
    :lorem        Insert N words of placeholder text (default 30)
    :lower        lowercase lines
    :nl           Prefix lines with zero-padded numbers
    :number       Prefix lines with 1. 2. 3.
    :pascal       Convert identifiers to PascalCase
    :prefix       Add text at the start of every line
    :pwgen        Insert a random password (default 20 chars)
    :quote        Prefix lines with "> "
    :reject       Remove lines matching a regex  (also :drop)
    :reverse      Reverse the order of lines  (also :rev)
    :revwords     Reverse the words inside each line
    :right        Right-align lines in a width (default 80)
    :rot13        ROT13 each line
    :s            Substitute: :%s/old/new/gi  (also :sub)
    :seq          Insert numbers 1..N on separate lines
    :shuffle      Shuffle lines randomly
    :snake        Convert identifiers to snake_case
    :sort         Sort lines A-Z
    :sorti        Sort lines ignoring case
    :sortlen      Sort lines by length
    :sortn        Sort lines by the first number in them
    :sortr        Sort lines Z-A  (also :sort!)
    :sortwords    Sort the words inside each line
    :splitat      Split every line at a delimiter into several lines
    :squeeze      Collapse runs of blank lines into one
    :suffix       Add text at the end of every line
    :surround     Surround every line with a character (default ")
    :swapcase     sWAP cASE
    :time         Insert the current time
    :timestamp    Insert a Unix timestamp
    :title        Title Case lines
    :trim         Remove trailing spaces
    :trimall      Remove spaces at both ends
    :trimleft     Remove leading spaces
    :unbullet     Remove "- " or "* " prefixes
    :uniq         Remove adjacent duplicate lines
    :unnumber     Remove 1. 2. 3. prefixes
    :unquote      Remove "> " prefixes
    :unwrap       Join paragraphs into single lines
    :upper        UPPERCASE lines
    :urldec       URL-decode each line
    :urlenc       URL-encode each line
    :uuid         Insert a random UUID
    :wrap         Hard-wrap long lines at a width (default 72)

### Code (17)

    :banner       Insert a comment banner (:banner TEXT)
    :bracketcheck Find unbalanced brackets
    :comment      Comment lines using the file language
    :def          Jump to a function/class/variable definition  (also :goto-def)
    :dupelines    List duplicated lines
    :hr           Insert a horizontal rule
    :imports      List import/include lines
    :longlines    List lines longer than N (default 100)
    :nexterr      Jump to the first syntax error (Python/JSON)
    :outline      List functions and classes (Enter jumps)  (also :symbols)
    :rmcomments   Delete whole-line comments
    :snippet      Insert a snippet for this language (:snippet main)  (also :snip)
    :snippets     List snippets for this language
    :todo         List TODO / FIXME / XXX / HACK lines
    :togglecomment Toggle comments on lines  (also :tc)
    :trailing     List lines with trailing spaces
    :uncomment    Uncomment lines

### View (9)

    :cmdhelp      Describe a command (:cmdhelp sort)
    :commands     Command palette: every command with its description  (also :palette)
    :cursorline   Toggle the cursor line highlight  (also :cl)
    :features     Count and group the extra commands
    :guides       Toggle indent guides
    :ruler        Set the column ruler (:ruler 80, 0 = off)
    :tab          Set the tab width (:tab 2)
    :whitespace   Toggle whitespace dots  (also :ws)
    :zen          Toggle distraction-free mode (no explorer, no numbers)

### Files and project (19)

    :backup       Save a copy as name.bak  (also :bak)
    :bm           Bookmark the current line  (also :bookmark)
    :bms          List bookmarks (Enter jumps)  (also :bookmarks)
    :cd           Change the working folder
    :dir          List files in a folder (Enter opens)
    :dirtree      Show a folder tree (:dirtree [depth])  (also :dt)
    :diskdiff     Show what changed compared to the saved file
    :find         Find files by name under the current folder  (also :ff)
    :gitbranch    Current git branch  (also :gb)
    :gitdiff      git diff of the current file  (also :gd)
    :gitlog       Last 20 commits  (also :gl)
    :gitstatus    Changed files according to git (Enter opens)  (also :gs)
    :grep         Search all files under the current folder (Enter jumps)
    :new          Create and open a new file (:new name.py)  (also :touch)
    :pwd          Print the working folder
    :r            Insert the contents of a file below the cursor  (also :read)
    :recent       Recently opened files (Enter opens)
    :rename       Rename the current file  (also :mv)
    :sh           Run a shell command and show its output  (also :!)

### Info (13)

    :avg          Average of numbers in the range
    :calc         Calculator: :calc 2*(3+4)  (:calc! also inserts the result)
    :calc!        Calculator that inserts the result at the cursor
    :count        Count matches of a regex
    :freq         Most frequent words
    :marks        List marks set with m<letter>
    :md5          MD5 of the range
    :minmax       Smallest and largest number
    :sha1         SHA-1 of the range
    :sha256       SHA-256 of the range
    :stats        Lines, words, characters and bytes  (also :wc)
    :sum          Sum all numbers in the range
    :where        Path, size, language and modified time of this file

## Changes (0.3.0)

- Edit mode, saving, undo, line delete/paste added. The previous release was read-only; `:w` gave E45.
- Ctrl-S saves and Ctrl-Q quits (terminal flow control is off, so Ctrl-S does not freeze the terminal).
- `nview read` added (non-interactive, colored output).
- Screen redraw (Ctrl-l, `:redraw`) and reload from disk (`:e!`).
- Theme option (4 themes) and language option (Turkish / English).
- New splash screen; header and status bar added.
- A file name that does not exist opens a new file instead of failing.
- A clear error message when the terminal is not interactive.
- The installer looks like the app's splash screen.
