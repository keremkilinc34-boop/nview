#!/usr/bin/env python3
"""nview - Neovim tarzı, renkli, minimal metin düzenleyici.

Kullanım:
  nview [seçenekler] [dosya ...]      düzenleyiciyi aç
  nview read [--plain] dosya ...      dosyayı terminale renkli yazdır ve çık

Seçenekler:
  --no-splash     açılış ekranını atla
  --theme AD      tema: neon-mor, mor-tonlar, okyanus, orman, vscode, dracula, monokai, nord, gunes, gece-mavisi, kiraz
  --lang KOD      dil: tr, en
  --plain         (read ile) renk ve satır numarası olmadan yazdır
  --version, -h   sürüm ve yardım
"""
import curses
import hashlib
import json
import locale
import os
import re
import shlex
import tempfile
import threading
import shutil
import subprocess
import sys
import time
import ast
import base64
import codecs
import collections
import difflib
import html
import math
import operator
import random
import string
import textwrap
import urllib.parse
import uuid

VERSION = '0.6.0'
VERSION_NAME = 'Pocket GUI'
CONFIG_FILE = os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'),
                           'nview', 'config.json')
TOP = 1  # üstteki bilgi satırı
STATE_DIR = os.path.join(os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state'),
                         'nview', 'snapshots')
MAX_SNAPS = 30
RING_MAX = 10

# ------------------------------------------------------------------ ayarlar

SETTINGS = {'theme': 'neon-mor', 'lang': 'en', 'opts': {}, 'box': None}
START = {'mode': None, 'dir': None}


def load_config():
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            data = json.load(f)
        for k in SETTINGS:
            if isinstance(data.get(k), str):
                SETTINGS[k] = data[k]
        if isinstance(data.get('opts'), dict):
            SETTINGS['opts'] = data['opts']
        if isinstance(data.get('box'), dict):
            SETTINGS['box'] = data['box']
    except (OSError, ValueError):
        pass
    if SETTINGS['theme'] not in THEMES:
        SETTINGS['theme'] = 'neon-mor'
    if SETTINGS['lang'] not in STR:
        SETTINGS['lang'] = 'en'


def save_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def persist(opts=None):
    if opts is not None:
        SETTINGS['opts'] = dict(opts)
    return t('saved_cfg') if save_config() else t('nocfg')


SETTING_ROWS = [
    'H:grp_view', 'theme', 'lang', 'number', 'relativenumber', 'syntax', 'cursorline',
    'hlsearch', 'ignorecase', 'focus',
    'H:grp_code', 'ide', 'sidebar', 'ruler', 'showws', 'indentguide', 'bracketmatch', 'autoclose',
    'autoindent', 'tabsize', 'trimws', 'finalnl',
    'H:grp_edit', 'wrap', 'scrolloff', 'wordgoal',
    'H:grp_app', 'statushints', 'confirmquit', 'snapshots',
]
SETTING_KEYS = [r for r in SETTING_ROWS if not r.startswith('H:')]
CHOICES = {'tabsize': [2, 4, 8], 'scrolloff': [0, 3, 5, 8], 'ruler': [0, 80, 100, 120],
           'wordgoal': [0, 250, 500, 1000, 2000]}
TABSIZES = CHOICES['tabsize']
SCROLLOFFS = CHOICES['scrolloff']
PAIRS = {'(': ')', '[': ']', '{': '}'}
RPAIRS = {v: k for k, v in PAIRS.items()}
SPLASH_ITEMS = [('new', '^N'), ('open', '^O'), ('find', '^F'), ('code', '+'), ('box', 'N'), ('settings', '...'), ('quit', '^Q')]


# ------------------------------------------------------------------ çeviri

LANG_NAMES = {'tr': 'Türkçe', 'en': 'English', 'de': 'Deutsch', 'es': 'Español', 'fr': 'Français'}

STR = {
    'tr': {
        'subtitle': 'Basit, hızlı ve minimal metin düzenleyici.',
        'start': 'Başlamak için bir tuşa basın...',
        'key_new': 'Yeni dosya', 'key_open': 'Dosya aç', 'key_save': 'Kaydet',
        'key_find': 'Bul', 'key_quit': 'Çık', 'key_settings': 'Ayarlar (tema, dil)',
        'mode_normal': 'NORMAL', 'mode_nav': 'GEZİN', 'mode_insert': 'EKLE', 'mode_search': 'ARA',
        'mode_cmd': 'KOMUT', 'mode_menu': 'AYAR',
        'l_save': 'Kaydet', 'l_quit': 'Çık', 'l_find': 'Bul', 'l_goto': 'Satıra Git', 'l_search': 'Ara', 'h_save': '^S Kaydet', 'h_open': '^O Aç', 'h_find': '/ Ara', 'h_quit': ':q Çık',
        'noname': '[Yeni]', 'mod': '[+]', 'ln': 'Satır',
        'loaded': '"{name}" {n} satır   (? yardım)',
        'newfile': '"{name}" yeni dosya (kaydedince oluşur)',
        'binary': 'İkili dosya gibi görünüyor, düzenleme kapalı',
        'binary_write': 'Yazılmadı: ikili dosya',
        'noname_write': 'E32: Dosya adı yok. :w dosya_adı kullanın',
        'write_fail': 'E212: Yazılamadı: {err}',
        'written': '"{name}" yazıldı ({n} satır)',
        'wrote_all': '{n} dosya yazıldı',
        'quit_modified': 'Kaydedilmemiş değişiklik var. :w ile kaydedin ya da :q! ile atın',
        'reloaded': '"{name}" diskten yeniden yüklendi',
        'redrawn': 'Ekran yenilendi',
        'no_search': 'Önce /desen ile arayın',
        'not_found': 'E486: Desen bulunamadı: {pat}',
        'wrapped': '   (baştan devam)',
        'no_word': 'İmlecin altında kelime yok',
        'mark_set': 'İşaret {ch} ayarlandı',
        'mark_missing': 'E20: İşaret bulunamadı: {ch}',
        'copied': '{n} satır kopyalandı ({where})',
        'clip_sys': 'sistem panosu', 'clip_int': 'dahili kayıt',
        'pasted': '{n} satır yapıştırıldı',
        'deleted': '{n} satır silindi',
        'empty_reg': 'Kayıt boş',
        'undo_none': 'Geri alınacak bir şey yok', 'undone': 'Geri alındı',
        'reg_show': 'Kayıt: {text}',
        'ctrl_c': 'Çıkmak için :q yazın',
        'nofile': 'E484: Dosya bulunamadı: {path}',
        'isdir': 'E502: Bu bir klasör: {path}',
        'opened': '"{path}" açıldı',
        'usage_e': 'Kullanım: :e dosya',
        'bad_opt': 'E518: Bilinmeyen seçenek: {a}',
        'unknown_cmd': 'E492: Bilinmeyen komut: {name}',
        'theme_list': 'Temalar: {list}',
        'bad_theme': 'Bilinmeyen tema: {name}   (temalar: {list})',
        'theme_set': 'Tema: {name}',
        'bad_lang': 'Bilinmeyen dil: {name}   (diller: tr, en, de, es, fr)',
        'lang_set': 'Dil: {name}',
        'saved_cfg': 'Ayarlar kaydedildi',
        'nocfg': 'Ayarlar kaydedilemedi (yazma izni yok)',
        'menu_title': 'Ayarlar', 'menu_theme': 'Tema', 'menu_lang': 'Dil',
        'menu_foot': 'j/k seç   Enter değiştir   Esc kapat',
        'help_close': 'Kapatmak için bir tuşa basın',
        'pct_all': 'Tümü', 'pct_top': 'Üst', 'pct_bot': 'Alt',
        'version_line': 'nview {v} ({name})',
        'usage': 'Kullanım: nview [--no-splash] [--theme AD] [--lang KOD] [dosya ...]\n'
                 '       nview read [--plain] dosya ...',
        'read_usage': 'Kullanım: nview read [--plain] dosya ...   (- ile stdin okunur)',
        'bad_file': 'Dosya bulunamadı: {path}',
        'bin_skip': 'İkili dosya atlandı: {path}',
        'bad_option': 'Bilinmeyen seçenek: {a}',
        'no_tty': 'nview etkileşimli bir terminal gerektirir. Yazdırmak için: nview read dosya',
    },
    'en': {
        'subtitle': 'A simple, fast and minimal text editor.',
        'start': 'Press any key to start editing...',
        'key_new': 'New File', 'key_open': 'Open File', 'key_save': 'Save File',
        'key_find': 'Find', 'key_quit': 'Quit', 'key_settings': 'Settings (theme, language)',
        'mode_normal': 'NORMAL', 'mode_nav': 'NAV', 'mode_insert': 'INSERT', 'mode_search': 'SEARCH',
        'mode_cmd': 'COMMAND', 'mode_menu': 'SETTINGS',
        'l_save': 'Save', 'l_quit': 'Quit', 'l_find': 'Find', 'l_goto': 'Go To Line', 'l_search': 'Search', 'h_save': '^S Save', 'h_open': '^O Open', 'h_find': '/ Find', 'h_quit': ':q Quit',
        'noname': '[New]', 'mod': '[+]', 'ln': 'Line',
        'loaded': '"{name}" {n} lines   (? help)',
        'newfile': '"{name}" new file (created on save)',
        'binary': 'Looks like a binary file, editing disabled',
        'binary_write': 'Not written: binary file',
        'noname_write': 'E32: No file name. Use :w file_name',
        'write_fail': 'E212: Cannot write: {err}',
        'written': '"{name}" written ({n} lines)',
        'wrote_all': '{n} files written',
        'quit_modified': 'Unsaved changes. Use :w to save or :q! to discard',
        'reloaded': '"{name}" reloaded from disk',
        'redrawn': 'Screen redrawn',
        'no_search': 'Search first with /pattern',
        'not_found': 'E486: Pattern not found: {pat}',
        'wrapped': '   (search wrapped)',
        'no_word': 'No word under cursor',
        'mark_set': 'Mark {ch} set',
        'mark_missing': 'E20: Mark not set: {ch}',
        'copied': '{n} lines yanked ({where})',
        'clip_sys': 'system clipboard', 'clip_int': 'internal register',
        'pasted': '{n} lines pasted',
        'deleted': '{n} lines deleted',
        'empty_reg': 'Register is empty',
        'undo_none': 'Nothing to undo', 'undone': 'Undone',
        'reg_show': 'Register: {text}',
        'ctrl_c': 'Type :q to quit',
        'nofile': 'E484: File not found: {path}',
        'isdir': 'E502: This is a directory: {path}',
        'opened': '"{path}" opened',
        'usage_e': 'Usage: :e file',
        'bad_opt': 'E518: Unknown option: {a}',
        'unknown_cmd': 'E492: Not an editor command: {name}',
        'theme_list': 'Themes: {list}',
        'bad_theme': 'Unknown theme: {name}   (themes: {list})',
        'theme_set': 'Theme: {name}',
        'bad_lang': 'Unknown language: {name}   (languages: tr, en, de, es, fr)',
        'lang_set': 'Language: {name}',
        'saved_cfg': 'Settings saved',
        'nocfg': 'Could not save settings (no write permission)',
        'menu_title': 'Settings', 'menu_theme': 'Theme', 'menu_lang': 'Language',
        'menu_foot': 'j/k select   Enter change   Esc close',
        'help_close': 'Press any key to close',
        'pct_all': 'All', 'pct_top': 'Top', 'pct_bot': 'Bot',
        'version_line': 'nview {v} ({name})',
        'usage': 'Usage: nview [--no-splash] [--theme NAME] [--lang CODE] [file ...]\n'
                 '       nview read [--plain] file ...',
        'read_usage': 'Usage: nview read [--plain] file ...   (use - to read stdin)',
        'bad_file': 'File not found: {path}',
        'bin_skip': 'Binary file skipped: {path}',
        'bad_option': 'Unknown option: {a}',
        'no_tty': 'nview needs an interactive terminal. To print a file: nview read FILE',
    },
}


STR['tr'].update({
    'tab_file': 'DOSYA AÇ', 'tab_settings': 'AYARLAR', 'title_settings': 'AYARLAR',
    'mode_open': 'DOSYA', 'mode_settings': 'AYAR', 'dir': 'DİZİN', 'empty_dir': 'Bu dizin boş',
    'cant_read': 'Okunamadı: {path}', 'hidden_on': 'Gizli dosyalar gösteriliyor',
    'hidden_off': 'Gizli dosyalar gizlendi', 'prompt_open': 'AÇ >_ ',
    'st_theme': 'Tema', 'st_lang': 'Dil', 'st_number': 'Satır numaraları',
    'st_wrap': 'Satır kaydırma', 'st_syntax': 'Sözdizimi renkleri',
    'st_cursorline': 'İmleç satırı vurgusu', 'st_hlsearch': 'Arama vurgusu',
    'st_ignorecase': 'Büyük/küçük harf duyarsız', 'on': 'AÇIK', 'off': 'KAPALI',
    'l_select': 'Seç', 'l_open': 'Aç', 'l_up': 'Üst dizin', 'l_path': 'Yol yaz',
    'l_hidden': 'Gizli', 'l_tab': 'Sekme', 'l_back': 'Geri', 'l_change': 'Değiştir',
    'l_value': 'Değer', 'l_file': 'Dosya',
})
STR['en'].update({
    'tab_file': 'OPEN FILE', 'tab_settings': 'SETTINGS', 'title_settings': 'SETTINGS',
    'mode_open': 'FILES', 'mode_settings': 'SETTINGS', 'dir': 'DIR', 'empty_dir': 'Directory is empty',
    'cant_read': 'Cannot read: {path}', 'hidden_on': 'Hidden files shown',
    'hidden_off': 'Hidden files hidden', 'prompt_open': 'OPEN >_ ',
    'st_theme': 'Theme', 'st_lang': 'Language', 'st_number': 'Line numbers',
    'st_wrap': 'Line wrap', 'st_syntax': 'Syntax colors',
    'st_cursorline': 'Cursor line highlight', 'st_hlsearch': 'Search highlight',
    'st_ignorecase': 'Ignore case', 'on': 'ON', 'off': 'OFF',
    'l_select': 'Select', 'l_open': 'Open', 'l_up': 'Parent', 'l_path': 'Type path',
    'l_hidden': 'Hidden', 'l_tab': 'Tab', 'l_back': 'Back', 'l_change': 'Change',
    'l_value': 'Value', 'l_file': 'File',
})


STR['tr'].update({
    'sp_new': 'Yeni dosya', 'sp_open': 'Dosya aç', 'sp_find': 'Bul',
    'sp_settings': 'Ayarlar', 'sp_quit': 'Çık',
    'sp_hint': 'Yön tuşları: seç    Enter: aç    Yazmaya başlamak için harf yazın',
    'st_relativenumber': 'Göreli satır numaraları', 'st_autoindent': 'Otomatik girinti',
    'st_tabsize': 'Sekme genişliği', 'st_scrolloff': 'İmleç kenar payı',
    'st_statushints': 'Durum çubuğu ipuçları', 'st_confirmquit': 'Değişiklik varken uyar',
})
STR['en'].update({
    'sp_new': 'New file', 'sp_open': 'Open file', 'sp_find': 'Find',
    'sp_settings': 'Settings', 'sp_quit': 'Quit',
    'sp_hint': 'Arrow keys: select    Enter: open    Type a letter to start writing',
    'st_relativenumber': 'Relative line numbers', 'st_autoindent': 'Auto indent',
    'st_tabsize': 'Tab width', 'st_scrolloff': 'Cursor scroll margin',
    'st_statushints': 'Status bar hints', 'st_confirmquit': 'Warn on unsaved changes',
})


STR['tr'].update({
    'matches': '{n} eşleşme', 'find_nofile': 'Aranacak dosya yok: önce bir dosya açın',
})
STR['en'].update({
    'matches': '{n} matches', 'find_nofile': 'Nothing to search: open a file first',
})


STR['tr'].update({
    'grp_view': 'GÖRÜNÜM', 'grp_code': 'KOD ALANI', 'grp_edit': 'DÜZENLEME', 'grp_app': 'UYGULAMA',
    'st_ruler': 'Sütun çizgisi', 'st_showws': 'Boşlukları göster', 'st_indentguide': 'Girinti kılavuzları',
    'st_bracketmatch': 'Parantez eşleştirme', 'st_autoclose': 'Parantezleri otomatik kapat',
    'st_trimws': 'Kaydederken sondaki boşlukları sil', 'st_finalnl': 'Kaydederken son satır sonu',
    'd_theme': 'Renk paleti seçin', 'd_lang': 'Arayüz dilini değiştirir',
    'd_number': 'Satır numaralarını gösterir', 'd_relativenumber': 'Numaraları imleçten uzaklığa göre gösterir',
    'd_syntax': 'Kod için renkli vurgulama', 'd_cursorline': 'İmlecin olduğu satırı vurgular',
    'd_hlsearch': 'Arama sonuçlarını vurgular', 'd_ignorecase': 'Aramada büyük/küçük harfi yok sayar',
    'd_ruler': 'Bu sütunda dikey çizgi çizer (kapalı: 0)', 'd_showws': 'Boşlukları · işaretiyle gösterir',
    'd_indentguide': 'Girinti seviyelerini ┊ ile gösterir', 'd_bracketmatch': 'İmlecin yanındaki parantezin eşini vurgular',
    'd_autoclose': '( [ { yazınca karşılığını da ekler', 'd_autoindent': 'Yeni satırda önceki girintiyi korur',
    'd_tabsize': 'Tab tuşunun eklediği boşluk sayısı', 'd_trimws': 'Kaydetmeden önce satır sonu boşluklarını siler',
    'd_finalnl': 'Dosyayı bir satır sonu ile bitirir', 'd_wrap': 'Uzun satırları ekrana sığacak şekilde kırar',
    'd_scrolloff': 'İmleç kenara bu kadar satır kalınca kaydırır', 'd_statushints': 'Alt çubukta kısayol ipuçlarını gösterir',
    'd_confirmquit': 'Kaydedilmemiş değişiklik varken çıkmadan uyarır',
})
STR['en'].update({
    'grp_view': 'VIEW', 'grp_code': 'CODE AREA', 'grp_edit': 'EDITING', 'grp_app': 'APP',
    'st_ruler': 'Column ruler', 'st_showws': 'Show whitespace', 'st_indentguide': 'Indent guides',
    'st_bracketmatch': 'Bracket matching', 'st_autoclose': 'Auto-close brackets',
    'st_trimws': 'Trim trailing spaces on save', 'st_finalnl': 'Final newline on save',
    'd_theme': 'Choose a color palette', 'd_lang': 'Changes the interface language',
    'd_number': 'Shows line numbers', 'd_relativenumber': 'Shows numbers relative to the cursor',
    'd_syntax': 'Colors code by syntax', 'd_cursorline': 'Highlights the cursor line',
    'd_hlsearch': 'Highlights search matches', 'd_ignorecase': 'Ignores case when searching',
    'd_ruler': 'Draws a vertical line at this column (off: 0)', 'd_showws': 'Shows spaces as dots',
    'd_indentguide': 'Shows indent levels with ┊', 'd_bracketmatch': 'Highlights the match of the bracket next to the cursor',
    'd_autoclose': 'Adds the closing character when you type ( [ {', 'd_autoindent': 'Keeps the previous indent on a new line',
    'd_tabsize': 'Number of spaces inserted by the Tab key', 'd_trimws': 'Removes trailing spaces before saving',
    'd_finalnl': 'Ends the file with a newline', 'd_wrap': 'Wraps long lines to fit the screen',
    'd_scrolloff': 'Scrolls when the cursor gets this close to the edge', 'd_statushints': 'Shows shortcut hints in the status bar',
    'd_confirmquit': 'Warns before quitting with unsaved changes',
})


STR['tr'].update({
    'st_focus': 'Odak modu', 'd_focus': 'İmlecin paragrafı dışındaki metni soluklaştırır',
    'st_wordgoal': 'Kelime hedefi', 'd_wordgoal': 'Oturum hedefi; durum çubuğunda ilerleme gösterir (kapalı: 0)',
    'st_snapshots': 'Kaydederken zaman çizelgesi', 'd_snapshots': 'Her kaydetmede anlık görüntü alır (:zaman ile gezin)',
    'tab_timeline': 'ZAMAN ÇİZGİSİ', 'tab_ring': 'PANO', 'mode_timeline': 'ZAMAN', 'mode_ring': 'PANO',
    'l_restore': 'Geri yükle', 'l_paste': 'Yapıştır', 'list_empty': 'Henüz kayıt yok',
    'restored': 'Anlık görüntü geri yüklendi', 'goal_set': 'Kelime hedefi: {n}',
    'words': 'kelime', 'bad_num': 'Sayı bekleniyor: {a}',
})
STR['en'].update({
    'st_focus': 'Focus mode', 'd_focus': 'Dims the text outside the cursor paragraph',
    'st_wordgoal': 'Word goal', 'd_wordgoal': 'Session goal shown as progress in the status bar (off: 0)',
    'st_snapshots': 'Snapshots on save', 'd_snapshots': 'Takes a snapshot on every save (browse with :timeline)',
    'tab_timeline': 'TIMELINE', 'tab_ring': 'CLIPS', 'mode_timeline': 'TIMELINE', 'mode_ring': 'CLIPS',
    'l_restore': 'Restore', 'l_paste': 'Paste', 'list_empty': 'Nothing here yet',
    'restored': 'Snapshot restored', 'goal_set': 'Word goal: {n}',
    'words': 'words', 'bad_num': 'Number expected: {a}',
})


STR['tr'].update({
    'sp_box': 'N box', 'box_install': 'Kur', 'box_status': 'Durum', 'tab_box': 'N BOX', 'mode_box': 'NBOX',
    'mode_job': 'KURULUM', 'job_install': 'KURULUM', 'console': 'KONSOL', 'job_pkg': '{name} kuruluyor',
    'st_pkgs': 'Bağımlılıklar kuruluyor (podman, distrobox)', 'st_update': 'Paket listesi güncelleniyor',
    'st_create': 'Kutu oluşturuluyor (nbox)', 'st_dbx_dl': 'distrobox indiriliyor ve ~/.local altına kuruluyor',
    'st_engine': 'Konteyner motoru kuruluyor (podman)', 'st_check': 'Doğrulanıyor (distrobox --version)', 'st_boot': 'Kutu hazırlanıyor', 'st_pkg': 'Paket kuruluyor',
    'job_done': 'Tamamlandı', 'job_failed': 'Hata: çıkış kodu {code}', 'job_busy': 'Zaten bir işlem çalışıyor',
    'box_no_pm': 'Desteklenen paket yöneticisi bulunamadı (dnf, apt, pacman, zypper)',
    'sudo_needed': 'Yönetici izni gerekli: önce terminalde "sudo -v" çalıştırın',
    'box_status_msg': 'Kutu: {name} · tür: {fam} · distrobox: {dt}',
    'box_missing': 'Önce N box > Kur ile kutuyu kurun', 'box_home': 'Paket dosyası ev dizininde olmalı',
    'box_wrongfam': 'Bu paket türü kutunun dağıtımıyla uyumsuz', 'box_notpkg': 'Yalnızca .deb ve .rpm kurulabilir',
    'l_pkg': 'Kutuya kur', 'sp_code': 'Kod +', 'tab_lang': 'KOD DİLİ', 'mode_lang': 'KOD', 'l_new': 'Yeni dosya',
    'no_runner': 'Bu dil için çalıştırıcı yok: {lang}', 'out_title': '{cmd} · çıkış {code}',
    'out_empty_title': 'ÇIKTI', 'out_hint': 'Ctrl-r ile kodu çalıştırın', 'out_none': '(çıktı yok)',
    'out_timeout': 'Zaman aşımı (10 sn)', 'ran': 'Çalıştırıldı', 'new_code': 'Yeni {lang} dosyası: {name}',
})
STR['en'].update({
    'sp_box': 'N box', 'box_install': 'Install', 'box_status': 'Status', 'tab_box': 'N BOX', 'mode_box': 'NBOX',
    'mode_job': 'SETUP', 'job_install': 'SETUP', 'console': 'CONSOLE', 'job_pkg': 'Installing {name}',
    'st_pkgs': 'Installing dependencies (podman, distrobox)', 'st_update': 'Updating package list',
    'st_create': 'Creating the box (nbox)', 'st_dbx_dl': 'Downloading distrobox and installing to ~/.local',
    'st_engine': 'Installing a container engine (podman)', 'st_check': 'Verifying (distrobox --version)', 'st_boot': 'Preparing the box', 'st_pkg': 'Installing the package',
    'job_done': 'Done', 'job_failed': 'Error: exit code {code}', 'job_busy': 'Another job is running',
    'box_no_pm': 'No supported package manager found (dnf, apt, pacman, zypper)',
    'sudo_needed': 'Admin rights needed: run "sudo -v" in a terminal first',
    'box_status_msg': 'Box: {name} · family: {fam} · distrobox: {dt}',
    'box_missing': 'Install the box first via N box > Install', 'box_home': 'Package file must be under your home directory',
    'box_wrongfam': 'This package type does not match the box distribution', 'box_notpkg': 'Only .deb and .rpm can be installed',
    'l_pkg': 'Install in box', 'sp_code': 'Code +', 'tab_lang': 'CODE LANGUAGE', 'mode_lang': 'CODE', 'l_new': 'New file',
    'no_runner': 'No runner for: {lang}', 'out_title': '{cmd} · exit {code}',
    'out_empty_title': 'OUTPUT', 'out_hint': 'Press Ctrl-r to run the code', 'out_none': '(no output)',
    'out_timeout': 'Timed out (10 s)', 'ran': 'Ran', 'new_code': 'New {lang} file: {name}',
})


STR['tr'].update({
    'st_create': 'Kutu oluşturuluyor ({name})', 'box_exists': '{name} zaten var, atlanıyor',
    'skipped': '(atlandı)', 'tab_pick': 'PAKET SEÇ', 'l_install': 'Kur',
    'box_list': 'Kutular', 'box_pkg': 'Paket kur (.deb / .rpm)',
    'box_installed': 'kurulu', 'box_none': 'Henüz kutu yok: önce N box > Kur',
    'box_no_dbx': 'distrobox kurulu değil: önce N box > Kur',
    'box_nobox': '{ext} için {fam} ailesinden bir kutu yok: önce N box > Kur',
    'box_nopkgs': '.deb / .rpm dosyası yok (dizinlerde gezinin)',
    'box_pick_hint': 'Paket seçin ve Enter ile kutuya kurun',
})
STR['en'].update({
    'st_create': 'Creating the box ({name})', 'box_exists': '{name} already exists, skipping',
    'skipped': '(skipped)', 'tab_pick': 'PICK PACKAGE', 'l_install': 'Install',
    'box_list': 'Boxes', 'box_pkg': 'Install package (.deb / .rpm)',
    'box_installed': 'installed', 'box_none': 'No boxes yet: use N box > Install first',
    'box_no_dbx': 'distrobox is not installed: use N box > Install first',
    'box_nobox': 'No {fam}-family box for {ext}: use N box > Install first',
    'box_nopkgs': 'No .deb / .rpm files here (browse folders)',
    'box_pick_hint': 'Pick a package and press Enter to install it in the box',
})
STR['tr']['st_create'] = 'Kutu oluşturuluyor ({name})'
STR['tr'].update({
    'mode_palette': 'PALET', 'mode_results': 'SONUÇ',
    'st_ide': 'IDE görünümü', 'd_ide': 'Kod + test alanında sekmeler, gezgin, tamamlama ve terminal paneli gösterir',
    'st_sidebar': 'Dosya gezgini', 'd_sidebar': 'Sol tarafta dosya gezginini gösterir (F2 aç/kapat, F3 odak)',
    'spaces': 'Boşluk', 'explorer': 'GEZGİN', 'terminal': 'TERMİNAL', 'ide_on': 'IDE görünümü: açık', 'ide_off': 'IDE görünümü: kapalı',
})
STR['en'].update({
    'mode_palette': 'PALETTE', 'mode_results': 'RESULTS',
    'st_ide': 'IDE layout', 'd_ide': 'Shows tabs, explorer, completion and a terminal panel in the Code + playground',
    'st_sidebar': 'File explorer', 'd_sidebar': 'Shows the file explorer on the left (F2 toggle, F3 focus)',
    'spaces': 'Spaces', 'explorer': 'EXPLORER', 'terminal': 'TERMINAL', 'ide_on': 'IDE layout: on', 'ide_off': 'IDE layout: off',
})

STR.update({
    'de': {
        'subtitle': 'Einfacher, schneller und minimaler Texteditor.',
        'start': 'Beliebige Taste drücken zum Starten...',
        'key_new': 'Neue Datei', 'key_open': 'Datei öffnen', 'key_save': 'Speichern',
        'key_find': 'Suchen', 'key_quit': 'Beenden', 'key_settings': 'Einstellungen (Design, Sprache)',
        'mode_insert': 'EINFÜGEN', 'mode_search': 'SUCHE', 'mode_cmd': 'BEFEHL', 'mode_menu': 'EINST',
        'l_save': 'Speichern', 'l_quit': 'Beenden', 'l_find': 'Suchen', 'l_goto': 'Zeile', 'l_search': 'Suche',
        'noname': '[Neu]', 'loaded': '"{name}" {n} Zeilen   (? Hilfe)',
        'written': '"{name}" geschrieben ({n} Zeilen)', 'matches': '{n} Treffer',
        'sp_new': 'Neue Datei', 'sp_open': 'Datei öffnen', 'sp_find': 'Suchen',
        'sp_settings': 'Einstellungen', 'sp_quit': 'Beenden',
        'sp_hint': 'Pfeiltasten: wählen    Enter: öffnen    Buchstabe tippen zum Schreiben',
        'tab_file': 'DATEI ÖFFNEN', 'tab_settings': 'EINSTELLUNGEN', 'title_settings': 'EINSTELLUNGEN',
        'mode_open': 'DATEIEN', 'mode_settings': 'EINST', 'dir': 'ORDNER', 'empty_dir': 'Ordner ist leer',
        'cant_read': 'Nicht lesbar: {path}', 'hidden_on': 'Versteckte Dateien sichtbar',
        'hidden_off': 'Versteckte Dateien ausgeblendet',
        'st_theme': 'Design', 'st_lang': 'Sprache', 'st_number': 'Zeilennummern', 'st_wrap': 'Zeilenumbruch',
        'st_syntax': 'Syntaxfarben', 'on': 'AN', 'off': 'AUS',
        'l_select': 'Wählen', 'l_open': 'Öffnen', 'l_up': 'Übergeordnet', 'l_path': 'Pfad',
        'l_hidden': 'Versteckt', 'l_tab': 'Tab', 'l_back': 'Zurück', 'l_change': 'Ändern', 'l_value': 'Wert',
        'l_file': 'Datei', 'grp_view': 'ANSICHT', 'grp_code': 'CODEBEREICH', 'grp_edit': 'BEARBEITEN', 'grp_app': 'APP',
        'lang_set': 'Sprache: {name}', 'list_empty': 'Noch nichts vorhanden',
        'sp_code': 'Code +', 'tab_lang': 'CODESPRACHE', 'mode_lang': 'CODE', 'l_new': 'Neue Datei',
        'box_install': 'Installieren', 'box_list': 'Boxen', 'box_pkg': 'Paket installieren (.deb / .rpm)',
        'box_installed': 'installiert', 'box_none': 'Noch keine Box: zuerst N box > Installieren',
        'box_no_dbx': 'distrobox fehlt: zuerst N box > Installieren',
        'box_nobox': 'Keine Box der Familie {fam} für {ext}: zuerst N box > Installieren',
        'box_nopkgs': 'Keine .deb / .rpm Dateien hier (Ordner durchsuchen)',
        'tab_pick': 'PAKET WÄHLEN', 'l_install': 'Installieren', 'skipped': '(übersprungen)',
        'mode_job': 'SETUP', 'job_install': 'SETUP', 'console': 'KONSOLE', 'job_pkg': '{name} wird installiert',
        'st_pkgs': 'Abhängigkeiten werden installiert (podman, distrobox)', 'st_update': 'Paketliste wird aktualisiert',
        'st_create': 'Box wird erstellt ({name})', 'box_exists': '{name} existiert bereits, übersprungen',
        'st_dbx_dl': 'distrobox wird geladen und nach ~/.local installiert',
        'st_engine': 'Container-Engine wird installiert (podman)', 'st_check': 'Prüfung (distrobox --version)',
        'st_boot': 'Box wird vorbereitet', 'st_pkg': 'Paket wird installiert',
        'job_done': 'Fertig', 'job_failed': 'Fehler: Exit-Code {code}', 'job_busy': 'Ein anderer Vorgang läuft',
        'box_missing': 'Zuerst über N box > Installieren eine Box einrichten',
        'box_home': 'Paketdatei muss im Home-Verzeichnis liegen',
        'box_wrongfam': 'Dieser Pakettyp passt nicht zur Box-Distribution',
        'box_notpkg': 'Nur .deb und .rpm können installiert werden',
        'l_pkg': 'In Box installieren',
    },
    'es': {
        'subtitle': 'Editor de texto simple, rápido y minimalista.',
        'start': 'Pulsa una tecla para empezar...',
        'key_new': 'Nuevo archivo', 'key_open': 'Abrir archivo', 'key_save': 'Guardar',
        'key_find': 'Buscar', 'key_quit': 'Salir', 'key_settings': 'Ajustes (tema, idioma)',
        'mode_insert': 'INSERTAR', 'mode_search': 'BUSCAR', 'mode_cmd': 'COMANDO', 'mode_menu': 'AJUSTES',
        'l_save': 'Guardar', 'l_quit': 'Salir', 'l_find': 'Buscar', 'l_goto': 'Ir a línea', 'l_search': 'Buscar',
        'noname': '[Nuevo]', 'loaded': '"{name}" {n} líneas   (? ayuda)',
        'written': '"{name}" guardado ({n} líneas)', 'matches': '{n} coincidencias',
        'sp_new': 'Nuevo archivo', 'sp_open': 'Abrir archivo', 'sp_find': 'Buscar',
        'sp_settings': 'Ajustes', 'sp_quit': 'Salir',
        'sp_hint': 'Flechas: elegir    Enter: abrir    Escribe una letra para empezar',
        'tab_file': 'ABRIR ARCHIVO', 'tab_settings': 'AJUSTES', 'title_settings': 'AJUSTES',
        'mode_open': 'ARCHIVOS', 'mode_settings': 'AJUSTES', 'dir': 'DIR', 'empty_dir': 'La carpeta está vacía',
        'cant_read': 'No se puede leer: {path}', 'hidden_on': 'Archivos ocultos visibles',
        'hidden_off': 'Archivos ocultos ocultos',
        'st_theme': 'Tema', 'st_lang': 'Idioma', 'st_number': 'Números de línea', 'st_wrap': 'Ajuste de línea',
        'st_syntax': 'Colores de sintaxis', 'on': 'SÍ', 'off': 'NO',
        'l_select': 'Elegir', 'l_open': 'Abrir', 'l_up': 'Carpeta superior', 'l_path': 'Ruta',
        'l_hidden': 'Ocultos', 'l_tab': 'Tab', 'l_back': 'Atrás', 'l_change': 'Cambiar', 'l_value': 'Valor',
        'l_file': 'Archivo', 'grp_view': 'VISTA', 'grp_code': 'ÁREA DE CÓDIGO', 'grp_edit': 'EDICIÓN', 'grp_app': 'APP',
        'lang_set': 'Idioma: {name}', 'list_empty': 'Aún no hay nada',
        'sp_code': 'Código +', 'tab_lang': 'LENGUAJE', 'mode_lang': 'CÓDIGO', 'l_new': 'Nuevo archivo',
        'box_install': 'Instalar', 'box_list': 'Cajas', 'box_pkg': 'Instalar paquete (.deb / .rpm)',
        'box_installed': 'instalada', 'box_none': 'Aún no hay cajas: primero N box > Instalar',
        'box_no_dbx': 'distrobox no está instalado: primero N box > Instalar',
        'box_nobox': 'No hay caja de la familia {fam} para {ext}: primero N box > Instalar',
        'box_nopkgs': 'No hay archivos .deb / .rpm aquí (explora carpetas)',
        'tab_pick': 'ELEGIR PAQUETE', 'l_install': 'Instalar', 'skipped': '(omitido)',
        'mode_job': 'INSTALAR', 'job_install': 'INSTALACIÓN', 'console': 'CONSOLA', 'job_pkg': 'Instalando {name}',
        'st_pkgs': 'Instalando dependencias (podman, distrobox)', 'st_update': 'Actualizando lista de paquetes',
        'st_create': 'Creando la caja ({name})', 'box_exists': '{name} ya existe, se omite',
        'st_dbx_dl': 'Descargando distrobox e instalándolo en ~/.local',
        'st_engine': 'Instalando motor de contenedores (podman)', 'st_check': 'Verificando (distrobox --version)',
        'st_boot': 'Preparando la caja', 'st_pkg': 'Instalando el paquete',
        'job_done': 'Listo', 'job_failed': 'Error: código de salida {code}', 'job_busy': 'Ya hay una tarea en curso',
        'box_missing': 'Primero crea una caja con N box > Instalar',
        'box_home': 'El paquete debe estar dentro de tu carpeta personal',
        'box_wrongfam': 'Este tipo de paquete no coincide con la distribución de la caja',
        'box_notpkg': 'Solo se pueden instalar .deb y .rpm',
        'l_pkg': 'Instalar en la caja',
    },
    'fr': {
        'subtitle': 'Éditeur de texte simple, rapide et minimaliste.',
        'start': 'Appuyez sur une touche pour commencer...',
        'key_new': 'Nouveau fichier', 'key_open': 'Ouvrir un fichier', 'key_save': 'Enregistrer',
        'key_find': 'Chercher', 'key_quit': 'Quitter', 'key_settings': 'Réglages (thème, langue)',
        'mode_insert': 'INSERTION', 'mode_search': 'RECHERCHE', 'mode_cmd': 'COMMANDE', 'mode_menu': 'RÉGLAGES',
        'l_save': 'Enregistrer', 'l_quit': 'Quitter', 'l_find': 'Chercher', 'l_goto': 'Aller à', 'l_search': 'Recherche',
        'noname': '[Nouveau]', 'loaded': '"{name}" {n} lignes   (? aide)',
        'written': '"{name}" écrit ({n} lignes)', 'matches': '{n} correspondances',
        'sp_new': 'Nouveau fichier', 'sp_open': 'Ouvrir un fichier', 'sp_find': 'Chercher',
        'sp_settings': 'Réglages', 'sp_quit': 'Quitter',
        'sp_hint': 'Flèches : choisir    Entrée : ouvrir    Tapez une lettre pour écrire',
        'tab_file': 'OUVRIR UN FICHIER', 'tab_settings': 'RÉGLAGES', 'title_settings': 'RÉGLAGES',
        'mode_open': 'FICHIERS', 'mode_settings': 'RÉGLAGES', 'dir': 'DOSSIER', 'empty_dir': 'Le dossier est vide',
        'cant_read': 'Lecture impossible : {path}', 'hidden_on': 'Fichiers cachés affichés',
        'hidden_off': 'Fichiers cachés masqués',
        'st_theme': 'Thème', 'st_lang': 'Langue', 'st_number': 'Numéros de ligne', 'st_wrap': 'Retour à la ligne',
        'st_syntax': 'Couleurs de syntaxe', 'on': 'OUI', 'off': 'NON',
        'l_select': 'Choisir', 'l_open': 'Ouvrir', 'l_up': 'Dossier parent', 'l_path': 'Chemin',
        'l_hidden': 'Cachés', 'l_tab': 'Tab', 'l_back': 'Retour', 'l_change': 'Changer', 'l_value': 'Valeur',
        'l_file': 'Fichier', 'grp_view': 'AFFICHAGE', 'grp_code': 'ZONE DE CODE', 'grp_edit': 'ÉDITION', 'grp_app': 'APPLI',
        'lang_set': 'Langue : {name}', 'list_empty': 'Rien pour le moment',
        'sp_code': 'Code +', 'tab_lang': 'LANGAGE', 'mode_lang': 'CODE', 'l_new': 'Nouveau fichier',
        'box_install': 'Installer', 'box_list': 'Boîtes', 'box_pkg': 'Installer un paquet (.deb / .rpm)',
        'box_installed': 'installée', 'box_none': 'Aucune boîte : d’abord N box > Installer',
        'box_no_dbx': 'distrobox n’est pas installé : d’abord N box > Installer',
        'box_nobox': 'Aucune boîte de la famille {fam} pour {ext} : d’abord N box > Installer',
        'box_nopkgs': 'Aucun fichier .deb / .rpm ici (parcourez les dossiers)',
        'tab_pick': 'CHOISIR UN PAQUET', 'l_install': 'Installer', 'skipped': '(ignoré)',
        'mode_job': 'INSTALL', 'job_install': 'INSTALLATION', 'console': 'CONSOLE', 'job_pkg': 'Installation de {name}',
        'st_pkgs': 'Installation des dépendances (podman, distrobox)', 'st_update': 'Mise à jour de la liste des paquets',
        'st_create': 'Création de la boîte ({name})', 'box_exists': '{name} existe déjà, ignorée',
        'st_dbx_dl': 'Téléchargement de distrobox et installation dans ~/.local',
        'st_engine': 'Installation du moteur de conteneurs (podman)', 'st_check': 'Vérification (distrobox --version)',
        'st_boot': 'Préparation de la boîte', 'st_pkg': 'Installation du paquet',
        'job_done': 'Terminé', 'job_failed': 'Erreur : code de sortie {code}', 'job_busy': 'Une tâche est déjà en cours',
        'box_missing': 'Créez d’abord une boîte avec N box > Installer',
        'box_home': 'Le paquet doit se trouver dans votre dossier personnel',
        'box_wrongfam': 'Ce type de paquet ne correspond pas à la distribution de la boîte',
        'box_notpkg': 'Seuls les fichiers .deb et .rpm peuvent être installés',
        'l_pkg': 'Installer dans la boîte',
    },
})


def cycle_lang(d=1):
    codes = [c for c in STR if c in LANG_NAMES]
    cur = codes.index(SETTINGS['lang']) if SETTINGS['lang'] in codes else 0
    SETTINGS['lang'] = codes[(cur + d) % len(codes)]


def t(key, **kw):
    table = STR.get(SETTINGS['lang'], STR['en'])
    s = table.get(key) or STR['en'].get(key) or STR['tr'].get(key) or key
    return s.format(**kw) if kw else s


HELP = {
    'tr': [
        'nview yardım',
        '',
        'Hareket   h j k l  w b e  ^ 0 $  { }  gg G 42G  H M L',
        '          Ctrl-d/u  Ctrl-f/b  Ctrl-e/y  zz zt zb  ma \'a',
        'Düzenle   i a I A  ekle (Esc: normal)      o O  satır ekle',
        '          x  dd 3dd  yy 3yy  p P  u geri al',
        'Arama     /desen  ?desen  n N  * #',
        'Dosya     Ctrl-s kaydet  Ctrl-o aç  Ctrl-n yeni  Ctrl-l yenile',
        'Kod       Ctrl-r veya F5 çalıştır  F6 çıktı  Ctrl-k satır sil  Ctrl-d satır kopyala',
        'Komut     :w :wq :q :q! :qa! :e dosya :e! :ls :bn :bp :N',
        '          :theme AD  :lang tr|en  :ayar  :redraw  :noh',
        '          :set nu rnu wrap ic hls syn cul  (no ile kapat, ! tersle)',
        '',
        'Herhangi bir tuşa basın: kapat',
    ],
    'en': [
        'nview help',
        '',
        'Motion    h j k l  w b e  ^ 0 $  { }  gg G 42G  H M L',
        '          Ctrl-d/u  Ctrl-f/b  Ctrl-e/y  zz zt zb  ma \'a',
        'Edit      i a I A  insert (Esc: normal)     o O  new line',
        '          x  dd 3dd  yy 3yy  p P  u undo',
        'Search    /pattern  ?pattern  n N  * #',
        'File      Ctrl-s save  Ctrl-o open  Ctrl-n new  Ctrl-l redraw',
        'Code      Ctrl-r or F5 run  F6 output  Ctrl-k delete line  Ctrl-d duplicate line',
        'Command   :w :wq :q :q! :qa! :e file :e! :ls :bn :bp :N',
        '          :theme NAME  :lang tr|en  :settings  :redraw  :noh',
        '          :set nu rnu wrap ic hls syn cul  (no to turn off, ! to toggle)',
        '',
        'Press any key to close',
    ],
}

# ------------------------------------------------------------------ açılış yazısı

_LETTERS = {
    'n': [r"_ __  ", r"| '_ \ ", r"| | | |", r"|_| |_|"],
    'v': [r"__   __", r"\ \ / /", r" \ V / ", r"  \_/  "],
    'i': [r" _ ", r"(_)", r"| |", r"|_|"],
    'e': [r"  ___ ", r" / _ \ ", r"|  __/", r" \___|"],
    'w': [r"__      __", r"\ \ /\ / /", r" \ V  V / ", r"  \_/\_/  "],
}
ART_RAW = [''.join(_LETTERS[c][r] for c in 'nview') for r in range(4)]
ART_W = max(len(r) for r in ART_RAW)
ART = [r.ljust(ART_W) for r in ART_RAW]

# ------------------------------------------------------------------ diller

C_KW = ('auto break case char const continue default do double else enum extern float '
        'for goto if inline int long register return short signed sizeof static struct '
        'switch typedef union unsigned void volatile while bool true false NULL')
CPP_KW = C_KW + (' class public private protected namespace template new delete this '
                 'try catch throw using virtual override nullptr')
JAVA_KW = ('abstract boolean break byte case catch char class continue default do double '
           'else enum extends final finally float for if implements import instanceof int '
           'interface long new package private protected public return short static super '
           'switch this throw throws try void while true false null var')
JS_KW = ('async await break case catch class const continue debugger default delete do '
         'else export extends finally for from function if import in instanceof let new of '
         'return static super switch this throw try typeof var void while with yield true '
         'false null undefined interface type enum implements readonly')
PY_KW = ('and as assert async await break class continue def del elif else except finally '
         'for from global if import in is lambda nonlocal not or pass raise return try while '
         'with yield True False None self')
RS_KW = ('as async await break const continue crate dyn else enum extern false fn for if '
         'impl in let loop match mod move mut pub ref return self Self static struct super '
         'trait true type unsafe use where while')
GO_KW = ('break case chan const continue default defer else fallthrough for func go goto '
         'if import interface map package range return select struct switch type var true '
         'false nil')
SH_KW = ('if then else elif fi case esac for while until do done in function select '
         'return exit local export readonly declare echo source')
SQL_KW = ('select from where insert into update delete create table drop alter join left '
          'right inner outer on group by order having limit values set and or not null as '
          'distinct union index primary key foreign references')

# (ad, yorum işareti, anahtar kelimeler, blok yorum var mı, büyük/küçük harf duyarsız mı)
LANG_TEXT = ('text', None, '', False, False)
LANGS = {
    'py': ('python', '#', PY_KW, False, False),
    'sh': ('sh', '#', SH_KW, False, False),
    'bash': ('sh', '#', SH_KW, False, False),
    'c': ('c', '//', C_KW, True, False),
    'h': ('c', '//', C_KW, True, False),
    'cpp': ('cpp', '//', CPP_KW, True, False),
    'cc': ('cpp', '//', CPP_KW, True, False),
    'hpp': ('cpp', '//', CPP_KW, True, False),
    'java': ('java', '//', JAVA_KW, True, False),
    'js': ('js', '//', JS_KW, True, False),
    'mjs': ('js', '//', JS_KW, True, False),
    'jsx': ('js', '//', JS_KW, True, False),
    'ts': ('ts', '//', JS_KW, True, False),
    'tsx': ('ts', '//', JS_KW, True, False),
    'rs': ('rust', '//', RS_KW, True, False),
    'go': ('go', '//', GO_KW, True, False),
    'sql': ('sql', '--', SQL_KW, True, True),
    'json': ('json', None, 'true false null', False, False),
    'yml': ('yaml', '#', 'true false null yes no on off', False, False),
    'yaml': ('yaml', '#', 'true false null yes no on off', False, False),
    'toml': ('conf', '#', 'true false', False, False),
    'ini': ('conf', '#', 'true false', False, False),
    'conf': ('conf', '#', '', False, False),
    'md': ('markdown', None, '', False, False),
    'markdown': ('markdown', None, '', False, False),
    'html': ('html', None, '', False, False),
    'htm': ('html', None, '', False, False),
    'xml': ('html', None, '', False, False),
    'css': ('css', None, '', True, False),
    'txt': LANG_TEXT,
    'log': LANG_TEXT,
}
NAME_LANGS = {
    'Makefile': ('make', '#', '', False, False),
}

KIND_ALIAS = {'bcom': 'com', 'tag': 'kw'}
WORD_RE = re.compile(r'\w+|[^\w\s]+')


def pick_lang(path):
    if not path:
        return LANG_TEXT
    base = os.path.basename(path)
    if base in NAME_LANGS:
        return NAME_LANGS[base]
    ext = base.rsplit('.', 1)[-1].lower() if '.' in base else ''
    return LANGS.get(ext, LANG_TEXT)


def make_rule(lang):
    name, cm, kw, block, icase = lang
    parts = []
    if name == 'html':
        parts.append(r'(?P<com><!--.*?(?:-->|$))')
        parts.append(r'(?P<tag></?[A-Za-z][^>]*>)')
    parts.append(r'(?P<str>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')')
    if block:
        parts.append(r'(?P<bcom>/\*.*?(?:\*/|$))')
    if cm:
        parts.append(r'(?P<com>' + re.escape(cm) + r'.*)')
    if kw:
        parts.append(r'(?P<kw>\b(?:' + '|'.join(map(re.escape, kw.split())) + r')\b)')
    parts.append(r'(?P<url>https?://[^\s"\'<>]+)')
    parts.append(r'(?P<num>\b(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?)\b)')
    return re.compile('|'.join(parts), re.I if icase else 0)


# ------------------------------------------------------------------ temalar

THEMES = {
    'neon-mor': {
        'label': 'Neon Mor', 'text': 252, 'str': 114, 'com': 244, 'kw': 176, 'num': 215,
        'url': 75, 'head': 141, 'fence': 180, 'ln': 240, 'lncur': 221, 'tilde': 27,
        'accent': 141, 'curbg': 53, 'bar': 234, 'srch': 220,
    },
    'mor-tonlar': {
        'label': 'Mor Tonlar', 'text': 183, 'str': 146, 'com': 97, 'kw': 140, 'num': 176,
        'url': 110, 'head': 135, 'fence': 139, 'ln': 60, 'lncur': 183, 'tilde': 54,
        'accent': 98, 'curbg': 54, 'bar': 234, 'srch': 176,
    },
    'okyanus': {
        'label': 'Okyanus', 'text': 153, 'str': 116, 'com': 66, 'kw': 81, 'num': 216,
        'url': 75, 'head': 39, 'fence': 109, 'ln': 60, 'lncur': 117, 'tilde': 24,
        'accent': 39, 'curbg': 17, 'bar': 234, 'srch': 220,
    },
    'orman': {
        'label': 'Orman', 'text': 194, 'str': 150, 'com': 65, 'kw': 114, 'num': 222,
        'url': 79, 'head': 71, 'fence': 143, 'ln': 59, 'lncur': 150, 'tilde': 22,
        'accent': 71, 'curbg': 22, 'bar': 234, 'srch': 220,
    },
    'vscode': {
        'label': 'VS Code Dark', 'text': 252, 'str': 180, 'com': 65, 'kw': 75, 'num': 151,
        'url': 75, 'head': 75, 'fence': 108, 'ln': 240, 'lncur': 252, 'tilde': 238,
        'accent': 117, 'curbg': 236, 'bar': 24, 'srch': 178,
    },
    'dracula': {
        'label': 'Dracula', 'text': 253, 'str': 228, 'com': 61, 'kw': 212, 'num': 141,
        'url': 117, 'head': 141, 'fence': 84, 'ln': 60, 'lncur': 228, 'tilde': 61,
        'accent': 212, 'curbg': 236, 'bar': 235, 'srch': 215,
    },
    'monokai': {
        'label': 'Monokai', 'text': 252, 'str': 186, 'com': 242, 'kw': 197, 'num': 141,
        'url': 81, 'head': 148, 'fence': 208, 'ln': 240, 'lncur': 186, 'tilde': 238,
        'accent': 148, 'curbg': 237, 'bar': 235, 'srch': 208,
    },
    'nord': {
        'label': 'Nord', 'text': 189, 'str': 150, 'com': 103, 'kw': 110, 'num': 139,
        'url': 110, 'head': 109, 'fence': 152, 'ln': 60, 'lncur': 153, 'tilde': 60,
        'accent': 110, 'curbg': 236, 'bar': 235, 'srch': 222,
    },
    'gunes': {
        'label': 'Güneş', 'text': 246, 'str': 37, 'com': 240, 'kw': 136, 'num': 166,
        'url': 33, 'head': 136, 'fence': 64, 'ln': 240, 'lncur': 254, 'tilde': 235,
        'accent': 136, 'curbg': 235, 'bar': 234, 'srch': 166,
    },
    'gece-mavisi': {
        'label': 'Gece Mavisi', 'text': 146, 'str': 150, 'com': 60, 'kw': 141, 'num': 215,
        'url': 111, 'head': 111, 'fence': 73, 'ln': 60, 'lncur': 146, 'tilde': 60,
        'accent': 111, 'curbg': 236, 'bar': 234, 'srch': 215,
    },
    'kiraz': {
        'label': 'Kiraz', 'text': 224, 'str': 186, 'com': 138, 'kw': 204, 'num': 215,
        'url': 211, 'head': 204, 'fence': 175, 'ln': 95, 'lncur': 224, 'tilde': 52,
        'accent': 204, 'curbg': 52, 'bar': 233, 'srch': 220,
    },
}

# 8 renkli terminal için yedek: (renk, nitelik)
FB = {
    'text': (7, 0), 'str': (2, 0), 'com': (7, curses.A_DIM), 'kw': (5, curses.A_BOLD),
    'num': (3, 0), 'url': (4, curses.A_UNDERLINE), 'head': (5, curses.A_BOLD),
    'fence': (3, 0), 'ln': (7, curses.A_DIM), 'lncur': (3, curses.A_BOLD),
    'tilde': (4, curses.A_BOLD), 'accent': (5, curses.A_BOLD),
}
ANSI_EXTRA = {'com': '2', 'ln': '2', 'kw': '1', 'head': '1', 'lncur': '1',
              'tilde': '1', 'accent': '1', 'url': '4'}


class Colors:
    def __init__(self, ok=False, big=False):
        self.ok = ok
        self.big = ok and big
        self.cache = {}

    def theme(self):
        return THEMES[SETTINGS['theme']]

    def reset(self):
        self.cache = {}

    def pair(self, fg, bg=-1):
        if not self.ok:
            return 0
        key = (fg, bg)
        if key not in self.cache:
            n = len(self.cache) + 1
            if n >= curses.COLOR_PAIRS:
                return 0
            curses.init_pair(n, fg, bg)
            self.cache[key] = n
        return curses.color_pair(self.cache[key])

    def style(self, name, bg=-1):
        fb = FB.get(name, FB['text'])
        fg = self.theme().get(name, self.theme()['text']) if self.big else fb[0]
        return self.pair(fg, bg) | fb[1]

    def cursor_bg(self):
        return self.theme()['curbg'] if self.big else -1

    def on_bar(self, name, bold=False):
        """Durum çubuğu (koyu zemin) üzerinde metin niteliği."""
        if self.big:
            return self.pair(self.theme()[name], self.theme()['bar']) | (curses.A_BOLD if bold else 0)
        return curses.A_REVERSE | (curses.A_BOLD if bold else 0)

    def accent_cell(self):
        """Mod etiketi hücresi (mor zemin, koyu yazı)."""
        if self.big:
            return self.pair(16, self.theme()['accent']) | curses.A_BOLD
        return curses.A_REVERSE | curses.A_BOLD

    def search_attr(self):
        fg, bg = (16, self.theme()['srch']) if self.big else (0, 3)
        return self.pair(fg, bg) | curses.A_BOLD


def ansi(name):
    th = THEMES[SETTINGS['theme']]
    codes = [c for c in (ANSI_EXTRA.get(name),) if c]
    codes.append('38;5;%d' % th.get(name, th['text']))
    return '\x1b[' + ';'.join(codes) + 'm'


RESET = '\x1b[0m'


# ------------------------------------------------------------------ buffer

class Buffer:
    UNDO_MAX = 200

    def __init__(self, path=None):
        self.path = None
        self.name = None
        self.lang = LANG_TEXT
        self.rule = make_rule(self.lang)
        self.binary = False
        self.modified = False
        self.is_new = False
        self.lines = ['']
        self.cur = self.cc = self.top = self.left = 0
        self.marks = {}
        self.undo = []
        self._spans = {}
        if path:
            self.path = path
            self.name = os.path.basename(path)
            self.lang = pick_lang(path)
            self.rule = make_rule(self.lang)
            if os.path.exists(path):
                self.load()
            else:
                self.is_new = True
        self.base_words = self.word_count()

    def word_count(self):
        return sum(len(l.split()) for l in self.lines)

    def bufname(self):
        return self.name or t('noname')

    def load(self):
        with open(self.path, 'rb') as f:
            data = f.read()
        self.binary = b'\0' in data[:8192]
        self.set_text(data.decode('utf-8', errors='replace'))
        self.modified = False
        self.undo = []
        record_recent(self.path)

    def set_text(self, text):
        self.lines = [l.rstrip('\r').replace('\t', '    ') for l in text.split('\n')]
        if text.endswith('\n'):
            self.lines.pop()
        if not self.lines:
            self.lines = ['']
        self._spans = {}

    def save(self, target=None, final_nl=True):
        target = os.path.expanduser(target or self.path)
        text = '\n'.join(self.lines) + ('\n' if final_nl else '')
        with open(target, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        self.path = target
        self.name = os.path.basename(target)
        self.lang = pick_lang(target)
        self.rule = make_rule(self.lang)
        self.is_new = False
        self.modified = False
        self._spans = {}
        return len(self.lines)

    def spans(self, i):
        if i not in self._spans:
            line = self.lines[i]
            if self.lang[0] == 'markdown' and line[:1] in ('#', '`', '>'):
                kind = {'#': 'head', '`': 'fence', '>': 'com'}[line[0]]
                res = [(0, len(line), kind)]
            else:
                res = [(m.start(), m.end(), KIND_ALIAS.get(m.lastgroup, m.lastgroup))
                       for m in self.rule.finditer(line)]
            self._spans[i] = res
        return self._spans[i]

    def rowcount(self, i, textw, wrap):
        if not wrap:
            return 1
        n = len(self.lines[i]) + 1
        return max(1, -(-n // textw))

    # ---- düzenleme ilkelleri

    def touch(self):
        self.modified = True
        self._spans = {}

    def snapshot(self):
        self.undo.append((list(self.lines), self.cur, self.cc))
        if len(self.undo) > self.UNDO_MAX:
            del self.undo[0]

    def undo_pop(self):
        if not self.undo:
            return False
        self.lines, self.cur, self.cc = self.undo.pop()
        self.touch()
        return True

    def insert_text(self, s):
        line = self.lines[self.cur]
        self.lines[self.cur] = line[:self.cc] + s + line[self.cc:]
        self.cc += len(s)
        self.touch()

    def split_line(self):
        line = self.lines[self.cur]
        self.lines[self.cur] = line[:self.cc]
        self.lines.insert(self.cur + 1, line[self.cc:])
        self.cur += 1
        self.cc = 0
        self.touch()

    def backspace(self):
        if self.cc > 0:
            line = self.lines[self.cur]
            self.lines[self.cur] = line[:self.cc - 1] + line[self.cc:]
            self.cc -= 1
        elif self.cur > 0:
            prev = self.lines[self.cur - 1]
            self.cc = len(prev)
            self.lines[self.cur - 1] = prev + self.lines[self.cur]
            del self.lines[self.cur]
            self.cur -= 1
        else:
            return
        self.touch()

    def delete_char(self, n):
        line = self.lines[self.cur]
        if line:
            self.lines[self.cur] = line[:self.cc] + line[self.cc + n:]
            self.touch()

    def delete_lines(self, n):
        chunk = self.lines[self.cur:self.cur + n]
        del self.lines[self.cur:self.cur + n]
        if not self.lines:
            self.lines = ['']
        self.cur = min(self.cur, len(self.lines) - 1)
        self.touch()
        return chunk

    def open_line(self, below):
        at = self.cur + 1 if below else self.cur
        self.lines.insert(at, '')
        self.cur = at
        self.cc = 0
        self.touch()


# ------------------------------------------------------------------ uygulama

TR_MAP = str.maketrans('ÇÖÜŞĞİ', 'COUSGI')
BIG = {
    'A': '010101111101101', 'B': '110101110101110', 'C': '011100100100011',
    'D': '110101101101110', 'E': '111100110100111', 'F': '111100110100100',
    'G': '011100101101011', 'H': '101101111101101', 'I': '111010010010111',
    'J': '001001001101010', 'K': '101101110101101', 'L': '100100100100111',
    'M': '101111111101101', 'N': '101111111111101', 'O': '010101101101010',
    'P': '110101110100100', 'Q': '010101101111011', 'R': '110101110101101',
    'S': '011100010001110', 'T': '111010010010010', 'U': '101101101101111',
    'V': '101101101101010', 'W': '101101111111101', 'X': '101101010101101',
    'Y': '101101010010010', 'Z': '111001010100111',
    '0': '111101101101111', '1': '010110010010111', '2': '110001010100111',
    '3': '110001010001110', '4': '101101111001001', '5': '111100110001110',
    '6': '011100111101111', '7': '111001010010010', '8': '111101111101111',
    '9': '111101111001110',
    ':': '000010000010000', '.': '000000000000010', '-': '000000111000000',
    '/': '001001010100100', '>': '100010001010100', '_': '000000000000111',
    ' ': '000000000000000',
}


def big_lines(text):
    rows = [''] * 5
    for ch in text.upper().translate(TR_MAP):
        bits = BIG.get(ch, BIG[' '])
        for r in range(5):
            row = bits[r * 3:r * 3 + 3]
            rows[r] += ''.join('██' if b == '1' else '  ' for b in row) + '  '
    return [r.rstrip() for r in rows]


# Logo: lowercase pixel "nview" plus a blinking cursor block (same as the icon and website)
_LOGO = {
    'n': ['XXX.', 'X..X', 'X..X', 'X..X', 'X..X'],
    'v': ['X..X', 'X..X', 'X..X', 'X..X', '.XX.'],
    'i': ['X', '.', 'X', 'X', 'X'],
    'e': ['.XX.', 'X..X', 'XXXX', 'X...', '.XXX'],
    'w': ['X...X', 'X...X', 'X.X.X', 'X.X.X', '.X.X.'],
}


def logo_rows():
    rows = [''] * 5
    for ch in 'nview':
        for r in range(5):
            rows[r] += ''.join('██' if c == 'X' else '  ' for c in _LOGO[ch][r]) + '  '
    return rows


ART = logo_rows()
ART_TXT_W = len(ART[0])
ART_CUR_W = 4
ART_W = ART_TXT_W + ART_CUR_W


def human(n):
    x = float(n)
    for u in ('B', 'K', 'M', 'G'):
        if x < 1024 or u == 'G':
            return f'{x:.0f}{u}' if u == 'B' else f'{x:.1f}{u}'
        x /= 1024


def find_bracket(b):
    """İmlecin yanındaki parantezi ve karşılığını döndürür: ((l, c), eş) ya da None."""
    line = b.lines[b.cur]
    for pos in (b.cc, b.cc - 1):
        if 0 <= pos < len(line) and (line[pos] in PAIRS or line[pos] in RPAIRS):
            return (b.cur, pos), _scan_pair(b, b.cur, pos)
    return None


def _scan_pair(b, li, ci):
    ch = b.lines[li][ci]
    if ch in PAIRS:
        target, step = PAIRS[ch], 1
    else:
        target, step = RPAIRS[ch], -1
    depth = 0
    l, c = li, ci
    budget = 20000
    while 0 <= l < len(b.lines) and budget > 0:
        line = b.lines[l]
        while 0 <= c < len(line) and budget > 0:
            x = line[c]
            if x == ch:
                depth += 1
            elif x == target:
                depth -= 1
                if depth == 0:
                    return (l, c)
            c += step
            budget -= 1
        l += step
        if 0 <= l < len(b.lines):
            c = 0 if step == 1 else len(b.lines[l]) - 1
    return None


def para_bounds(b):
    """İmlecin bulunduğu boş satırla ayrılmış paragrafın sınırları."""
    lines = b.lines
    c = b.cur
    if not lines[c].strip():
        return c, c
    s = c
    while s > 0 and lines[s - 1].strip():
        s -= 1
    e = c
    while e < len(lines) - 1 and lines[e + 1].strip():
        e += 1
    return s, e


def snap_dir(path):
    key = hashlib.sha1(os.path.abspath(path).encode('utf-8')).hexdigest()[:16]
    return os.path.join(STATE_DIR, key)


def take_snapshot(path, text):
    d = snap_dir(path)
    os.makedirs(d, exist_ok=True)
    files = sorted(os.listdir(d))
    if files:
        with open(os.path.join(d, files[-1]), encoding='utf-8') as f:
            if f.read() == text:
                return False
    ms = int(time.time() * 1000)
    while os.path.exists(os.path.join(d, f'{ms:015d}.txt')):
        ms += 1
    name = f'{ms:015d}.txt'
    with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
        f.write(text)
    files.append(name)
    for old in files[:-MAX_SNAPS]:
        os.remove(os.path.join(d, old))
    return True


def list_snapshots(path):
    """En yeni önce: (dosya, zaman, satır sayısı, önceki sürüme göre fark)."""
    d = snap_dir(path)
    try:
        files = sorted(os.listdir(d))
    except OSError:
        return []
    out = []
    prev = 0
    for name in files:
        try:
            with open(os.path.join(d, name), encoding='utf-8') as f:
                n = f.read().count('\n')
        except OSError:
            continue
        ms = int(name[:-4])
        stamp = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(ms / 1000))
        out.append((os.path.join(d, name), stamp, n, n - prev))
        prev = n
    out.reverse()
    return out


LANG_CATALOG = {
    'python': {'label': 'Python', 'ext': '.py', 'template': '#!/usr/bin/env python3\n\n\ndef main():\n    print("Merhaba, nview!")\n\n\nif __name__ == "__main__":\n    main()\n'},
    'javascript': {'label': 'JavaScript', 'ext': '.js', 'template': 'console.log("Merhaba, nview!");\n'},
    'typescript': {'label': 'TypeScript', 'ext': '.ts', 'template': 'const mesaj: string = "Merhaba, nview!";\nconsole.log(mesaj);\n'},
    'c': {'label': 'C', 'ext': '.c', 'template': '#include <stdio.h>\n\nint main(void) {\n    printf("Merhaba, nview!\\n");\n    return 0;\n}\n'},
    'cpp': {'label': 'C++', 'ext': '.cpp', 'template': '#include <iostream>\n\nint main() {\n    std::cout << "Merhaba, nview!" << std::endl;\n}\n'},
    'java': {'label': 'Java', 'ext': '.java', 'template': 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Merhaba, nview!");\n    }\n}\n'},
    'go': {'label': 'Go', 'ext': '.go', 'template': 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Merhaba, nview!")\n}\n'},
    'rust': {'label': 'Rust', 'ext': '.rs', 'template': 'fn main() {\n    println!("Merhaba, nview!");\n}\n'},
    'bash': {'label': 'Bash', 'ext': '.sh', 'template': '#!/usr/bin/env bash\n\necho "Merhaba, nview!"\n'},
    'sql': {'label': 'SQL', 'ext': '.sql', 'template': 'SELECT 1;\n'},
    'html': {'label': 'HTML', 'ext': '.html', 'template': '<!doctype html>\n<html>\n<body>\n  <h1>Merhaba, nview!</h1>\n</body>\n</html>\n'},
    'markdown': {'label': 'Markdown', 'ext': '.md', 'template': '# Başlık\n\n'},
    'json': {'label': 'JSON', 'ext': '.json', 'template': '{\n  "mesaj": "Merhaba, nview!"\n}\n'},
    'text': {'label': 'Düz metin', 'ext': '.txt', 'template': ''},
}


def run_argv(lang, path):
    """Dile göre çalıştırma komutu. Desteklenmiyorsa None."""
    d = os.path.dirname(os.path.abspath(path))
    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    q = shlex.quote
    out = os.path.join(tempfile.gettempdir(), 'nview_run_' + stem)
    if lang == 'python':
        return ['python3', path]
    if lang == 'js':
        return ['node', path]
    if lang == 'sh':
        return ['bash', path]
    if lang == 'go':
        return ['go', 'run', path]
    if lang == 'c':
        return ['sh', '-c', f'cc -o {q(out)} {q(path)} && {q(out)}']
    if lang == 'cpp':
        return ['sh', '-c', f'c++ -o {q(out)} {q(path)} && {q(out)}']
    if lang == 'rust':
        return ['sh', '-c', f'rustc -o {q(out)} {q(path)} && {q(out)}']
    if lang == 'java':
        return ['sh', '-c', f'cd {q(d)} && javac {q(name)} && java {q(stem)}']
    return None


BOX_NAME = 'nbox'
DBX_URL = 'https://raw.githubusercontent.com/89luca89/distrobox/main/install'
LOCAL_BIN = os.path.join(os.path.expanduser('~'), '.local', 'bin')


def job_env():
    env = dict(os.environ)
    env['PATH'] = LOCAL_BIN + os.pathsep + env.get('PATH', '')
    return env


def dbx_download_argv():
    """distrobox resmi kurulum betiğini dosyaya indirir, sonra ~/.local altına kurar."""
    q = shlex.quote
    tmp = os.path.join(tempfile.gettempdir(), 'nview-distrobox-install.sh')
    prefix = os.path.join(os.path.expanduser('~'), '.local')
    script = (
        'set -e; '
        f'if command -v curl >/dev/null 2>&1; then curl -fsSL {q(DBX_URL)} -o {q(tmp)}; '
        f'else wget -q {q(DBX_URL)} -O {q(tmp)}; fi; '
        f'sh {q(tmp)} --prefix {q(prefix)}'
    )
    return ['sh', '-c', script]


BOX_KINDS = ('boxmenu', 'boxdistro', 'boxlist')
BOX_DISTROS = {
    'fedora': ('Fedora', 'fedora:latest', 'fedora'),
    'ubuntu': ('Ubuntu 24.04', 'ubuntu:24.04', 'debian'),
    'debian': ('Debian 12', 'debian:12', 'debian'),
    'arch': ('Arch Linux', 'archlinux:latest', 'arch'),
}


SIDEW = 26
PLAYGROUND = os.environ.get('NVIEW_PLAYGROUND') or os.path.join(os.path.expanduser('~'), 'nview-playground')


def in_playground(path):
    if not path:
        return False
    full = os.path.abspath(path)
    return full == PLAYGROUND or full.startswith(PLAYGROUND + os.sep)

LANG_LABEL = {'js': 'JavaScript', 'ts': 'TypeScript', 'cpp': 'C++', 'c': 'C', 'python': 'Python', 'sh': 'Shell',
              'rust': 'Rust', 'go': 'Go', 'java': 'Java', 'json': 'JSON', 'yaml': 'YAML', 'html': 'HTML',
              'css': 'CSS', 'markdown': 'Markdown', 'sql': 'SQL', 'conf': 'Config', 'text': 'Text'}
SYMBOL_RES = [re.compile(r'^\s*(?:async\s+def|def|class|function|func|fn|sub)\s+([A-Za-z_]\w*)'),
              re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:function|\()')]


def git_branch(path):
    d = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()
    for _ in range(12):
        try:
            with open(os.path.join(d, '.git', 'HEAD'), encoding='utf-8') as f:
                head = f.read().strip()
            return head.split('/')[-1] if head.startswith('ref:') else head[:7]
        except OSError:
            pass
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def diagnostics(b):
    """(errors, warnings, first_error_line). Errors: Python/JSON syntax. Warnings: trailing spaces."""
    key = (len(b.lines), b.cur, b.cc, b.lines[b.cur] if b.lines else '')
    c = getattr(b, '_diag', None)
    if c and c[0] == key:
        return c[1]
    errs, line = 0, None
    name = b.lang[0]
    text = '\n'.join(b.lines)
    if text.strip():
        if name == 'python':
            try:
                compile(text + '\n', b.name or '<buffer>', 'exec')
            except SyntaxError as e:
                errs, line = 1, e.lineno
            except (ValueError, RecursionError, MemoryError):
                pass
        elif name == 'json':
            try:
                json.loads(text)
            except ValueError as e:
                errs, line = 1, getattr(e, 'lineno', None)
    warns = sum(1 for l in b.lines[:5000] if l != l.rstrip())
    res = (errs, warns, line)
    b._diag = (key, res)
    return res


def current_symbol(b):
    for i in range(min(b.cur, len(b.lines) - 1), max(-1, b.cur - 400), -1):
        for rx in SYMBOL_RES:
            m = rx.match(b.lines[i])
            if m:
                return m.group(1)
    return None


PKG_EXT = {'debian': '.deb', 'fedora': '.rpm'}


def box_name_for(key):
    return 'nbox-' + key


def family_of(image):
    low = image.lower()
    if 'fedora' in low:
        return 'fedora'
    if 'ubuntu' in low or 'debian' in low:
        return 'debian'
    if 'arch' in low:
        return 'arch'
    return None


def list_boxes():
    """Returns None if distrobox is missing, otherwise a list of existing boxes."""
    exe = shutil.which('distrobox', path=job_env()['PATH'])
    if not exe:
        return None
    try:
        out = subprocess.run([exe, 'list', '--no-color'], capture_output=True, text=True,
                             timeout=20, env=job_env()).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    boxes = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4 or parts[0].upper() == 'ID':
            continue
        boxes.append({'name': parts[1], 'status': parts[2], 'image': parts[3],
                      'family': family_of(parts[3])})
    return boxes


def detect_pm():
    for binary, name in (('dnf', 'dnf'), ('apt-get', 'apt'), ('pacman', 'pacman'), ('zypper', 'zypper')):
        if shutil.which(binary):
            return name
    return None


# ====================================================================== extras (0.5 command pack)
# Every command below is registered with @xcmd / @lt and is listed by :commands and :features.
# Line commands accept a range: :%sort  :3,9upper  :.,$indent 4  (default: whole buffer).

XCMDS = {}
XCATS = {'edit': 'Editing', 'code': 'Code', 'view': 'View', 'file': 'Files and project', 'info': 'Info'}


def xcmd(names, doc, cat):
    def deco(fn):
        ns = names.split()
        for n in ns:
            XCMDS[n] = {'fn': fn, 'doc': doc, 'cat': cat, 'name': ns[0]}
        return fn
    return deco


def lt(names, doc, cat='edit'):
    """Register a pure line transform: fn(lines, arg) -> new lines."""
    def deco(fn):
        def run(app, rng, arg):
            a, b = rng
            old = app.b.lines[a:b + 1]
            new = fn(old, arg)
            app.xapply(a, b, new)
            return f'{names.split()[0]}: {len(old)} -> {len(new)} lines'
        xcmd(names, doc, cat)(run)
        return fn
    return deco


def _n(arg, default):
    m = re.search(r'-?\d+', arg or '')
    return int(m.group(0)) if m else default


def _words(s):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    return [w for w in re.split(r'[^A-Za-z0-9]+', s) if w]


def _idents(fn):
    return lambda lines, arg: [re.sub(r'[A-Za-z_][A-Za-z0-9_\-]*', lambda m: fn(_words(m.group(0))) or m.group(0), l) for l in lines]


# ---------------------------------------------------------------- editing: sorting and order
lt('sort', 'Sort lines A-Z')(lambda L, a: sorted(L))
lt('sortr sort!', 'Sort lines Z-A')(lambda L, a: sorted(L, reverse=True))
lt('sorti', 'Sort lines ignoring case')(lambda L, a: sorted(L, key=str.lower))
lt('sortlen', 'Sort lines by length')(lambda L, a: sorted(L, key=len))
lt('sortn', 'Sort lines by the first number in them')(
    lambda L, a: sorted(L, key=lambda l: float((re.search(r'-?\d+(?:\.\d+)?', l) or [0])[0]) if re.search(r'-?\d+', l) else 0.0))
lt('uniq', 'Remove adjacent duplicate lines')(
    lambda L, a: [l for i, l in enumerate(L) if i == 0 or l != L[i - 1]])
lt('dedupe', 'Remove all duplicate lines (keep first)')(
    lambda L, a: list(dict.fromkeys(L)))
lt('reverse rev', 'Reverse the order of lines')(lambda L, a: L[::-1])
lt('shuffle', 'Shuffle lines randomly')(lambda L, a: random.sample(L, len(L)))
lt('sortwords', 'Sort the words inside each line')(lambda L, a: [' '.join(sorted(l.split())) for l in L])
lt('revwords', 'Reverse the words inside each line')(lambda L, a: [' '.join(l.split()[::-1]) for l in L])
lt('filter keep', 'Keep only lines matching a regex')(lambda L, a: [l for l in L if re.search(a, l)] or [''])
lt('reject drop', 'Remove lines matching a regex')(lambda L, a: [l for l in L if not re.search(a, l)] or [''])

# ---------------------------------------------------------------- editing: case
lt('upper', 'UPPERCASE lines')(lambda L, a: [l.upper() for l in L])
lt('lower', 'lowercase lines')(lambda L, a: [l.lower() for l in L])
lt('title', 'Title Case lines')(lambda L, a: [l.title() for l in L])
lt('swapcase', 'sWAP cASE')(lambda L, a: [l.swapcase() for l in L])
lt('capitalize', 'Capitalize the first letter of each line')(lambda L, a: [l[:1].upper() + l[1:] for l in L])
lt('camel', 'Convert identifiers to camelCase')(_idents(lambda w: w[0].lower() + ''.join(x.title() for x in w[1:]) if w else None))
lt('pascal', 'Convert identifiers to PascalCase')(_idents(lambda w: ''.join(x.title() for x in w) if w else None))
lt('snake', 'Convert identifiers to snake_case')(_idents(lambda w: '_'.join(x.lower() for x in w) if w else None))
lt('kebab', 'Convert identifiers to kebab-case')(_idents(lambda w: '-'.join(x.lower() for x in w) if w else None))
lt('constant', 'Convert identifiers to UPPER_SNAKE')(_idents(lambda w: '_'.join(x.upper() for x in w) if w else None))

# ---------------------------------------------------------------- editing: whitespace and layout
lt('trim', 'Remove trailing spaces')(lambda L, a: [l.rstrip() for l in L])
lt('trimall', 'Remove spaces at both ends')(lambda L, a: [l.strip() for l in L])
lt('trimleft', 'Remove leading spaces')(lambda L, a: [l.lstrip() for l in L])
lt('squeeze', 'Collapse runs of blank lines into one')(
    lambda L, a: [l for i, l in enumerate(L) if l.strip() or i == 0 or L[i - 1].strip()])
lt('delblank', 'Delete blank lines')(lambda L, a: [l for l in L if l.strip()] or [''])
lt('join', 'Join all lines into one (space separated)')(lambda L, a: [' '.join(l.strip() for l in L)])
lt('dup', 'Duplicate the lines')(lambda L, a: L + L)
lt('indent', 'Indent lines (default 4 spaces)')(lambda L, a: [' ' * _n(a, 4) + l if l.strip() else l for l in L])
lt('dedent', 'Remove up to N leading spaces (default 4)')(
    lambda L, a: [l[min(_n(a, 4), len(l) - len(l.lstrip())):] for l in L])
lt('center', 'Center lines in a width (default 80)')(lambda L, a: [l.strip().center(_n(a, 80)).rstrip() for l in L])
lt('right', 'Right-align lines in a width (default 80)')(lambda L, a: [l.strip().rjust(_n(a, 80)) for l in L])
lt('wrap', 'Hard-wrap long lines at a width (default 72)')(
    lambda L, a: [seg for l in L for seg in (textwrap.wrap(l, _n(a, 72)) or [''])])
lt('unwrap', 'Join paragraphs into single lines')(
    lambda L, a: [' '.join(p.split()) for p in re.split(r'\n\s*\n', '\n'.join(L))] if any(L) else L)
lt('align', 'Align lines on a separator (default =)')(
    lambda L, a: (lambda sep: [(l.split(sep, 1)[0].rstrip().ljust(max(len(x.split(sep, 1)[0].rstrip()) for x in L if sep in x) + 1)
                                + sep + l.split(sep, 1)[1]) if sep in l else l for l in L])(a or '='))
lt('splitat', 'Split every line at a delimiter into several lines')(
    lambda L, a: [part for l in L for part in (l.split(a) if a else [l])])
lt('commas', 'Join lines with commas')(lambda L, a: [', '.join(l.strip() for l in L)])

# ---------------------------------------------------------------- editing: prefixes
lt('number', 'Prefix lines with 1. 2. 3.')(lambda L, a: [f'{i + 1}. {l}' for i, l in enumerate(L)])
lt('unnumber', 'Remove 1. 2. 3. prefixes')(lambda L, a: [re.sub(r'^\s*\d+[.)]\s?', '', l) for l in L])
lt('nl', 'Prefix lines with zero-padded numbers')(lambda L, a: [f'{i + 1:0{len(str(len(L)))}d}  {l}' for i, l in enumerate(L)])
lt('bullet', 'Prefix lines with "- "')(lambda L, a: ['- ' + l if l.strip() else l for l in L])
lt('unbullet', 'Remove "- " or "* " prefixes')(lambda L, a: [re.sub(r'^(\s*)[-*+]\s', r'\1', l) for l in L])
lt('quote', 'Prefix lines with "> "')(lambda L, a: ['> ' + l for l in L])
lt('unquote', 'Remove "> " prefixes')(lambda L, a: [re.sub(r'^>\s?', '', l) for l in L])
lt('prefix', 'Add text at the start of every line')(lambda L, a: [a + l for l in L])
lt('suffix', 'Add text at the end of every line')(lambda L, a: [l + a for l in L])
lt('surround', 'Surround every line with a character (default ")')(
    lambda L, a: [(a or '"') + l + {'(': ')', '[': ']', '{': '}', '<': '>'}.get((a or '"')[0], a or '"') for l in L])
lt('incr', 'Add N (default 1) to every number')(
    lambda L, a: [re.sub(r'-?\d+', lambda m: str(int(m.group(0)) + _n(a, 1)), l) for l in L])

# ---------------------------------------------------------------- editing: encodings
lt('base64enc', 'Base64-encode each line')(lambda L, a: [base64.b64encode(l.encode()).decode() for l in L])
lt('base64dec', 'Base64-decode each line')(lambda L, a: [base64.b64decode(l.encode()).decode('utf-8', 'replace') for l in L])
lt('urlenc', 'URL-encode each line')(lambda L, a: [urllib.parse.quote(l, safe='') for l in L])
lt('urldec', 'URL-decode each line')(lambda L, a: [urllib.parse.unquote(l) for l in L])
lt('htmlesc', 'Escape HTML characters')(lambda L, a: [html.escape(l) for l in L])
lt('htmlunesc', 'Unescape HTML entities')(lambda L, a: [html.unescape(l) for l in L])
lt('rot13', 'ROT13 each line')(lambda L, a: [codecs.encode(l, 'rot13') for l in L])
lt('hexenc', 'Hex-encode each line')(lambda L, a: [l.encode().hex() for l in L])
lt('hexdec', 'Hex-decode each line')(lambda L, a: [bytes.fromhex(l.strip()).decode('utf-8', 'replace') for l in L])


def _json_lines(L, indent, sort=False):
    data = json.loads('\n'.join(L))
    if indent is None:
        return [json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=sort)]
    return json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=sort).split('\n')


lt('json', 'Pretty-print JSON')(lambda L, a: _json_lines(L, _n(a, 2)))
lt('jsonmin', 'Minify JSON')(lambda L, a: _json_lines(L, None))
lt('jsonsort', 'Pretty-print JSON with sorted keys')(lambda L, a: _json_lines(L, _n(a, 2), True))


def _csv_md(L, a):
    rows = [[c.strip() for c in l.split(a or ',')] for l in L if l.strip()]
    if not rows:
        return L
    w = max(len(r) for r in rows)
    rows = [r + [''] * (w - len(r)) for r in rows]
    out = ['| ' + ' | '.join(rows[0]) + ' |', '|' + '|'.join(' --- ' for _ in range(w)) + '|']
    out += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
    return out


lt('csv2md', 'Turn CSV lines into a Markdown table')(_csv_md)


# ---------------------------------------------------------------- code: comments
def _comment_of(app):
    return app.b.lang[1] or '#'


def _toggle(app, rng, mode):
    a, b = rng
    c = _comment_of(app)
    lines = app.b.lines[a:b + 1]
    all_c = all(l.strip().startswith(c) for l in lines if l.strip())
    out = []
    for l in lines:
        if not l.strip():
            out.append(l)
            continue
        ind = l[:len(l) - len(l.lstrip())]
        body = l.lstrip()
        if mode == 'off' or (mode == 'toggle' and all_c):
            if body.startswith(c):
                body = body[len(c):]
                body = body[1:] if body.startswith(' ') else body
            out.append(ind + body)
        else:
            out.append(ind + c + ' ' + body)
    app.xapply(a, b, out)
    return f'{len(lines)} lines'


xcmd('comment', 'Comment lines using the file language', 'code')(lambda app, rng, arg: _toggle(app, rng, 'on'))
xcmd('uncomment', 'Uncomment lines', 'code')(lambda app, rng, arg: _toggle(app, rng, 'off'))
xcmd('togglecomment tc', 'Toggle comments on lines', 'code')(lambda app, rng, arg: _toggle(app, rng, 'toggle'))


@xcmd('rmcomments', 'Delete whole-line comments', 'code')
def _rmcomments(app, rng, arg):
    a, b = rng
    c = _comment_of(app)
    old = app.b.lines[a:b + 1]
    new = [l for l in old if not l.strip().startswith(c)] or ['']
    app.xapply(a, b, new)
    return f'removed {len(old) - len(new)} comment lines'


# ---------------------------------------------------------------- code: snippets
SNIPPETS = {
    'python': {'main': 'def main():\n    $0\n\n\nif __name__ == "__main__":\n    main()', 'def': 'def name(args):\n    $0',
               'class': 'class Name:\n    def __init__(self):\n        $0', 'for': 'for item in items:\n    $0',
               'if': 'if condition:\n    $0', 'try': 'try:\n    $0\nexcept Exception as e:\n    print(e)',
               'with': 'with open(path) as f:\n    $0', 'ifmain': 'if __name__ == "__main__":\n    $0'},
    'js': {'fn': 'function name(args) {\n  $0\n}', 'arrow': 'const name = (args) => {\n  $0\n}', 'for': 'for (const item of items) {\n  $0\n}',
           'log': 'console.log($0)', 'class': 'class Name {\n  constructor() {\n    $0\n  }\n}', 'try': 'try {\n  $0\n} catch (e) {\n  console.error(e)\n}'},
    'c': {'main': 'int main(void) {\n    $0\n    return 0;\n}', 'for': 'for (int i = 0; i < n; i++) {\n    $0\n}', 'if': 'if (cond) {\n    $0\n}',
          'inc': '#include <stdio.h>'},
    'cpp': {'main': 'int main() {\n    $0\n    return 0;\n}', 'for': 'for (int i = 0; i < n; i++) {\n    $0\n}', 'inc': '#include <iostream>'},
    'go': {'main': 'package main\n\nimport "fmt"\n\nfunc main() {\n\t$0\n}', 'func': 'func name(args) {\n\t$0\n}', 'for': 'for i := 0; i < n; i++ {\n\t$0\n}',
           'iferr': 'if err != nil {\n\treturn err\n}'},
    'sh': {'shebang': '#!/usr/bin/env bash\nset -euo pipefail\n$0', 'if': 'if [[ cond ]]; then\n  $0\nfi', 'for': 'for f in *; do\n  $0\ndone',
           'func': 'name() {\n  $0\n}'},
    'rust': {'main': 'fn main() {\n    $0\n}', 'fn': 'fn name() {\n    $0\n}', 'for': 'for i in 0..n {\n    $0\n}', 'match': 'match value {\n    _ => $0,\n}'},
    'java': {'main': 'public class Main {\n    public static void main(String[] args) {\n        $0\n    }\n}', 'for': 'for (int i = 0; i < n; i++) {\n    $0\n}'},
}


def _snips(app):
    key = app.b.lang[0]
    return SNIPPETS.get('js' if key in ('js', 'ts') else key, {})


@xcmd('snippet snip', 'Insert a snippet for this language (:snippet main)', 'code')
def _snippet(app, rng, arg):
    snips = _snips(app)
    if arg not in snips:
        return 'snippets: ' + (', '.join(sorted(snips)) or 'none for this language')
    lines = snips[arg].split('\n')
    app.xinsert(lines)
    # put the cursor where $0 was
    bf = app.b
    for k in range(len(lines)):
        row = bf.cur + k
        if row < len(bf.lines) and '$0' in bf.lines[row]:
            col = bf.lines[row].index('$0')
            bf.lines[row] = bf.lines[row].replace('$0', '', 1)
            bf.cur, bf.cc = row, col
            break
    return f'snippet {arg} inserted'


@xcmd('snippets', 'List snippets for this language', 'code')
def _snippets(app, rng, arg):
    app.xout('Snippets', [f':snippet {k}' for k in sorted(_snips(app))] or ['No snippets for this language'])


# ---------------------------------------------------------------- code: navigation and checks
def _scan(app, rx):
    return [(i, l) for i, l in enumerate(app.b.lines) if rx.search(l)]


@xcmd('nexterr', 'Jump to the first syntax error (Python/JSON)', 'code')
def _nexterr(app, rng, arg):
    e, w, ln = diagnostics(app.b)
    if not e:
        return 'no syntax errors found'
    app.goto((ln or 1) - 1)
    return f'syntax error on line {ln}'


@xcmd('def goto-def', 'Jump to a function/class/variable definition', 'code')
def _def(app, rng, arg):
    if not arg:
        return 'usage: :def NAME'
    rx = re.compile(r'^\s*(?:async\s+def|def|class|function|func|fn|const|let|var|struct|enum|type)\s+' + re.escape(arg) + r'\b|^\s*' + re.escape(arg) + r'\s*=')
    hits = _scan(app, rx)
    if not hits:
        return f'no definition of {arg}'
    app.goto(hits[0][0])
    return f'{arg}: line {hits[0][0] + 1}'


@xcmd('outline symbols', 'List functions and classes (Enter jumps)', 'code')
def _outline(app, rng, arg):
    rx = re.compile(r'^\s*(?:async\s+def|def|class|function|func|fn|struct|enum|impl|interface)\s+[A-Za-z_]\w*')
    items = [(f'{i + 1:>5}  {l.strip()[:70]}', (app.b.path, i + 1)) for i, l in _scan(app, rx)]
    app.xlist('Outline', items)


@xcmd('imports', 'List import/include lines', 'code')
def _imports(app, rng, arg):
    rx = re.compile(r'^\s*(?:import|from\s+\S+\s+import|#include|using|require|use)\b')
    app.xlist('Imports', [(f'{i + 1:>5}  {l.strip()[:70]}', (app.b.path, i + 1)) for i, l in _scan(app, rx)])


@xcmd('todo', 'List TODO / FIXME / XXX / HACK lines', 'code')
def _todo(app, rng, arg):
    rx = re.compile(r'\b(TODO|FIXME|XXX|HACK|BUG)\b')
    app.xlist('TODO', [(f'{i + 1:>5}  {l.strip()[:70]}', (app.b.path, i + 1)) for i, l in _scan(app, rx)])


@xcmd('longlines', 'List lines longer than N (default 100)', 'code')
def _long(app, rng, arg):
    n = _n(arg, 100)
    app.xlist(f'Lines > {n}', [(f'{i + 1:>5}  {len(l)} chars', (app.b.path, i + 1)) for i, l in enumerate(app.b.lines) if len(l) > n])


@xcmd('trailing', 'List lines with trailing spaces', 'code')
def _trailing(app, rng, arg):
    app.xlist('Trailing spaces', [(f'{i + 1:>5}  {l.rstrip()[-40:]}', (app.b.path, i + 1)) for i, l in enumerate(app.b.lines) if l != l.rstrip()])


@xcmd('dupelines', 'List duplicated lines', 'code')
def _dupes(app, rng, arg):
    seen = collections.Counter(l for l in app.b.lines if l.strip())
    app.xlist('Duplicate lines', [(f'{c}x  {l.strip()[:70]}', None) for l, c in seen.most_common() if c > 1])


@xcmd('bracketcheck', 'Find unbalanced brackets', 'code')
def _brackets(app, rng, arg):
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for i, line in enumerate(app.b.lines):
        for j, ch in enumerate(line):
            if ch in '([{':
                stack.append((ch, i, j))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    app.goto(i)
                    return f'unmatched {ch} on line {i + 1}'
                stack.pop()
    if stack:
        app.goto(stack[-1][1])
        return f'unclosed {stack[-1][0]} from line {stack[-1][1] + 1}'
    return 'brackets are balanced'


@xcmd('banner', 'Insert a comment banner (:banner TEXT)', 'code')
def _banner(app, rng, arg):
    c = _comment_of(app)
    bar = c + ' ' + '=' * 50
    app.xinsert([bar, f'{c} {arg or "SECTION"}', bar])
    return 'banner inserted'


@xcmd('hr', 'Insert a horizontal rule', 'code')
def _hr(app, rng, arg):
    app.xinsert([('-' * _n(arg, 60))])


# ---------------------------------------------------------------- insert helpers
xcmd('uuid', 'Insert a random UUID', 'edit')(lambda app, rng, arg: app.xtext(str(uuid.uuid4())))
xcmd('date', 'Insert today\'s date', 'edit')(lambda app, rng, arg: app.xtext(time.strftime('%Y-%m-%d')))
xcmd('time', 'Insert the current time', 'edit')(lambda app, rng, arg: app.xtext(time.strftime('%H:%M:%S')))
xcmd('datetime now', 'Insert date and time', 'edit')(lambda app, rng, arg: app.xtext(time.strftime('%Y-%m-%d %H:%M:%S')))
xcmd('timestamp', 'Insert a Unix timestamp', 'edit')(lambda app, rng, arg: app.xtext(str(int(time.time()))))


@xcmd('lorem', 'Insert N words of placeholder text (default 30)', 'edit')
def _lorem(app, rng, arg):
    base = ('lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore '
            'magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi').split()
    n = _n(arg, 30)
    app.xtext(' '.join((base * (n // len(base) + 1))[:n]))


@xcmd('pwgen', 'Insert a random password (default 20 chars)', 'edit')
def _pwgen(app, rng, arg):
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*-_'
    app.xtext(''.join(random.SystemRandom().choice(alphabet) for _ in range(_n(arg, 20))))


@xcmd('seq', 'Insert numbers 1..N on separate lines', 'edit')
def _seq(app, rng, arg):
    app.xinsert([str(i) for i in range(1, _n(arg, 10) + 1)])


@xcmd('s sub', 'Substitute: :%s/old/new/gi', 'edit')
def _subst(app, rng, arg):
    m = re.match(r'^(.)(.*?)(?<!\\)\1(.*?)(?:(?<!\\)\1([gi]*))?$', arg)
    if not m:
        return 'usage: :%s/pattern/replacement/gi'
    d, pat, rep, flags = m.groups()
    flags = flags or ''
    rx = re.compile(pat, re.I if 'i' in flags else 0)
    a, b = rng
    old = app.b.lines[a:b + 1]
    total = 0
    new = []
    for l in old:
        l2, n = rx.subn(rep, l, count=0 if 'g' in flags else 1)
        total += n
        new.append(l2)
    app.xapply(a, b, new)
    return f'{total} substitutions'


# ---------------------------------------------------------------- info
def _text(app, rng):
    return '\n'.join(app.b.lines[rng[0]:rng[1] + 1])


@xcmd('stats wc', 'Lines, words, characters and bytes', 'info')
def _stats(app, rng, arg):
    tx = _text(app, rng)
    return f'{tx.count(chr(10)) + 1} lines, {len(tx.split())} words, {len(tx)} chars, {len(tx.encode())} bytes'


def _nums(app, rng):
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', _text(app, rng))]


def _fmt(x):
    return str(int(x)) if x == int(x) else f'{x:.6g}'


xcmd('sum', 'Sum all numbers in the range', 'info')(lambda app, rng, arg: 'sum = ' + _fmt(sum(_nums(app, rng))))
xcmd('avg', 'Average of numbers in the range', 'info')(lambda app, rng, arg: ('avg = ' + _fmt(sum(_nums(app, rng)) / len(_nums(app, rng)))) if _nums(app, rng) else 'no numbers')
xcmd('minmax', 'Smallest and largest number', 'info')(lambda app, rng, arg: ('min = %s, max = %s' % (_fmt(min(_nums(app, rng))), _fmt(max(_nums(app, rng))))) if _nums(app, rng) else 'no numbers')
xcmd('count', 'Count matches of a regex', 'info')(lambda app, rng, arg: f'{len(re.findall(arg, _text(app, rng)))} matches' if arg else 'usage: :count PATTERN')
xcmd('md5', 'MD5 of the range', 'info')(lambda app, rng, arg: 'md5 ' + hashlib.md5(_text(app, rng).encode()).hexdigest())
xcmd('sha1', 'SHA-1 of the range', 'info')(lambda app, rng, arg: 'sha1 ' + hashlib.sha1(_text(app, rng).encode()).hexdigest())
xcmd('sha256', 'SHA-256 of the range', 'info')(lambda app, rng, arg: 'sha256 ' + hashlib.sha256(_text(app, rng).encode()).hexdigest())


@xcmd('freq', 'Most frequent words', 'info')
def _freq(app, rng, arg):
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü']{3,}", _text(app, rng).lower())
    app.xlist('Word frequency', [(f'{c:>4}  {w}', None) for w, c in collections.Counter(words).most_common(50)])


@xcmd('marks', 'List marks set with m<letter>', 'info')
def _marks(app, rng, arg):
    items = [(f"'{k}  line {v[0] + 1 if isinstance(v, (tuple, list)) else v + 1}", (app.b.path, (v[0] if isinstance(v, (tuple, list)) else v) + 1))
             for k, v in sorted(app.b.marks.items())]
    app.xlist('Marks', items)


@xcmd('where', 'Path, size, language and modified time of this file', 'info')
def _where(app, rng, arg):
    b = app.b
    if not b.path or not os.path.exists(b.path):
        return f'{b.bufname()} (not saved yet), language {b.lang[0]}'
    st = os.stat(b.path)
    return f"{os.path.abspath(b.path)}  {st.st_size} bytes  {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}  {b.lang[0]}"


_SAFE = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
         ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'log': math.log, 'log10': math.log10,
          'abs': abs, 'round': round, 'floor': math.floor, 'ceil': math.ceil}
_CONST = {'pi': math.pi, 'e': math.e}


def safe_eval(expr):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE:
            if isinstance(n.op, ast.Pow) and abs(ev(n.right)) > 1000:
                raise ValueError('exponent too large')
            return _SAFE[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _SAFE:
            return _SAFE[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Name) and n.id in _CONST:
            return _CONST[n.id]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise ValueError('unsupported expression')
    return ev(ast.parse(expr, mode='eval'))


@xcmd('calc', 'Calculator: :calc 2*(3+4)  (:calc! also inserts the result)', 'info')
def _calc(app, rng, arg):
    try:
        r = safe_eval(arg)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError) as e:
        return f'calc error: {e}'
    return f'{arg} = {_fmt(r) if isinstance(r, (int, float)) else r}'


@xcmd('calc!', 'Calculator that inserts the result at the cursor', 'info')
def _calci(app, rng, arg):
    try:
        r = safe_eval(arg)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError) as e:
        return f'calc error: {e}'
    app.xtext(_fmt(r))
    return f'{arg} = {_fmt(r)}'


# ---------------------------------------------------------------- files and project
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'target', 'dist', 'build', '.mypy_cache'}


def _walk(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith('.'))
        for f in sorted(files):
            yield os.path.join(d, f)


@xcmd('grep', 'Search all files under the current folder (Enter jumps)', 'file')
def _grep(app, rng, arg):
    if not arg:
        return 'usage: :grep PATTERN'
    try:
        rx = re.compile(arg, 0 if re.search(r'[A-Z]', arg) else re.I)
    except re.error as e:
        return f'bad pattern: {e}'
    root = os.getcwd()
    items = []
    for path in _walk(root):
        try:
            if os.path.getsize(path) > 1_000_000:
                continue
            with open(path, encoding='utf-8') as f:
                for n, line in enumerate(f, 1):
                    if rx.search(line):
                        items.append((f'{os.path.relpath(path, root)}:{n}: {line.strip()[:60]}', (path, n)))
                        if len(items) >= 500:
                            break
        except (OSError, UnicodeDecodeError):
            continue
        if len(items) >= 500:
            break
    app.xlist(f'grep {arg}  ({len(items)})', items)


@xcmd('find ff', 'Find files by name under the current folder', 'file')
def _find(app, rng, arg):
    if not arg:
        return 'usage: :find NAME'
    root = os.getcwd()
    items = [(os.path.relpath(p, root), (p, 1)) for p in _walk(root) if arg.lower() in os.path.basename(p).lower()][:500]
    app.xlist(f'find {arg}  ({len(items)})', items)


RECENT_FILE = os.path.join(os.path.dirname(CONFIG_FILE), 'recent.json')


def record_recent(path):
    try:
        full = os.path.abspath(path)
        try:
            with open(RECENT_FILE, encoding='utf-8') as f:
                cur = json.load(f)
        except (OSError, ValueError):
            cur = []
        cur = [full] + [p for p in cur if p != full][:29]
        os.makedirs(os.path.dirname(RECENT_FILE), exist_ok=True)
        with open(RECENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(cur, f)
    except OSError:
        pass


@xcmd('recent', 'Recently opened files (Enter opens)', 'file')
def _recent(app, rng, arg):
    try:
        with open(RECENT_FILE, encoding='utf-8') as f:
            cur = json.load(f)
    except (OSError, ValueError):
        cur = []
    app.xlist('Recent files', [(p.replace(os.path.expanduser('~'), '~'), (p, 1)) for p in cur if os.path.exists(p)])


@xcmd('dirtree dt', 'Show a folder tree (:dirtree [depth])', 'file')
def _dirtree(app, rng, arg):
    depth = _n(arg, 2)
    root = os.getcwd()
    out = [os.path.basename(root) + '/']

    def rec(d, prefix, lvl):
        try:
            ents = sorted(os.scandir(d), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        ents = [e for e in ents if not e.name.startswith('.') and e.name not in SKIP_DIRS]
        for k, e in enumerate(ents):
            last = k == len(ents) - 1
            out.append(prefix + ('└── ' if last else '├── ') + e.name + ('/' if e.is_dir() else ''))
            if e.is_dir() and lvl < depth:
                rec(e.path, prefix + ('    ' if last else '│   '), lvl + 1)
    rec(root, '', 1)
    app.xout('Tree', out[:400])


xcmd('pwd', 'Print the working folder', 'file')(lambda app, rng, arg: os.getcwd())


@xcmd('cd', 'Change the working folder', 'file')
def _cd(app, rng, arg):
    try:
        os.chdir(os.path.expanduser(arg or '~'))
    except OSError as e:
        return f'cd: {e.strerror}'
    app._side_cache = (0, None, [])
    app.side_dir = None
    return os.getcwd()


@xcmd('dir', 'List files in a folder (Enter opens)', 'file')
def _dir(app, rng, arg):
    d = os.path.expanduser(arg or '.')
    try:
        ents = sorted(os.scandir(d), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as e:
        return f'dir: {e.strerror}'
    app.xlist(f'dir {d}', [(e.name + ('/' if e.is_dir() else ''), (e.path, 1)) for e in ents if not e.is_dir()])


@xcmd('new touch', 'Create and open a new file (:new name.py)', 'file')
def _new(app, rng, arg):
    if not arg:
        return 'usage: :new NAME'
    app.open_path(arg)


@xcmd('rename mv', 'Rename the current file', 'file')
def _rename(app, rng, arg):
    b = app.b
    if not (b.path and arg):
        return 'usage: :rename NEWNAME (file must be saved)'
    dst = os.path.join(os.path.dirname(os.path.abspath(b.path)), arg)
    if os.path.exists(dst):
        return 'target exists'
    try:
        os.rename(b.path, dst)
    except OSError as e:
        return f'rename: {e.strerror}'
    b.path, b.name = dst, os.path.basename(dst)
    b.lang = pick_lang(dst)
    b.rule = make_rule(b.lang)
    b._spans = {}
    return 'renamed to ' + b.name


@xcmd('backup bak', 'Save a copy as name.bak', 'file')
def _backup(app, rng, arg):
    b = app.b
    if not b.path:
        return 'save the file first'
    dst = os.path.abspath(b.path) + '.bak'
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(b.lines) + '\n')
    return 'backup: ' + dst


@xcmd('r read', 'Insert the contents of a file below the cursor', 'file')
def _read(app, rng, arg):
    try:
        with open(os.path.expanduser(arg), encoding='utf-8') as f:
            app.xinsert(f.read().rstrip('\n').split('\n'))
    except (OSError, UnicodeDecodeError) as e:
        return f'read: {e}'
    return 'inserted ' + arg


@xcmd('diskdiff', 'Show what changed compared to the saved file', 'file')
def _diskdiff(app, rng, arg):
    b = app.b
    if not (b.path and os.path.exists(b.path)):
        return 'file is not on disk yet'
    with open(b.path, encoding='utf-8', errors='replace') as f:
        disk = f.read().split('\n')
    if disk and disk[-1] == '':
        disk.pop()
    diff = [l.rstrip('\n') for l in difflib.unified_diff(disk, b.lines, 'disk', 'buffer', lineterm='', n=1)]
    app.xout('Diff vs disk', diff or ['no differences'])


def _sh(cmd, cwd=None, timeout=15):
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except (OSError, subprocess.SubprocessError) as e:
        return [f'error: {e}']
    return (r.stdout + r.stderr).rstrip('\n').split('\n')


@xcmd('sh !', 'Run a shell command and show its output', 'file')
def _shell(app, rng, arg):
    if not arg:
        return 'usage: :sh COMMAND'
    app.xout('$ ' + arg, _sh(arg))


@xcmd('gitstatus gs', 'Changed files according to git (Enter opens)', 'file')
def _gitstatus(app, rng, arg):
    out = _sh(['git', 'status', '--short'])
    if out and out[0].startswith(('fatal', 'error')):
        return out[0]
    root = (_sh(['git', 'rev-parse', '--show-toplevel']) or [os.getcwd()])[0]
    app.xlist('git status', [(l, (os.path.join(root, l[3:].strip().split(' -> ')[-1]), 1)) for l in out if len(l) > 3])


@xcmd('gitlog gl', 'Last 20 commits', 'file')
def _gitlog(app, rng, arg):
    app.xout('git log', _sh(['git', 'log', '--oneline', '-20']))


@xcmd('gitdiff gd', 'git diff of the current file', 'file')
def _gitdiff(app, rng, arg):
    cmd = ['git', 'diff', '--no-color'] + ([app.b.path] if app.b.path else [])
    app.xout('git diff', _sh(cmd) or ['no changes'])


xcmd('gitbranch gb', 'Current git branch', 'file')(lambda app, rng, arg: 'branch: ' + (git_branch(app.b.path) or 'not a git repository'))


@xcmd('bm bookmark', 'Bookmark the current line', 'file')
def _bm(app, rng, arg):
    app.bookmarks.append((app.b.path, app.b.cur + 1, app.b.lines[app.b.cur].strip()[:50]))
    return f'bookmark {len(app.bookmarks)} added'


@xcmd('bms bookmarks', 'List bookmarks (Enter jumps)', 'file')
def _bms(app, rng, arg):
    app.xlist('Bookmarks', [(f'{os.path.basename(p or "[New]")}:{n}  {txt}', (p, n)) for p, n, txt in app.bookmarks])


# ---------------------------------------------------------------- view and discovery
@xcmd('zen', 'Toggle distraction-free mode (no explorer, no numbers)', 'view')
def _zen(app, rng, arg):
    on = not app.opts.get('_zen')
    app.opts['_zen'] = on
    app.opts['sidebar'] = not on
    app.opts['number'] = not on
    return 'zen mode ' + ('on' if on else 'off')


xcmd('ruler', 'Set the column ruler (:ruler 80, 0 = off)', 'view')(lambda app, rng, arg: app.opts.__setitem__('ruler', _n(arg, 0)) or f'ruler {_n(arg, 0)}')
xcmd('tab', 'Set the tab width (:tab 2)', 'view')(lambda app, rng, arg: app.opts.__setitem__('tabsize', _n(arg, 4)) or f'tab width {_n(arg, 4)}')
xcmd('whitespace ws', 'Toggle whitespace dots', 'view')(lambda app, rng, arg: app.opts.__setitem__('showws', not app.opts.get('showws')) or 'whitespace toggled')
xcmd('guides', 'Toggle indent guides', 'view')(lambda app, rng, arg: app.opts.__setitem__('indentguide', not app.opts.get('indentguide', True)) or 'guides toggled')
xcmd('cursorline cl', 'Toggle the cursor line highlight', 'view')(lambda app, rng, arg: app.opts.__setitem__('cursorline', not app.opts.get('cursorline', True)) or 'cursor line toggled')


@xcmd('commands palette', 'Command palette: every command with its description', 'view')
def _commands(app, rng, arg):
    names = sorted({v['name'] for v in XCMDS.values()})
    items = [(f":{n:<12} {XCMDS[n]['doc']}", ('cmd', n)) for n in names if not arg or arg in n or arg in XCMDS[n]['doc'].lower()]
    app.xlist(f'Commands ({len(items)})', items)


@xcmd('features', 'Count and group the extra commands', 'view')
def _features(app, rng, arg):
    names = {v['name']: v for v in XCMDS.values()}
    out = [f'{len(names)} extra commands']
    for cat, label in XCATS.items():
        ns = sorted(n for n, v in names.items() if v['cat'] == cat)
        out.append(f'{label} ({len(ns)}): ' + ' '.join(ns))
    app.xout('Features', out)


@xcmd('cmdhelp', 'Describe a command (:cmdhelp sort)', 'view')
def _cmdhelp(app, rng, arg):
    v = XCMDS.get(arg)
    return f":{v['name']}  {v['doc']}" if v else 'unknown command'


class XMixin:
    bookmarks = []

    def xapply(self, a, b, new):
        bf = self.b
        bf.snapshot()
        bf.lines[a:b + 1] = new or ['']
        bf.cur = max(0, min(bf.cur, len(bf.lines) - 1))
        bf.cc = min(bf.cc, len(bf.lines[bf.cur]))
        bf.touch()

    def xinsert(self, lines):
        bf = self.b
        bf.snapshot()
        cur = bf.lines[bf.cur]
        ind = cur[:len(cur) - len(cur.lstrip())]
        lines = [(ind + l) if l else l for l in lines]
        if cur.strip():
            at = bf.cur + 1
            bf.lines[at:at] = lines
        else:
            at = bf.cur
            bf.lines[at:at + 1] = lines
        bf.cur, bf.cc = at, 0
        bf.touch()

    def xtext(self, s):
        self.b.snapshot()
        self.b.insert_text(s)

    def xout(self, title, lines):
        if len(lines) > 8:
            self.xlist(title, [(l, None) for l in lines])
        else:
            self.panel = {'title': title, 'lines': lines, 'cmd': title.split()[0] if title else 'out'}

    def xlist(self, title, items):
        self.xres_title = title
        self.xres_items = items
        self.open_list('xres')
        if not items:
            self.msg = title + ': nothing found'

    def xjump(self, payload):
        if not payload:
            return
        if payload[0] == 'cmd':
            self.msg = f':{payload[1]}  ' + XCMDS[payload[1]]['doc']
            return
        path, line = payload
        if path and (not self.b.path or os.path.abspath(path) != os.path.abspath(self.b.path)):
            self.open_path(path)
        self.goto(max(0, line - 1))

    def extra_command(self, text):
        m = re.match(r'^(?:(\d+|\.|\$|%)(?:,(\d+|\.|\$))?)?\s*(.*)$', text, re.S)
        r1, r2, rest = m.groups()
        if not rest:
            return None
        sm = re.match(r'^s([^\w\s])', rest)
        if sm:
            name, arg = 's', rest[1:]
        else:
            parts = rest.split(None, 1)
            name, arg = parts[0], (parts[1].strip() if len(parts) > 1 else '')
        spec = XCMDS.get(name) or XCMDS.get(name.rstrip('!')) if name not in ('calc!', 'sort!') else XCMDS.get(name)
        if spec is None:
            return None
        n = len(self.b.lines)

        def conv(x):
            return self.b.cur if x == '.' else (n - 1 if x == '$' else int(x) - 1)
        if r1 is None or r1 == '%':
            a, b = 0, n - 1
        else:
            a = conv(r1)
            b = conv(r2) if r2 else a
        a, b = sorted((max(0, min(a, n - 1)), max(0, min(b, n - 1))))
        try:
            res = spec['fn'](self, (a, b), arg)
        except Exception as e:      # a bad regex or bad input must never crash the editor
            res = f"{spec['name']}: {type(e).__name__}: {e}"
        if res:
            self.msg = str(res)
        return True


# ====================================================================== GUI layer (menu bar, palette, mouse)
# Menu items: (label, action, hint). Actions starting with ':' run a command; a trailing space or "/"
# opens the command line with the text pre-filled. Actions starting with '@' are built-in actions.

MENUS = [
    ('File', [
        ('New file', '@new', 'Ctrl-N'), ('Open...', '@open', 'Ctrl-O'), ('Code + playground', ':play', ''),
        ('Recent files', ':recent', ''), None,
        ('Save', '@save', 'Ctrl-S'), ('Save as...', ':w ', ''), ('Backup copy', ':backup', ''),
        ('Rename...', ':rename ', ''), ('Reload from disk', ':e!', ''), None,
        ('Close buffer', ':q', ''), ('Quit', '@quit', 'Ctrl-Q')]),
    ('Edit', [
        ('Undo', '@undo', 'u'), ('Find...', '@find', 'Ctrl-F'), ('Replace...', ':%s/', ''),
        ('Go to line...', '@goto', 'Ctrl-G'), ('Clipboard history', '@clip', 'Ctrl-P'), None,
        ('Sort A-Z', ':sort', ''), ('Sort Z-A', ':sort!', ''), ('Remove duplicates', ':dedupe', ''),
        ('Reverse lines', ':reverse', ''), ('Delete blank lines', ':delblank', ''), ('Join lines', ':join', ''),
        ('Trim trailing spaces', ':trim', '')]),
    ('Format', [
        ('UPPERCASE', ':upper', ''), ('lowercase', ':lower', ''), ('Title Case', ':title', ''), None,
        ('camelCase', ':camel', ''), ('snake_case', ':snake', ''), ('kebab-case', ':kebab', ''),
        ('PascalCase', ':pascal', ''), ('CONSTANT_CASE', ':constant', ''), None,
        ('Indent', ':indent', ''), ('Dedent', ':dedent', ''), ('Wrap at 72', ':wrap 72', ''),
        ('Number lines', ':number', ''), ('Bullets', ':bullet', ''), ('Quote', ':quote', '')]),
    ('Insert', [
        ('Snippet...', ':snippet ', ''), ('Snippet list', ':snippets', ''), None,
        ('Date', ':date', ''), ('Date and time', ':datetime', ''), ('UUID', ':uuid', ''),
        ('Lorem ipsum', ':lorem', ''), ('Password', ':pwgen', ''), None,
        ('Banner...', ':banner ', ''), ('Divider', ':hr', ''), ('Numbers 1-10', ':seq', ''), ('File contents...', ':r ', '')]),
    ('Code', [
        ('Comment', ':comment', ''), ('Uncomment', ':uncomment', ''), ('Toggle comment', ':togglecomment', ''), None,
        ('Run', '@run', 'F5'), ('Output panel', ':panel', 'F6'), None,
        ('Next syntax error', ':nexterr', ''), ('Outline', ':outline', ''), ('Imports', ':imports', ''),
        ('TODO list', ':todo', ''), ('Check brackets', ':bracketcheck', ''), ('Long lines', ':longlines', ''),
        ('JSON pretty', ':json', ''), ('JSON minify', ':jsonmin', '')]),
    ('Go', [
        ('Find in project...', ':grep ', ''), ('Find file...', ':find ', ''), ('Definition...', ':def ', ''), None,
        ('Bookmark line', ':bm', ''), ('Bookmarks', ':bms', ''), ('Marks', ':marks', ''), None,
        ('Command palette', '@palette', 'F4'), ('Directory tree', ':dirtree', '')]),
    ('View', [
        ('Explorer', '@sidebar', 'F2'), ('IDE layout', ':ide', ''), ('Zen mode', ':zen', ''), None,
        ('Settings', ':settings', ''), ('Whitespace dots', ':whitespace', ''), ('Indent guides', ':guides', ''),
        ('Cursor line', ':cursorline', ''), ('Ruler 80', ':ruler 80', ''), ('Ruler off', ':ruler 0', ''), None,
        ('Tab width 2', ':tab 2', ''), ('Tab width 4', ':tab 4', ''), None,
        ('Toggle menu bar', ':menubar', ''), ('Toggle mouse', ':mouse', '')]),
    ('Tools', [
        ('Statistics', ':stats', ''), ('Sum numbers', ':sum', ''), ('Calculator...', ':calc ', ''),
        ('SHA-256', ':sha256', ''), ('Word frequency', ':freq', ''), ('Diff vs disk', ':diskdiff', ''), None,
        ('git status', ':gitstatus', ''), ('git log', ':gitlog', ''), ('git diff', ':gitdiff', ''),
        ('Shell command...', ':sh ', ''), None, ('N box', '@box', ''), ('Install package', ':pkg', '')]),
    ('Help', [
        ('Help', '@help', 'F1'), ('All commands', ':commands', ''), ('Feature summary', ':features', ''),
        ('Version', ':version', '')]),
]

ARGS_NEEDED = {'filter', 'reject', 'prefix', 'suffix', 'splitat', 'grep', 'find', 'def', 'snippet', 'count', 'rename',
               'new', 'r', 'sh', 'calc', 'calc!', 's', 'cd', 'cmdhelp', 'banner'}


@xcmd('menubar', 'Show or hide the menu bar', 'view')
def _menubar(app, rng, arg):
    app.opts['menubar'] = not app.opts.get('menubar', True)
    return 'menu bar ' + ('on' if app.opts['menubar'] else 'off')


@xcmd('mouse', 'Turn mouse support on or off (off lets you select text with the terminal)', 'view')
def _mouse(app, rng, arg):
    on = not app.opts.get('mouse', True)
    app.opts['mouse'] = on
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS if on else 0)
    except curses.error:
        pass
    return 'mouse ' + ('on' if on else 'off')


class GuiMixin:
    hit_menu = []
    hit_tabs = []
    side_rows = {}
    rowmap = {}
    frame_off = (0, 0)
    drop_i = 0
    drop_sel = 0
    drop_back = 'NORMAL'
    drop_rect = None
    drop_rows = {}
    pal_q = ''
    pal_i = 0
    pal_rect = None
    pal_rows = {}

    # ---- drawing
    def draw_menubar(self):
        w = self.width
        b = self.b
        txt = self.colors.on_bar('text')
        acc = self.colors.on_bar('accent', True)
        com = self.colors.on_bar('com')
        self.put(0, 0, ' ' * w, txt)
        self.put(0, 1, 'nview', acc)
        x = 8
        self.hit_menu = []
        for i, (title, _) in enumerate(MENUS):
            label = f' {title} '
            if x + len(label) > w - 12:
                break
            on = self.mode == 'DROP' and i == self.drop_i
            self.put(0, x, label, self.colors.accent_cell() if on else txt)
            self.hit_menu.append((x, x + len(label), i))
            x += len(label)
        right = f"{b.bufname()}{' ●' if b.modified else ''}  v{VERSION}"
        if x + len(right) + 2 < w:
            self.put(0, w - len(right) - 1, right, com)

    def draw_dropdown(self):
        items = MENUS[self.drop_i][1]
        base = self.colors.style('text', self.colors.cursor_bg())
        com = self.colors.style('com', self.colors.cursor_bg())
        sel_attr = self.colors.style('accent') | curses.A_REVERSE | curses.A_BOLD
        labw = max(len(it[0]) for it in items if it)
        hintw = max((len(it[2]) for it in items if it), default=0)
        width = labw + hintw + 6
        x0 = next((x for x, _, i in self.hit_menu if i == self.drop_i), 1)
        x0 = max(0, min(x0, self.width - width))
        avail = self.height - 3
        shown = items[:max(1, avail - 2)]
        self.drop_rect = (1, x0, len(shown) + 2, width)
        self.drop_rows = {}
        self.put(1, x0, '┌' + '─' * (width - 2) + '┐', base)
        for k, it in enumerate(shown):
            y = 2 + k
            if it is None:
                self.put(y, x0, '├' + '─' * (width - 2) + '┤', base)
                continue
            on = k == self.drop_sel
            attr = sel_attr if on else base
            self.put(y, x0, '│' + ' ' * (width - 2) + '│', base)
            self.put(y, x0 + 1, ' ' + it[0].ljust(labw + 1) + ' ' * (hintw + 1), attr)
            if it[2]:
                self.put(y, x0 + width - 2 - len(it[2]), it[2], attr if on else com)
            self.drop_rows[y] = k
        self.put(2 + len(shown), x0, '└' + '─' * (width - 2) + '┘', base)

    def pal_items(self):
        items, seen = [], set()
        for title, its in MENUS:
            for it in its:
                if it and it[1] not in seen:
                    seen.add(it[1])
                    items.append((f'{title}: {it[0]}', it[1], it[2]))
        for n in sorted({v['name'] for v in XCMDS.values()}):
            act = ':' + n + (' ' if n in ARGS_NEEDED else '')
            if act not in seen:
                seen.add(act)
                items.append((f":{n}  {XCMDS[n]['doc']}", act, ''))
        q = self.pal_q.lower().split()
        if q:
            items = [x for x in items if all(w in x[0].lower() for w in q)]
        return items

    def draw_palette(self):
        w = self.width
        width = min(78, w - 4)
        base = self.colors.style('text', self.colors.cursor_bg())
        com = self.colors.style('com', self.colors.cursor_bg())
        acc = self.colors.style('accent') | curses.A_BOLD
        sel_attr = self.colors.style('accent') | curses.A_REVERSE | curses.A_BOLD
        items = self.pal_items()
        self.pal_i = max(0, min(self.pal_i, len(items) - 1))
        rows = min(12, max(1, self.height - 8))
        top = max(0, min(self.pal_i - rows + 1, len(items) - rows)) if self.pal_i >= rows else 0
        x0 = (w - width) // 2
        self.pal_rect = (2, x0, rows + 3, width)
        self.pal_rows = {}
        self.put(2, x0, '┌' + '─' * (width - 2) + '┐', base)
        self.put(3, x0, '│' + ' ' * (width - 2) + '│', base)
        self.put(3, x0 + 2, '> ', acc)
        self.put(3, x0 + 4, self.pal_q[-(width - 8):] + '▌', base)
        self.put(3, x0 + width - 12, f'{len(items)} found', com)
        self.put(4, x0, '├' + '─' * (width - 2) + '┤', base)
        for k in range(rows):
            y = 5 + k
            self.put(y, x0, '│' + ' ' * (width - 2) + '│', base)
            if top + k < len(items):
                label, act, hint = items[top + k]
                on = top + k == self.pal_i
                attr = sel_attr if on else base
                self.put(y, x0 + 1, (' ' + label)[:width - 2].ljust(width - 2), attr)
                if hint:
                    self.put(y, x0 + width - 2 - len(hint), hint, attr if on else com)
                self.pal_rows[y] = top + k
        self.put(5 + rows, x0, '└' + '─' * (width - 2) + '┘', base)

    # ---- actions
    def gui_menu(self, i):
        self.drop_back = self.mode if self.mode in ('NORMAL', 'INSERT') else 'NORMAL'
        self.mode = 'DROP'
        self.drop_i = i % len(MENUS)
        self.drop_sel = next((k for k, it in enumerate(MENUS[self.drop_i][1]) if it), 0)
        self.comp = None

    def open_palette(self):
        self.drop_back = self.mode if self.mode in ('NORMAL', 'INSERT') else 'NORMAL'
        self.mode = 'PALETTE'
        self.pal_q, self.pal_i = '', 0
        self.comp = None

    def gui_run(self, action):
        back = self.drop_back
        self.mode = back
        self.prompt_back = back
        if action.startswith('@'):
            name = action[1:]
            if name == 'new':
                self.new_buffer()
            elif name == 'open':
                self.enter_open()
            elif name == 'save':
                self.write()
            elif name == 'quit':
                return self.quit_app(False)
            elif name == 'undo':
                self.undo()
            elif name == 'find':
                self.start_search('/')
            elif name == 'goto':
                self.mode, self.buf = 'CMD', ''
            elif name == 'clip':
                self.open_list('ring')
            elif name == 'run':
                self.run_code()
            elif name == 'palette':
                self.open_palette()
            elif name == 'sidebar':
                self.ide_global_key(curses.KEY_F2)
            elif name == 'box':
                self.open_list('boxmenu')
            elif name == 'help':
                self.help = True
            return True
        text = action[1:]
        if text.endswith((' ', '/')):
            self.mode, self.buf = 'CMD', text
            return True
        r = self.command(text)
        return True if r is None else r

    def drop_key(self, code, ch):
        items = MENUS[self.drop_i][1]

        def step(d):
            k = self.drop_sel
            for _ in range(len(items)):
                k = (k + d) % len(items)
                if items[k]:
                    self.drop_sel = k
                    return
        if code in (27, curses.KEY_F10):
            self.mode = self.drop_back
        elif code == curses.KEY_RIGHT or ch == 'l':
            self.gui_menu(self.drop_i + 1)
        elif code == curses.KEY_LEFT or ch == 'h':
            self.gui_menu(self.drop_i - 1)
        elif code == curses.KEY_DOWN or ch == 'j':
            step(1)
        elif code == curses.KEY_UP or ch == 'k':
            step(-1)
        elif code in (10, 13, curses.KEY_ENTER):
            it = items[self.drop_sel]
            if it:
                return self.gui_run(it[1])
        return True

    def palette_key(self, code, ch):
        items = self.pal_items()
        if code == 27:
            self.mode = self.drop_back
        elif code == curses.KEY_DOWN:
            self.pal_i = min(len(items) - 1, self.pal_i + 1)
        elif code == curses.KEY_UP:
            self.pal_i = max(0, self.pal_i - 1)
        elif code in (10, 13, curses.KEY_ENTER):
            if items:
                return self.gui_run(items[min(self.pal_i, len(items) - 1)][1])
            self.mode = self.drop_back
        elif code in (8, 127, curses.KEY_BACKSPACE):
            self.pal_q = self.pal_q[:-1]
            self.pal_i = 0
        elif code == 21:
            self.pal_q, self.pal_i = '', 0
        elif ch and ch.isprintable():
            self.pal_q += ch
            self.pal_i = 0
        return True

    # ---- mouse
    def mouse_event(self):
        try:
            _, mx, my, _, bs = curses.getmouse()
        except curses.error:
            return True
        dy, dx = self.frame_off
        x, y = mx - dx, my - dy
        press = bool(bs & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED))
        up = bool(bs & curses.BUTTON4_PRESSED)
        down = bool(bs & getattr(curses, 'BUTTON5_PRESSED', 0))
        m = self.mode
        if m == 'DROP':
            if press:
                if self.drop_rect and y in self.drop_rows and self.drop_rect[1] <= x < self.drop_rect[1] + self.drop_rect[3]:
                    it = MENUS[self.drop_i][1][self.drop_rows[y]]
                    if it:
                        return self.gui_run(it[1])
                    return True
                hit = next((i for x0, x1, i in self.hit_menu if y == 0 and x0 <= x < x1), None)
                if hit is not None:
                    self.gui_menu(hit)
                else:
                    self.mode = self.drop_back
            return True
        if m == 'PALETTE':
            if press:
                if y in self.pal_rows:
                    return self.gui_run(self.pal_items()[self.pal_rows[y]][1])
                self.mode = self.drop_back
            return True
        if m not in ('NORMAL', 'INSERT'):
            return True
        b = self.b
        if up or down:
            b.cur = max(0, min(len(b.lines) - 1, b.cur + (-3 if up else 3)))
            b.cc = min(b.cc, len(b.lines[b.cur]))
            return True
        if not press:
            return True
        if y == 0:
            hit = next((i for x0, x1, i in self.hit_menu if x0 <= x < x1), None)
            if hit is not None:
                self.gui_menu(hit)
            return True
        if self.ide and y == TOP:
            for x0, x1, k in self.hit_tabs:
                if x0 <= x < x1:
                    self.bi = k
                    self.comp = None
            return True
        if self.ide and x < self.ox:
            if y in self.side_rows:
                name, path, isdir = self.side_entries()[self.side_rows[y]]
                if isdir:
                    self.side_dir, self.side_idx = path, 0
                else:
                    self.open_path(path)
            return True
        if y in self.rowmap and x >= self.ox + self.gw:
            line, start = self.rowmap[y]
            b.cur = line
            b.cc = max(0, min(len(b.lines[line]), start + x - self.ox - self.gw))
            self.side_focus = False
            self.comp = None
        return True


class App(XMixin, GuiMixin):
    MENU_N = 2

    def __init__(self, scr, paths, splash, colors):
        self.scr = scr
        self.colors = colors
        self.bufs = [Buffer(p) for p in paths] or [Buffer(None)]
        self.bi = 0
        self.opts = {
            'number': True, 'relativenumber': False, 'wrap': False,
            'ignorecase': False, 'hlsearch': True, 'syntax': True,
            'cursorline': True, 'autoindent': False, 'tabsize': 4, 'scrolloff': 0, 'statushints': True, 'confirmquit': True, 'ruler': 0, 'showws': False, 'indentguide': True, 'bracketmatch': True, 'autoclose': False, 'trimws': False, 'finalnl': True, 'focus': False, 'wordgoal': 0, 'snapshots': True, 'ide': True, 'sidebar': True,
        }
        self.mode = 'SPLASH' if (splash and not paths) else 'INSERT'
        self.prompt_back = 'INSERT'
        self.screen_back = 'INSERT'
        self.ob_dir = START.get('dir') or os.getcwd()
        self.ob_entries = []
        self.ob_idx = 0
        self.ob_top = 0
        self.ob_prompt = False
        self.ob_hidden = False
        self.st_idx = 1
        self.st_top = 0
        self.search_origin = None
        self.lst_kind = 'ring'
        self.lst_items = []
        self.lst_idx = 0
        self.lst_top = 0
        self.ring = []
        self.panel = None
        self.job = None
        self.sp_idx = 0
        self.opts.update({k: v for k, v in SETTINGS.get('opts', {}).items() if k in self.opts})
        if START.get('mode'):
            self.mode = START['mode']
            self.ob_load()
        self.menu_back = 'NORMAL'
        self.menu_idx = 0
        self.help = False
        self.buf = ''
        self.prefix = ''
        self.count = ''
        self.pending = ''
        self.pcount = 0
        self.search = ''
        self.search_fwd = True
        self.nohl = False
        self.reg_lines = []
        self.reg = ''
        self.width = 80
        self.height = 24
        self.rows = 1
        self.textw = 1
        self.gw = 0
        self.msg = ''
        if any(b.binary for b in self.bufs):
            self.msg = t('binary')
        elif paths and self.b.is_new:
            self.msg = t('newfile', name=self.b.name)

    @property
    def b(self):
        return self.bufs[self.bi]

    # ---- çizim yardımcıları

    def put(self, y, x, s, attr=0):
        if not s or x < 0 or x >= self.width or y < 0:
            return
        s = s[:self.width - x]
        try:
            self.scr.addstr(y, x, s, attr)
        except curses.error:
            pass  # ekranın sağ-alt köşesi: yoksay

    def put_runs(self, y, x, seg, sa):
        k = 0
        while k < len(seg):
            j = k + 1
            while j < len(seg) and sa[j] == sa[k]:
                j += 1
            self.put(y, x + k, seg[k:j], sa[k])
            k = j

    def search_re(self):
        return re.compile(re.escape(self.search), re.I if self.opts['ignorecase'] else 0)

    def line_attrs(self, i):
        b = self.b
        line = b.lines[i]
        cur = i == b.cur
        bg = self.colors.cursor_bg() if (self.opts['cursorline'] and cur) else -1
        attrs = [self.colors.style('text', bg)] * (len(line) + 1)
        dim = bool(self.opts.get('focus') and getattr(self, 'para', None)
                   and not (self.para[0] <= i <= self.para[1]))
        if dim:
            attrs = [self.colors.style('com')] * (len(line) + 1)
        if self.opts['syntax'] and not dim:
            for s, e, kind in b.spans(i):
                a = self.colors.style(kind, bg)
                for k in range(s, min(e, len(line))):
                    attrs[k] = a
        if self.search and self.opts['hlsearch'] and not self.nohl:
            sa = self.colors.search_attr()
            for m in self.search_re().finditer(line):
                for k in range(m.start(), m.end()):
                    attrs[k] = sa
        match = getattr(self, 'match', None)
        if match:
            (l1, c1), other = match
            ma = self.colors.style('accent') | curses.A_BOLD | curses.A_UNDERLINE
            if i == l1 and c1 < len(line):
                attrs[c1] = ma
            if other and i == other[0] and other[1] < len(line):
                attrs[other[1]] = ma
        if cur and self.mode in ('NORMAL', 'INSERT', 'SPLASH'):
            attrs[min(b.cc, len(attrs) - 1)] |= curses.A_REVERSE
        return attrs

    def numlabel(self, i):
        b = self.b
        rel = self.opts['relativenumber']
        if self.opts['number'] and rel:
            label = str(i + 1) if i == b.cur else str(abs(i - b.cur))
        elif rel:
            label = '0' if i == b.cur else str(abs(i - b.cur))
        else:
            label = str(i + 1)
        return label.rjust(self.gw - 4) + '    '

    def mode_label(self):
        if self.mode == 'LIST':
            return t({'timeline': 'mode_timeline', 'lang': 'mode_lang', 'boxmenu': 'mode_box', 'boxdistro': 'mode_box', 'boxlist': 'mode_box', 'xres': 'mode_results'}.get(self.lst_kind, 'mode_ring'))
        key = {'SPLASH': 'mode_normal', 'NORMAL': 'mode_nav', 'INSERT': 'mode_normal',
               'SEARCH': 'mode_search', 'CMD': 'mode_cmd', 'MENU': 'mode_menu',
               'OPEN': 'mode_open', 'SETTINGS': 'mode_settings', 'JOB': 'mode_job',
               'DROP': 'mode_menu', 'PALETTE': 'mode_palette'}[self.mode]
        return t(key)

    def clamp(self, insert=None):
        if insert is None:
            insert = self.mode == 'INSERT'
        b = self.b
        b.cur = max(0, min(b.cur, len(b.lines) - 1))
        last = len(b.lines[b.cur]) if insert else max(0, len(b.lines[b.cur]) - 1)
        b.cc = max(0, min(b.cc, last))

    def goto(self, i):
        self.b.cur = max(0, min(i, len(self.b.lines) - 1))
        self.clamp()

    def follow(self):
        b = self.b
        wrap = self.opts['wrap']
        if b.cur < b.top:
            b.top = b.cur
        elif b.cur > b.top + 2 * self.rows + 5:
            b.top = max(0, b.cur - self.rows // 2)
        so = min(self.opts.get('scrolloff', 0), (self.rows - 1) // 2)
        if b.cur - so < b.top:
            b.top = max(0, b.cur - so)
        elif not wrap and b.cur > b.top + self.rows - 1 - so:
            b.top = max(0, b.cur - (self.rows - 1 - so))
        total = sum(b.rowcount(i, self.textw, wrap) for i in range(b.top, b.cur + 1))
        while total > self.rows and b.top < b.cur:
            total -= b.rowcount(b.top, self.textw, wrap)
            b.top += 1
        if wrap:
            b.left = 0
        else:
            if b.cc < b.left:
                b.left = b.cc
            elif b.cc >= b.left + self.textw:
                b.left = b.cc - self.textw + 1

    def scroll(self, delta):
        b = self.b
        b.top = max(0, min(len(b.lines) - 1, b.top + delta))
        if b.cur < b.top:
            self.goto(b.top)
        elif b.cur > b.top + self.rows - 1:
            self.goto(b.top + self.rows - 1)

    # ---- çizim

    _inner = None
    _inner_key = None

    def draw(self):
        real = self.scr
        self.frame_off = (0, 0)
        H, W = real.getmaxyx()
        self.height, self.width = H, W
        if H >= 16 and W >= 70 and self.ide_on():
            self.draw_framed(real, H, W)
        else:
            self.draw_inner()

    def draw_framed(self, real, H, W):
        """Code + playground: the editor lives in its own rounded window with a title bar."""
        real.erase()
        y0, x0, y1, x1 = 1, 2, H - 2, W - 3
        acc = self.colors.style('accent') | curses.A_BOLD
        ln = self.colors.style('accent')
        self.put(y0, x0, '╭' + '─' * (x1 - x0 - 1) + '╮', ln)
        for yy in range(y0 + 1, y1):
            self.put(yy, x0, '│', ln)
            self.put(yy, x1, '│', ln)
        self.put(y1, x0, '╰' + '─' * (x1 - x0 - 1) + '╯', ln)
        for k, name in enumerate(('num', 'kw', 'str')):
            self.put(y0, x0 + 2 + k * 2, '●', self.colors.style(name) | curses.A_BOLD)
        self.put(y0, x0 + 10, f" Code + · {os.path.basename(PLAYGROUND)} ", acc)
        real.noutrefresh()
        ih, iw = y1 - y0 - 1, x1 - x0 - 1
        key = (ih, iw, y0 + 1, x0 + 1)
        if self._inner is None or self._inner_key != key:
            self._inner = curses.newwin(ih, iw, y0 + 1, x0 + 1)
            self._inner_key = key
        self.scr = self._inner
        self.frame_off = (y0 + 1, x0 + 1)
        try:
            self.draw_inner()
        finally:
            self.scr = real

    def draw_inner(self):
        scr = self.scr
        h, w = scr.getmaxyx()
        self.height, self.width = h, w
        ph = self.panel_height()
        self.ide = self.ide_on()
        self.ox = (min(SIDEW, w // 3) if self.opts.get('sidebar', True) else 0) if self.ide else 0
        self.oy = 2 if self.ide else 0
        self.rows = max(1, h - TOP - self.oy - 1 - ph)
        scr.erase()
        b = self.b
        n = len(b.lines)
        self.gw = max(7, len(str(n)) + 4) if (self.opts['number'] or self.opts['relativenumber']) else 0
        self.textw = max(1, w - self.gw - self.ox)
        self.follow()
        if self.mode == 'JOB':
            self.draw_job()
        elif self.mode == 'LIST':
            self.draw_list()
        elif self.mode == 'OPEN':
            self.draw_open()
        elif self.mode == 'SETTINGS':
            self.draw_settings()
        elif self.mode == 'SPLASH':
            self.draw_top()
            self.draw_splash()
        else:
            self.draw_top()
            self.draw_text()
            if ph:
                self.draw_panel(h - 1 - ph, ph)
            if self.ide:
                self.draw_ide_chrome()
                self.draw_completion()
            if self.mode == 'DROP':
                self.draw_dropdown()
            elif self.mode == 'PALETTE':
                self.draw_palette()
        self.draw_status(h - 1)
        if self.help:
            self.draw_box([(l, self.colors.style('accent') | curses.A_BOLD if i == 0 else 0)
                           for i, l in enumerate(HELP.get(SETTINGS['lang'], HELP['en']))])
        if self.mode == 'MENU':
            self.draw_menu()
        self.place_cursor()
        scr.refresh()

    def draw_top(self):
        if self.opts.get('menubar', True):
            return self.draw_menubar()
        b = self.b
        w = self.width
        acc = self.colors.style('accent') | curses.A_BOLD
        if self.ide:
            self.put(0, 0, ' ' * w, 0)
            self.put(0, 1, 'nview', acc)
            where = os.path.basename(os.path.dirname(os.path.abspath(b.path))) if b.path else os.path.basename(os.getcwd())
            title = f"{b.bufname()}{' ●' if b.modified else ''} — {where}"
            self.put(0, max(9, (w - len(title)) // 2), title, self.colors.style('com'))
            self.put(0, max(0, w - len(VERSION) - 3), f'v{VERSION}', self.colors.style('com'))
            return
        self.put(0, 0, ' ' * w, 0)
        self.put(0, 1, 'nview', acc)
        mod = (' ' + t('mod')) if b.modified else ''
        self.put(0, 7, f'v{VERSION} | {b.bufname()}{mod}', self.colors.style('com'))
        right = f'{b.lang[0]}  ·  UTF-8  ·  LF    Ln {b.cur + 1}, Col {b.cc + 1} '
        self.put(0, max(0, w - len(right)), right, acc)

    def draw_text(self):
        b = self.b
        o = self.opts
        wrap = o['wrap']
        y = 0
        self.cur_pos = None
        self.rowmap = {}
        i = b.top
        n = len(b.lines)
        tilde = self.colors.style('tilde')
        com = self.colors.style('com')
        band = self.colors.cursor_bg() if o['cursorline'] else -1
        self.match = find_bracket(b) if o.get('bracketmatch') else None
        self.para = para_bounds(b) if o.get('focus') else None
        ts = max(1, o.get('tabsize', 4))
        ruler = o.get('ruler', 0)
        while y < self.rows and i < n:
            cur = i == b.cur
            line = b.lines[i]
            text = line + ' '
            attrs = self.line_attrs(i)
            rc = b.rowcount(i, self.textw, wrap)
            indent = len(line) - len(line.lstrip(' '))
            for k in range(rc):
                if y >= self.rows:
                    break
                st = k * self.textw if wrap else b.left
                seg = list(text[st:st + self.textw])
                sa = list(attrs[st:st + self.textw])
                base = self.colors.style('text', band if cur else -1)
                while len(seg) < self.textw:
                    seg.append(' ')
                    sa.append(base)
                if cur:
                    self.put(TOP + self.oy + y, self.ox, ' ' * (self.width - self.ox), self.colors.style('text', band))
                if self.gw:
                    if k == 0:
                        self.put(TOP + self.oy + y, self.ox, self.numlabel(i),
                                 self.colors.style('lncur' if cur else 'ln', band if cur else -1))
                    self.put(TOP + self.oy + y, self.ox + self.gw - 1, '│', self.colors.style('ln'))
                for j in range(len(seg)):
                    idx = st + j
                    if idx >= len(line):
                        continue
                    if line[idx] == ' ':
                        if o.get('showws'):
                            seg[j], sa[j] = '·', com
                        elif o.get('indentguide') and idx < indent and idx % ts == 0 and idx > 0:
                            seg[j], sa[j] = '┊', com
                if ruler:
                    j = ruler - 1 - st
                    if 0 <= j < len(seg) and seg[j] == ' ':
                        seg[j], sa[j] = '│', com
                self.put_runs(TOP + self.oy + y, self.ox + self.gw, ''.join(seg), sa)
                self.rowmap[TOP + self.oy + y] = (i, st)
                if cur and k == (b.cc // self.textw if wrap else 0):
                    self.cur_pos = (TOP + self.oy + y, self.ox + self.gw + ((b.cc % self.textw) if wrap else b.cc - b.left))
                y += 1
            i += 1
        while y < self.rows:
            if self.gw:
                self.put(TOP + self.oy + y, self.ox + self.gw - 1, '│', self.colors.style('ln'))
            self.put(TOP + self.oy + y, self.ox, '~', tilde)
            y += 1

    def draw_splash(self):
        h, w = self.height, self.width
        acc = self.colors.style('accent') | curses.A_BOLD
        text = self.colors.style('text')
        com = self.colors.style('com')
        sel_attr = curses.A_REVERSE | curses.A_BOLD
        items = [(t('sp_' + a), hint) for a, hint in SPLASH_ITEMS]
        bw = max(len(l) for l, _ in items) + 16
        wide = w >= ART_W + 2
        art = ART if wide else ['nview ']
        txt_w = ART_TXT_W if wide else 6
        cur_w = ART_CUR_W if wide else 1
        aw = txt_w + cur_w
        total = len(art) + 1 + 1 + 1 + len(items) + 3
        y = max(TOP, (h - total) // 2)
        x0 = max(0, (w - aw) // 2)
        blink = int(time.monotonic() * 2) % 2 == 0
        cur_attr = self.colors.style('str') | curses.A_BOLD
        for row in art:
            self.put(y, x0, row[:txt_w], acc)
            if blink:
                self.put(y, x0 + txt_w, '█' * cur_w, cur_attr)
            y += 1
        y += 1
        sub = t('subtitle')
        self.put(y, max(0, (w - len(sub)) // 2), sub, text)
        y += 1
        self.put(y, x0, '─' * aw, acc)
        y += 2
        xb = max(0, (w - bw) // 2)
        for k, (label, hint) in enumerate(items):
            sel = k == self.sp_idx
            attr = sel_attr if sel else text
            self.put(y, xb, ' ' * bw, attr)
            self.put(y, xb + 2, label, attr)
            self.put(y, xb + bw - len(hint) - 2, hint, attr if sel else com)
            y += 1
        y += 2
        hint = t('sp_hint')
        self.put(y, max(0, (w - len(hint)) // 2), hint, com)

    # ---- IDE layout (tabs, breadcrumb, explorer, completion popup, terminal panel, status bar)

    def ide_on(self):
        return bool(self.opts.get('ide', True) and self.mode in ('NORMAL', 'INSERT', 'SEARCH', 'CMD', 'MENU', 'DROP', 'PALETTE')
                    and in_playground(self.b.path) and self.b.lang[0] not in ('text', 'markdown')
                    and getattr(self, 'width', 0) >= 60 and getattr(self, 'height', 0) >= 12)

    def side_base(self):
        if self.side_dir and os.path.isdir(self.side_dir):
            return self.side_dir
        b = self.b
        return os.path.dirname(os.path.abspath(b.path)) if b.path else os.getcwd()

    def side_entries(self):
        base = self.side_base()
        now = time.monotonic()
        ts, d, ents = self._side_cache
        if d == base and now - ts < 2:
            return ents
        dirs, files = [], []
        try:
            for e in os.scandir(base):
                if e.name.startswith('.'):
                    continue
                (dirs if e.is_dir() else files).append(e)
        except OSError:
            pass
        key = lambda e: e.name.lower()
        ents = [('..', os.path.dirname(base), True)]
        ents += [(e.name + '/', e.path, True) for e in sorted(dirs, key=key)]
        ents += [(e.name, e.path, False) for e in sorted(files, key=key)]
        self._side_cache = (now, base, ents)
        return ents

    def ide_global_key(self, code):
        if code == curses.KEY_F10:
            self.gui_menu(0)
            return True
        if code == curses.KEY_F4:
            self.open_palette()
            return True
        if code == curses.KEY_F2:
            self.opts['sidebar'] = not self.opts.get('sidebar', True)
            if not self.opts['sidebar']:
                self.side_focus = False
            return True
        if code == curses.KEY_F3:
            if not self.ide_on():
                return False
            self.opts['sidebar'] = True
            self.side_focus = not self.side_focus
            self.comp = None
            return True
        return False

    def side_key(self, code, ch):
        ents = self.side_entries()
        n = len(ents)
        if code in (27, curses.KEY_F3):
            self.side_focus = False
        elif ch == 'j' or code == curses.KEY_DOWN:
            self.side_idx = min(n - 1, self.side_idx + 1)
        elif ch == 'k' or code == curses.KEY_UP:
            self.side_idx = max(0, self.side_idx - 1)
        elif ch in ('h', '-') or code in (curses.KEY_LEFT, 8, 127, curses.KEY_BACKSPACE):
            self.side_dir = os.path.dirname(self.side_base())
            self.side_idx = 0
        elif code in (10, 13, curses.KEY_ENTER) or ch == 'l' or code == curses.KEY_RIGHT:
            name, path, isdir = ents[min(self.side_idx, n - 1)]
            if isdir:
                self.side_dir = path
                self.side_idx = 0
            else:
                self.side_focus = False
                self.open_path(path)
        return True

    def draw_ide_chrome(self):
        h, w = self.height, self.width
        ox = self.ox
        b = self.b
        acc = self.colors.style('accent') | curses.A_BOLD
        com = self.colors.style('com')
        text = self.colors.style('text')
        ln = self.colors.style('ln')
        act = self.colors.style('text', self.colors.cursor_bg()) | curses.A_BOLD
        self.hit_tabs = []
        self.side_rows = {}
        # tab bar
        y = TOP
        self.put(y, ox, ' ' * (w - ox), com)
        x = ox
        for k, bf in enumerate(self.bufs):
            name = (bf.bufname() if hasattr(bf, 'bufname') else (bf.name or '[New]'))[:18]
            badge = bf.lang[0][:2].upper()
            dot = ' ●' if bf.modified else '  '
            label = f' {name}{dot} '
            if x + len(badge) + len(label) + 1 > w:
                break
            on = k == self.bi
            tab_x0 = x
            self.put(y, x, ' ' + badge, (acc if on else com) | (curses.A_REVERSE if False else 0))
            self.put(y, x + len(badge) + 1, label, act if on else com)
            x += len(badge) + 1 + len(label)
            self.put(y, x, '│', ln)
            self.hit_tabs.append((tab_x0, x, k))
            x += 1
        # breadcrumb
        y = TOP + 1
        self.put(y, ox, ' ' * (w - ox), com)
        if b.path:
            rel = os.path.relpath(os.path.abspath(b.path), os.getcwd())
            parts = [p for p in rel.split(os.sep) if p != '..'] or [b.name]
        else:
            parts = [b.name or '[New]']
        x = ox + 1
        for k, part in enumerate(parts[-4:]):
            self.put(y, x, part, text if k == len(parts[-4:]) - 1 else com)
            x += len(part)
            self.put(y, x, ' › ', com)
            x += 3
        sym = current_symbol(b)
        if sym:
            self.put(y, x, 'ƒ ' + sym, acc)
        # explorer
        if ox:
            for yy in range(TOP, h - 1):
                self.put(yy, 0, ' ' * (ox - 1), 0)
                self.put(yy, ox - 1, '│', ln)
            self.put(TOP, 1, t('explorer'), acc if self.side_focus else com | curses.A_BOLD)
            base = self.side_base()
            self.put(TOP + 1, 1, '▾ ' + (os.path.basename(base) or base).upper()[:ox - 5], text | curses.A_BOLD)
            ents = self.side_entries()
            avail = max(1, h - 1 - (TOP + 2))
            self.side_idx = max(0, min(self.side_idx, len(ents) - 1))
            top = max(0, min(self.side_idx - avail + 1, len(ents) - avail)) if self.side_idx >= avail else 0
            here = os.path.abspath(b.path) if b.path else None
            for k, (name, path, isdir) in enumerate(ents[top:top + avail]):
                label = ('▸ ' if isdir else '  ') + name
                label = label[:ox - 3].ljust(ox - 3)
                attr = acc if isdir else text
                if here and os.path.abspath(path) == here:
                    attr = acc
                if self.side_focus and top + k == self.side_idx:
                    attr = attr | curses.A_REVERSE
                self.put(TOP + 2 + k, 1, label, attr)
                self.side_rows[TOP + 2 + k] = top + k

    def make_comp(self):
        b = self.b
        line = b.lines[b.cur]
        m = re.search(r'[A-Za-z_][A-Za-z0-9_]*$', line[:b.cc])
        if not m:
            return None
        pre = m.group(0)
        low = pre.lower()
        kws = set(b.lang[2].split()) if isinstance(b.lang[2], str) else set(b.lang[2] or ())
        freq = {}
        for bf in self.bufs[:8]:
            for l in bf.lines[:20000]:
                for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}', l):
                    if w != pre and w.lower().startswith(low):
                        freq[w] = freq.get(w, 0) + 1
        for w in kws:
            if w != pre and w.lower().startswith(low):
                freq.setdefault(w, 0)
        words = sorted(freq, key=lambda w: (0 if w in kws else 1, -freq[w], w.lower()))[:8]
        if not words:
            return None
        return {'items': [(w, 'keyword' if w in kws else 'word') for w in words], 'idx': 0, 'pre': pre}

    def accept_comp(self):
        b = self.b
        c = self.comp
        word = c['items'][c['idx']][0]
        line = b.lines[b.cur]
        start = b.cc - len(c['pre'])
        b.snapshot()
        b.lines[b.cur] = line[:start] + word + line[b.cc:]
        b.cc = start + len(word)
        b.touch()
        self.comp = None

    def draw_completion(self):
        c = self.comp
        if not c or self.mode != 'INSERT' or not self.cur_pos:
            return
        cy, cx = self.cur_pos
        items = c['items']
        pre = c['pre']
        wd = max(len(w) for w, _ in items)
        bw = wd + 14
        x = max(self.ox, min(cx - len(pre) - 3, self.width - bw))
        bottom = TOP + self.oy + self.rows
        y = cy + 1
        if y + len(items) > bottom:
            y = max(TOP + self.oy, cy - len(items))
        base = self.colors.style('text', self.colors.cursor_bg())
        acc = self.colors.style('accent') | curses.A_BOLD
        com = self.colors.style('com', self.colors.cursor_bg())
        for k, (w, kind) in enumerate(items):
            sel = k == c['idx']
            glyph = '◆' if kind == 'keyword' else '▫'
            row_attr = (self.colors.style('accent') | curses.A_REVERSE | curses.A_BOLD) if sel else base
            self.put(y + k, x, ' ' * bw, row_attr)
            self.put(y + k, x + 1, glyph, row_attr)
            self.put(y + k, x + 3, w, row_attr)
            if not sel:
                self.put(y + k, x + 3, w[:len(pre)], acc)
            self.put(y + k, x + bw - len(kind) - 1, kind, row_attr if sel else com)

    def draw_panel_ide(self, y0, ph):
        w, ox = self.width, self.ox
        pn = self.panel
        acc = self.colors.style('accent') | curses.A_BOLD
        com = self.colors.style('com')
        text = self.colors.style('text')
        ln = self.colors.style('ln')
        band = self.colors.style('text', self.colors.cursor_bg())
        self.put(y0, ox, '─' * (w - ox), ln)
        self.put(y0 + 1, ox + 2, ' ' + t('terminal') + ' ', acc | curses.A_UNDERLINE)
        self.put(y0 + 1, ox + 4 + len(t('terminal')) + 3, '···', com)
        task = f" 2: Task - {pn.get('cmd', 'run')} ▾ "
        tx = ox + 4 + len(t('terminal')) + 9
        self.put(y0 + 1, tx, task, band)
        right = '+  ▯  ⌃  ✕ '
        self.put(y0 + 1, max(tx + len(task) + 1, w - len(right)), right, com)
        has_badge = pn.get('ok') is not None
        avail = max(1, ph - 2 - (2 if has_badge else 0))
        for k, line in enumerate(pn['lines'][-avail:]):
            bad = re.search(r'error|traceback|exception|fatal|warning', line, re.I)
            self.put(y0 + 2 + k, ox + 4, line, self.colors.style('num') if bad else text)
        if has_badge:
            yb = y0 + ph - 1
            if pn['ok']:
                self.put(yb, ox + 4, ' DONE ', self.colors.style('str') | curses.A_REVERSE | curses.A_BOLD)
                self.put(yb, ox + 11, f"Finished in {pn.get('ms', 0)}ms", self.colors.style('str'))
            else:
                self.put(yb, ox + 4, ' FAIL ', self.colors.style('num') | curses.A_REVERSE | curses.A_BOLD)
                self.put(yb, ox + 11, f"exit code {pn.get('code', '-')}", self.colors.style('num'))
            stamp = time.strftime('%I:%M:%S %p')
            self.put(yb, max(ox + 30, w - len(stamp) - 3), stamp, com)

    def draw_status_ide(self, y):
        b = self.b
        w = self.width
        bar = self.colors.on_bar('text')
        acc = self.colors.on_bar('accent', True)
        com = self.colors.on_bar('com')
        self.put(y, 0, ' ' * w, bar)
        cell = f' {self.mode_label()} '
        self.put(y, 0, cell, self.colors.accent_cell())
        x = len(cell) + 1
        right = (f"Ln {b.cur + 1}, Col {b.cc + 1}   {t('spaces')}: {self.opts.get('tabsize', 4)}   "
                 f"UTF-8   LF   {LANG_LABEL.get(b.lang[0], b.lang[0].capitalize())} ")
        xr = max(x + 1, w - len(right))
        if self.mode in ('SEARCH', 'CMD'):
            prefix = self.prefix if self.mode == 'SEARCH' else ':'
            self.put(y, x, prefix + self.buf + '_', bar)
            if self.msg:
                self.put(y, x + len(prefix + self.buf) + 3, self.msg[:max(0, xr - x - len(self.buf) - 6)], bar)
        else:
            br = git_branch(b.path)
            if br:
                label = f' ⎇ {br} '
                self.put(y, x, label, acc)
                x += len(label)
            e, wn, eln = diagnostics(b)
            label = f' ✖ {e}  ▲ {wn} '
            self.put(y, x, label, bar)
            x += len(label)
            if e and eln:
                label = f'(Ln {eln}) '
                self.put(y, x, label, com)
                x += len(label)
            if self.msg:
                self.put(y, x + 1, self.msg[:max(0, xr - x - 3)], bar)
        self.put(y, xr, right, acc)

    def draw_status(self, y):
        if self.ide and self.mode in ('NORMAL', 'INSERT', 'SEARCH', 'CMD', 'MENU', 'DROP', 'PALETTE'):
            return self.draw_status_ide(y)
        b = self.b
        w = self.width
        n = len(b.lines)
        rows = self.rows
        pct = '100%' if n <= rows else f'{min(100, b.top * 100 // max(1, n - rows))}%'
        bar = self.colors.on_bar('text')
        acc = self.colors.on_bar('accent', True)
        com = self.colors.on_bar('com')
        self.put(y, 0, ' ' * w, bar)
        cell = f' {self.mode_label()} '
        self.put(y, 0, cell, self.colors.accent_cell())
        x = len(cell) + 2
        # sağ blok önce yerleşir; sol taraf ona girmez
        wc = b.word_count()
        goal = self.opts.get('wordgoal', 0)
        goal_part = ''
        if goal:
            net = max(0, wc - b.base_words)
            filled = min(10, net * 10 // goal)
            goal_part = '█' * filled + '░' * (10 - filled) + f' {net}/{goal}   '
        pos = f'{wc} {t("words")}   {goal_part}{b.cur + 1}:{b.cc + 1} '
        xp = w - len(pos) - len(pct) - 5
        if self.mode == 'OPEN' and self.ob_prompt:
            self.put(y, x, t('prompt_open') + self.buf + '_', bar)
        elif self.mode in ('SEARCH', 'CMD'):
            prefix = self.prefix if self.mode == 'SEARCH' else ':'
            self.put(y, x, prefix + self.buf + '_', bar)
            if self.msg:
                self.put(y, x + len(prefix + self.buf) + 3, self.msg, bar)
        elif self.msg:
            self.put(y, x, self.msg[:max(0, xp - x - 2)], bar)
        else:
            items = self.hint_items() if self.opts.get('statushints', True) else []
            for key, label in items:
                if x + len(key) + 1 + len(label) > xp - 4:
                    break
                self.put(y, x, key, acc)
                x += len(key) + 1
                self.put(y, x, label, bar)
                x += len(label)
                self.put(y, x, '  │  ', com)
                x += 5
        self.put(y, xp, '│', com)
        self.put(y, xp + 2, pct, acc)
        self.put(y, max(0, w - len(pos)), pos, acc)

    def place_cursor(self):
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    def draw_box(self, rows):
        h, w = self.height, self.width
        inner = max((len(text) for text, _ in rows), default=0)
        bw = min(w - 2, inner + 6)
        bh = min(h - 2, len(rows) + 2)
        x0 = max(0, (w - bw) // 2)
        y0 = max(0, (h - bh) // 2)
        acc = self.colors.style('accent')
        self.put(y0, x0, '╭' + '─' * (bw - 2) + '╮', acc)
        for r in range(1, bh - 1):
            self.put(y0 + r, x0, '│' + ' ' * (bw - 2) + '│', acc)
        self.put(y0 + bh - 1, x0, '╰' + '─' * (bw - 2) + '╯', acc)
        for r, (text, attr) in enumerate(rows[:bh - 2]):
            self.put(y0 + 1 + r, x0 + 3, text[:bw - 6], attr)

    def draw_menu(self):
        acc = self.colors.style('accent') | curses.A_BOLD
        rows = [(t('menu_title'), acc), ('', 0)]
        items = [
            (t('menu_theme'), THEMES[SETTINGS['theme']]['label']),
            (t('menu_lang'), LANG_NAMES[SETTINGS['lang']]),
        ]
        for idx, (label, val) in enumerate(items):
            attr = curses.A_REVERSE if idx == self.menu_idx else self.colors.style('text')
            rows.append((f'  {label:<8} {val}  ', attr))
        rows += [('', 0), (t('menu_foot'), self.colors.style('com'))]
        self.draw_box(rows)

    # ---- dosya ve ayar ekranları

    def _remember(self):
        if self.mode in ('SPLASH', 'NORMAL', 'INSERT'):
            self.screen_back = self.mode

    def enter_open(self):
        self._remember()
        self.mode = 'OPEN'
        self.ob_prompt = False
        self.buf = ''
        self.ob_load()

    def enter_settings(self):
        self._remember()
        self.mode = 'SETTINGS'
        self.ob_prompt = False
        self.buf = ''

    def leave_screen(self):
        self.pick_box = None
        self.mode = self.screen_back if self.screen_back in ('SPLASH', 'NORMAL', 'INSERT') else 'INSERT'
        self.ob_prompt = False
        self.buf = ''

    def body_top(self):
        return 8 if self.height >= 24 else 4

    def ob_geom(self):
        ly = self.body_top() + 2
        return ly, max(1, (self.height - 1) - ly)

    def ob_load(self):
        d = self.ob_dir
        try:
            names = os.listdir(d)
        except OSError:
            self.msg = t('cant_read', path=d)
            names = []
        if not self.ob_hidden:
            names = [n for n in names if not n.startswith('.')]
        dirs, files = [], []
        for n in names:
            p = os.path.join(d, n)
            try:
                if os.path.isdir(p):
                    dirs.append((n, p))
                else:
                    files.append((n, p, os.path.getsize(p)))
            except OSError:
                continue
        if self.pick_box:
            exts = self.pick_exts()
            files = [f for f in files if os.path.splitext(f[0])[1].lower() in exts]
        dirs.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())
        self.ob_entries = []
        parent = os.path.dirname(d)
        if parent and parent != d:
            self.ob_entries.append(('..', True, None, parent))
        self.ob_entries += [(n, True, None, p) for n, p in dirs]
        self.ob_entries += [(n, False, s, p) for n, p, s in files]
        self.ob_idx = 0
        self.ob_top = 0

    def ob_up(self):
        parent = os.path.dirname(self.ob_dir)
        if parent and parent != self.ob_dir:
            self.ob_dir = parent
            self.ob_load()

    def ob_activate(self):
        if not self.ob_entries:
            return
        _, is_dir, _, path = self.ob_entries[self.ob_idx]
        if is_dir:
            self.ob_dir = path
            self.ob_load()
        elif self.pick_box:
            self.install_package_in_box(path, self.pick_box if isinstance(self.pick_box, dict) else None)
        else:
            self.open_path(path)

    def ob_follow(self):
        lh = self.ob_geom()[1]
        if self.ob_idx < self.ob_top:
            self.ob_top = self.ob_idx
        elif self.ob_idx >= self.ob_top + lh:
            self.ob_top = self.ob_idx - lh + 1

    def open_path(self, path):
        full = os.path.abspath(os.path.expanduser(path))
        if os.path.isdir(full):
            self.ob_dir = full
            self.ob_load()
            self.mode = 'OPEN'
            return
        self.open_file(full)
        if self.mode in ('OPEN', 'SPLASH', 'NORMAL'):
            self.mode = 'INSERT'

    def open_key(self, code, ch):
        if self.ob_prompt:
            if code == 27:
                self.ob_prompt = False
                self.buf = ''
            elif code in (10, 13, curses.KEY_ENTER):
                path = self.buf.strip()
                self.buf = ''
                self.ob_prompt = False
                if path:
                    self.open_path(path)
            elif code in (8, 127, curses.KEY_BACKSPACE):
                self.buf = self.buf[:-1]
            elif ch and ch.isprintable():
                self.buf += ch
            return True
        n = len(self.ob_entries)
        if code == 27 or ch == 'q':
            self.leave_screen()
            return True
        if code == 9:
            self.mode = 'SETTINGS'
            return True
        if (ch == 'j' or code == curses.KEY_DOWN) and n:
            self.ob_idx = min(n - 1, self.ob_idx + 1)
        elif (ch == 'k' or code == curses.KEY_UP) and n:
            self.ob_idx = max(0, self.ob_idx - 1)
        elif ch == 'g':
            self.ob_idx = 0
        elif ch == 'G' and n:
            self.ob_idx = n - 1
        elif ch == '-' or ch == 'h' or code in (8, 127, curses.KEY_BACKSPACE, curses.KEY_LEFT):
            self.ob_up()
        elif code in (10, 13, curses.KEY_ENTER) or ch == 'l' or code == curses.KEY_RIGHT:
            self.ob_activate()
        elif ch == '.':
            self.ob_hidden = not self.ob_hidden
            self.ob_load()
            self.msg = t('hidden_on') if self.ob_hidden else t('hidden_off')
        elif ch == 'b' and n:
            _, is_dir, _, path = self.ob_entries[self.ob_idx]
            if not is_dir:
                self.install_package_in_box(path)   # box is picked automatically by extension
            else:
                self.msg = t('box_notpkg')
        elif ch == '/' or ch == ':':
            self.ob_prompt = True
            self.buf = ''
        self.ob_follow()
        return True

    def change_setting(self, key, d):
        if key == 'theme':
            names = list(THEMES)
            i = names.index(SETTINGS['theme'])
            SETTINGS['theme'] = names[(i + d) % len(names)]
            self.colors.reset()
            self.msg = t('theme_set', name=THEMES[SETTINGS['theme']]['label'])
        elif key == 'lang':
            cycle_lang(d)
            self.msg = t('lang_set', name=LANG_NAMES[SETTINGS['lang']])
        elif key in CHOICES:
            choices = CHOICES[key]
            cur = choices.index(self.opts[key]) if self.opts[key] in choices else 0
            self.opts[key] = choices[(cur + d) % len(choices)]
            self.msg = t('st_' + key) + ': ' + self.setting_value(key)
        else:
            self.opts[key] = not self.opts[key]
            self.msg = t('st_' + key) + ': ' + self.setting_value(key)
        self.msg += '  ·  ' + persist(self.opts)

    def setting_value(self, key):
        if key == 'theme':
            return THEMES[SETTINGS['theme']]['label'].upper()
        if key == 'lang':
            return LANG_NAMES[SETTINGS['lang']].upper()
        if key == 'ruler' and not self.opts[key]:
            return t('off')
        if key in CHOICES:
            return str(self.opts[key])
        return t('on') if self.opts[key] else t('off')

    def settings_key(self, code, ch):
        if code == 27 or ch == 'q':
            self.leave_screen()
            return True
        if code == 9:
            self.mode = 'OPEN'
            return True
        if ch == 'j' or code == curses.KEY_DOWN:
            self.st_step(1)
        elif ch == 'k' or code == curses.KEY_UP:
            self.st_step(-1)
        elif code in (10, 13, curses.KEY_ENTER) or ch in (' ', 'l') or code == curses.KEY_RIGHT:
            self.change_setting(SETTING_ROWS[self.st_idx], 1)
        elif ch == 'h' or code == curses.KEY_LEFT:
            self.change_setting(SETTING_ROWS[self.st_idx], -1)
        elif ch == 'g':
            self.st_idx = next(i for i, r in enumerate(SETTING_ROWS) if not r.startswith('H:'))
        elif ch == 'G':
            self.st_idx = max(i for i, r in enumerate(SETTING_ROWS) if not r.startswith('H:'))
        self.st_follow()
        return True

    def hint_items(self):
        if self.mode == 'JOB':
            return [('Enter', t('l_open')), ('Esc', t('l_back'))] if self.install_hint_done() else [('Esc', t('l_back'))]
        if self.mode == 'LIST':
            act = {'timeline': t('l_restore'), 'lang': t('l_new'), 'boxmenu': t('l_open'), 'boxdistro': t('l_open'), 'boxlist': t('l_pkg')}.get(self.lst_kind, t('l_paste'))
            return [('j/k', t('l_select')), ('Enter', act), ('Esc', t('l_back'))]
        if self.mode == 'OPEN':
            return [('j/k', t('l_select')), ('Enter', t('l_install') if self.pick_box else t('l_open')), ('-', t('l_up')),
                    ('/', t('l_path')), ('.', t('l_hidden')), ('Tab', t('l_tab')), ('Esc', t('l_back'))]
        if self.mode == 'SETTINGS':
            return [('Enter', t('l_change')), ('h/l', t('l_value')),
                    ('Tab', t('l_file')), ('Esc', t('l_back'))]
        return [('^S', t('l_save')), ('^Q', t('l_quit')), ('^F', t('l_find')),
                ('^G', t('l_goto')), ('^/', t('l_search'))]

    def draw_tabs(self, active):
        w = self.width
        self.put(0, 0, ' ' * w, 0)
        x = 2
        for key, name in (('OPEN', 'tab_file'), ('SETTINGS', 'tab_settings')):
            label = f' {t(name)} '
            attr = self.colors.accent_cell() if active == key else self.colors.style('com')
            self.put(0, x, label, attr)
            x += len(label) + 2
        right = f'nview v{VERSION} · {VERSION_NAME} '
        self.put(0, max(0, w - len(right)), right, self.colors.style('com'))

    def draw_big(self, y, text, attr):
        rows = big_lines(text)
        x = max(0, (self.width - max(len(r) for r in rows)) // 2)
        for k, r in enumerate(rows):
            self.put(y + k, x, r, attr)

    def draw_title(self, text):
        acc = self.colors.style('accent') | curses.A_BOLD
        if self.height >= 24:
            self.draw_big(2, text, acc)
        else:
            self.put(2, 2, text, acc)

    def draw_open(self):
        w = self.width
        self.draw_tabs('OPEN')
        self.draw_title(t('tab_pick') if self.pick_box else t('tab_file'))
        com = self.colors.style('com')
        self.put(self.body_top(), 2, f"{t('dir')}: {self.ob_dir}", com)
        ly, lh = self.ob_geom()
        if not self.ob_entries:
            self.put(ly, 4, t('box_nopkgs') if self.pick_box else t('empty_dir'), com)
            return
        for k in range(self.ob_top, min(len(self.ob_entries), self.ob_top + lh)):
            name, is_dir, size, _ = self.ob_entries[k]
            y = ly + (k - self.ob_top)
            sel = k == self.ob_idx
            if sel:
                attr = curses.A_REVERSE | curses.A_BOLD
            elif is_dir:
                attr = self.colors.style('accent') | curses.A_BOLD
            else:
                attr = self.colors.style('text')
            self.put(y, 2, ' ' * (w - 4), attr)
            label = name + '/' if (is_dir and name != '..') else name
            self.put(y, 4, label, attr)
            if size is not None:
                s = human(size)
                self.put(y, max(0, w - 4 - len(s)), s, attr if sel else com)

    def draw_settings(self):
        w = self.width
        self.draw_tabs('SETTINGS')
        self.draw_title(t('title_settings'))
        ly, _ = self.ob_geom()
        lh = max(1, (self.height - 2) - ly)
        acc = self.colors.style('accent') | curses.A_BOLD
        for k in range(self.st_top, min(len(SETTING_ROWS), self.st_top + lh)):
            row = SETTING_ROWS[k]
            y = ly + (k - self.st_top)
            if row.startswith('H:'):
                label = '── ' + t(row[2:]) + ' '
                self.put(y, 2, label + '─' * max(0, w - 6 - len(label)), acc)
                continue
            sel = k == self.st_idx
            attr = curses.A_REVERSE | curses.A_BOLD if sel else self.colors.style('text')
            self.put(y, 2, ' ' * (w - 4), attr)
            self.put(y, 4, t('st_' + row), attr)
            val = self.setting_value(row)
            self.put(y, max(0, w - 4 - len(val)), val, attr)
        self.put(self.height - 2, 2, t('d_' + SETTING_ROWS[self.st_idx]), self.colors.style('com'))

    def splash_run(self, action):
        if action == 'new':
            self.new_buffer()
        elif action == 'open':
            self.enter_open()
        elif action == 'find':
            b = self.b
            if b.path is None and not b.modified and len(self.bufs) == 1 and b.lines == ['']:
                self.msg = t('find_nofile')
                self.enter_open()
                return True
            self.start_search('/')
        elif action == 'code':
            self.open_list('lang')
        elif action == 'box':
            self.open_list('boxmenu')
        elif action == 'settings':
            self.enter_settings()
        elif action == 'quit':
            return False
        return True

    def st_follow(self):
        ly, _ = self.ob_geom()
        lh = max(1, (self.height - 2) - ly)
        if self.st_idx < self.st_top:
            self.st_top = self.st_idx
        elif self.st_idx >= self.st_top + lh:
            self.st_top = self.st_idx - lh + 1

    def st_step(self, d):
        n = len(SETTING_ROWS)
        i = self.st_idx
        for _ in range(n):
            i = (i + d) % n
            if not SETTING_ROWS[i].startswith('H:'):
                break
        self.st_idx = i

    def start_search(self, prefix):
        self.prompt_back = 'INSERT'
        self.mode, self.prefix, self.buf = 'SEARCH', prefix, ''
        self.search_origin = (self.b.cur, self.b.cc)
        self.msg = ''

    def search_restore(self):
        if self.search_origin is not None:
            self.b.cur, self.b.cc = self.search_origin
            self.clamp()

    def count_matches(self, text):
        rx = re.compile(re.escape(text), re.I if self.opts['ignorecase'] else 0)
        return sum(len(rx.findall(line)) for line in self.b.lines)

    def live_search(self):
        """Yazarken imleci ilk eşleşmeye götürür; eşleşme sayısını gösterir."""
        self.search_restore()
        if not self.buf:
            self.msg = ''
            return
        self.search_fwd = self.prefix == '/'
        self.nohl = False
        if self.do_search(self.buf, self.search_fwd, inclusive=True):
            self.msg = t('matches', n=self.count_matches(self.buf))

    def search_done(self, text):
        origin = self.search_origin
        self.search_origin = None
        self.search_restore()
        if origin is None:
            self.clamp()
        if text:
            self.search = text
            self.search_fwd = self.prefix == '/'
        if not self.search:
            self.msg = t('no_search')
            return
        self.nohl = False
        self.do_search(self.search, self.search_fwd, inclusive=bool(text))

    # ---- zaman çizelgesi ve pano listesi

    def push_ring(self, text):
        if not text:
            return
        self.ring = [text] + [x for x in self.ring if x != text][:RING_MAX - 1]

    def open_list(self, kind):
        self._remember()
        self.lst_kind = kind
        self.lst_idx = 0
        self.lst_top = 0
        if kind in BOX_KINDS:
            self.lst_items = self.box_items(kind)
        elif kind == 'lang':
            self.lst_items = [(spec['label'], key) for key, spec in LANG_CATALOG.items()]
        elif kind == 'xres':
            self.lst_items = list(self.xres_items)
        elif kind == 'timeline':
            snaps = list_snapshots(self.b.path) if self.b.path else []
            self.lst_items = [
                (f'{stamp}   {n} ln   {delta:+d}', path)
                for path, stamp, n, delta in snaps
            ]
        else:
            self.lst_items = []
            for text in self.ring:
                lines = text.split('\n')
                head = lines[0].strip()[:44] or '·'
                self.lst_items.append((f'{head}   ({len(lines)})', text))
        self.mode = 'LIST'

    def lst_follow(self):
        ly, _ = self.ob_geom()
        lh = max(1, (self.height - 2) - ly)
        if self.lst_idx < self.lst_top:
            self.lst_top = self.lst_idx
        elif self.lst_idx >= self.lst_top + lh:
            self.lst_top = self.lst_idx - lh + 1

    def list_key(self, code, ch):
        n = len(self.lst_items)
        if code == 27 or ch == 'q':
            self.leave_screen()
            return True
        if n and (ch == 'j' or code == curses.KEY_DOWN):
            self.lst_idx = min(n - 1, self.lst_idx + 1)
        elif n and (ch == 'k' or code == curses.KEY_UP):
            self.lst_idx = max(0, self.lst_idx - 1)
        elif n and ch == 'g':
            self.lst_idx = 0
        elif n and ch == 'G':
            self.lst_idx = n - 1
        elif n and code in (10, 13, curses.KEY_ENTER) and self.lst_kind in BOX_KINDS:
            self.box_select(self.lst_items[self.lst_idx][1])
            self.lst_follow()
            return True
        elif n and code in (10, 13, curses.KEY_ENTER):
            payload = self.lst_items[self.lst_idx][1]
            self.leave_screen()
            if self.lst_kind == 'lang':
                self.new_code_buffer(payload)
            elif self.lst_kind == 'timeline':
                self.restore_snapshot(payload)
            elif self.lst_kind == 'xres':
                self.xjump(payload)
            else:
                self.paste_text(payload)
            self.lst_follow()
            return True
        self.lst_follow()
        return True

    def restore_snapshot(self, path):
        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
        except OSError:
            self.msg = t('nofile', path=path)
            return
        b = self.b
        b.snapshot()
        b.set_text(text)
        b.touch()
        self.clamp()
        self.msg = t('restored')

    def paste_text(self, text):
        b = self.b
        b.snapshot()
        new = text.split('\n')
        at = b.cur + 1
        b.lines[at:at] = new
        b.cur = at
        b.cc = 0
        b.touch()
        self.msg = t('pasted', n=len(new))

    def draw_list(self):
        w = self.width
        com = self.colors.style('com')
        self.draw_title(self.xres_title.upper() if self.lst_kind == 'xres' else t({'timeline': 'tab_timeline', 'lang': 'tab_lang', 'boxmenu': 'tab_box', 'boxdistro': 'tab_box', 'boxlist': 'tab_box'}.get(self.lst_kind, 'tab_ring')))
        ly, _ = self.ob_geom()
        lh = max(1, (self.height - 2) - ly)
        if not self.lst_items:
            self.put(ly, 4, t('list_empty'), com)
            return
        for k in range(self.lst_top, min(len(self.lst_items), self.lst_top + lh)):
            label = self.lst_items[k][0]
            y = ly + (k - self.lst_top)
            sel = k == self.lst_idx
            attr = curses.A_REVERSE | curses.A_BOLD if sel else self.colors.style('text')
            self.put(y, 2, ' ' * (w - 4), attr)
            self.put(y, 4, label, attr)

    # ---- kod çalışma alanı

    def new_code_buffer(self, key):
        spec = LANG_CATALOG[key]
        d = PLAYGROUND
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            d = os.getcwd()
        n = 1
        path = os.path.join(d, 'new' + spec['ext'])
        while os.path.exists(path):
            n += 1
            path = os.path.join(d, f"new{n}" + spec['ext'])
        nb = Buffer(path)
        if spec['template']:
            nb.set_text(spec['template'])
            nb.touch()
        nb.cur = len(nb.lines) - 1
        nb.cc = len(nb.lines[nb.cur])
        if len(self.bufs) == 1 and self.bufs[0].path is None and not self.bufs[0].modified:
            self.bufs = []
        self.bufs.append(nb)
        self.bi = len(self.bufs) - 1
        self.mode = 'INSERT'
        self.msg = t('new_code', lang=spec['label'], name=os.path.basename(path))

    def run_code(self):
        b = self.b
        if b.path is None:
            self.msg = t('noname_write')
            return
        if b.modified or not os.path.exists(b.path):
            if not self.write():
                return
        argv = run_argv(b.lang[0], os.path.abspath(b.path))
        if argv is None:
            self.msg = t('no_runner', lang=b.lang[0])
            return
        name = os.path.basename(b.path)
        t0 = time.monotonic()
        try:
            res = subprocess.run(argv, capture_output=True, text=True, timeout=10,
                                 cwd=os.path.dirname(os.path.abspath(b.path)))
            code = str(res.returncode)
            text = res.stdout + res.stderr
            lines = text.rstrip('\n').split('\n') if text.strip() else [t('out_none')]
        except subprocess.TimeoutExpired:
            code = '-'
            lines = [t('out_timeout')]
        except OSError as e:
            code = '-'
            lines = [str(e)]
        self.panel = {'title': t('out_title', cmd=name, code=code), 'lines': lines, 'cmd': name,
                      'ok': code == '0', 'code': code, 'ms': int((time.monotonic() - t0) * 1000)}
        self.msg = t('ran')

    def toggle_panel(self):
        if self.panel:
            self.panel = None
        else:
            self.panel = {'title': t('out_empty_title'), 'lines': [t('out_hint')]}

    def panel_height(self):
        if not self.panel or self.mode not in ('NORMAL', 'INSERT'):
            return 0
        return min(12, max(6 if self.ide_on() else 4, self.height // 3))

    def draw_panel(self, y0, ph):
        if self.ide:
            return self.draw_panel_ide(y0, ph)
        w = self.width
        acc = self.colors.style('accent') | curses.A_BOLD
        text = self.colors.style('text')
        self.put(y0, 0, '─' * w, self.colors.style('ln'))
        self.put(y0, 2, ' ' + self.panel['title'] + ' ', acc)
        for k, line in enumerate(self.panel['lines'][-(ph - 1):]):
            self.put(y0 + 1 + k, 4, line, text)

    def dup_line(self):
        b = self.b
        b.snapshot()
        b.lines.insert(b.cur + 1, b.lines[b.cur])
        b.cur += 1
        b.touch()

    def del_line(self):
        b = self.b
        b.snapshot()
        chunk = b.delete_lines(1)
        self.push_ring('\n'.join(chunk))
        self.clamp(True)
        self.msg = t('deleted', n=len(chunk))

    # ---- N box: distrobox setup, box list and package install

    xres_title = ''
    xres_items = []
    ide = False
    ox = 0
    oy = 0
    cur_pos = None
    comp = None
    side_focus = False
    side_dir = None
    side_idx = 0
    _side_cache = (0, None, [])

    pick_box = None   # None: normal browser, True: pick a package (auto box), dict: pick for that box

    def box_items(self, kind):
        if kind == 'boxmenu':
            return [(t('box_install'), 'install'), (t('box_list'), 'list'), (t('box_pkg'), 'pkg')]
        boxes = list_boxes()
        if kind == 'boxlist':
            if boxes is None:
                self.msg = t('box_no_dbx')
                return []
            items = []
            for bx in boxes:
                up = bx['status'].lower().startswith('up')
                pkg = PKG_EXT.get(bx['family'], '-')
                items.append((f"{'●' if up else '○'} {bx['name']}   {bx['image']}   {bx['status']}   {pkg}", bx))
            if not items:
                self.msg = t('box_none')
            return items
        items = []
        for key, (name, _image, fam) in BOX_DISTROS.items():
            pkg = PKG_EXT.get(fam, 'pacman')
            have = any(bx['name'] == box_name_for(key) or
                       (bx['name'] == BOX_NAME and bx['family'] == fam and key in bx['image'].lower())
                       for bx in (boxes or []))
            mark = '✓' if have else ' '
            tail = '   ' + t('box_installed') if have else ''
            items.append((f'{mark} {name}   ·  {pkg}{tail}', key))
        return items

    def box_select(self, payload):
        if self.lst_kind == 'boxmenu':
            if payload == 'install':
                self.open_list('boxdistro')
            elif payload == 'list':
                self.open_list('boxlist')
            else:
                self.pick_package()
        elif self.lst_kind == 'boxlist':
            self.pick_package(payload)
        else:
            self.start_box_install(payload)

    def pick_package(self, box=None):
        boxes = list_boxes()
        if boxes is None:
            self.msg = t('box_no_dbx')
            return
        usable = [bx for bx in boxes if bx['family'] in PKG_EXT]
        if not usable:
            self.msg = t('box_missing')
            return
        if box is not None and box['family'] not in PKG_EXT:
            self.msg = t('box_notpkg')
            return
        self.pick_box = box if box is not None else True
        home = os.path.expanduser('~')
        dl = os.path.join(home, 'Downloads')
        self.ob_dir = dl if os.path.isdir(dl) else home
        self.ob_prompt = False
        self.buf = ''
        self.mode = 'OPEN'
        self.ob_load()
        self.msg = t('box_pick_hint')

    def pick_exts(self):
        if isinstance(self.pick_box, dict):
            return {PKG_EXT[self.pick_box['family']]}
        return set(PKG_EXT.values())

    def sudo_ok(self):
        if os.geteuid() == 0:
            return True
        try:
            return subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def pm_steps(self, pm, pkgs):
        sudo = [] if os.geteuid() == 0 else ['sudo', '-n']
        if pm == 'dnf':
            return [(t('st_pkgs'), sudo + ['dnf', 'install', '-y'] + pkgs, 2)]
        if pm == 'apt':
            return [(t('st_update'), sudo + ['apt-get', 'update'], 1),
                    (t('st_pkgs'), sudo + ['apt-get', 'install', '-y'] + pkgs, 2)]
        if pm == 'pacman':
            return [(t('st_pkgs'), sudo + ['pacman', '-S', '--needed', '--noconfirm'] + pkgs, 2)]
        return [(t('st_pkgs'), sudo + ['zypper', '-n', 'install'] + pkgs, 2)]

    def start_box_install(self, distro):
        if self.job and self.job['state'] == 'running':
            self.msg = t('job_busy')
            self._remember()
            self.mode = 'JOB'
            return
        name, image, fam = BOX_DISTROS[distro]
        bname = box_name_for(distro)
        steps = []
        if shutil.which('distrobox', path=job_env()['PATH']) is None:
            steps.append((t('st_dbx_dl'), dbx_download_argv(), 2))
        if not (shutil.which('podman') or shutil.which('docker')):
            pm = detect_pm()
            if pm is None:
                steps.append((t('st_engine'), ['sh', '-c', 'echo ' + shlex.quote(t('box_no_pm')) + '; exit 1'], 1))
            elif not self.sudo_ok():
                steps.append((t('st_engine'), ['sh', '-c', 'echo ' + shlex.quote(t('sudo_needed')) + '; exit 1'], 1))
            else:
                steps += self.pm_steps(pm, ['podman'])
        existing = list_boxes() or []
        if any(bx['name'] == bname for bx in existing):
            steps.append((t('box_exists', name=bname), None, 1))
        else:
            steps.append((t('st_create', name=bname), ['distrobox', 'create', '--name', bname,
                                                       '--image', image, '--yes'], 3))
        steps.append((t('st_boot'), ['distrobox', 'enter', bname, '--', 'true'], 1))
        steps.append((t('st_check'), ['distrobox', '--version'], 1))
        self.start_job(t('job_install'), steps, after=lambda: self.save_box(bname, fam))

    def save_box(self, bname, fam):
        SETTINGS['box'] = {'name': bname, 'family': fam}
        save_config()

    def install_package_in_box(self, path, box=None):
        full = os.path.abspath(path)
        home = os.path.expanduser('~')
        if not (full == home or full.startswith(home + os.sep)):
            self.msg = t('box_home')
            return
        ext = os.path.splitext(full)[1].lower()
        if ext not in ('.deb', '.rpm'):
            self.msg = t('box_notpkg')
            return
        if self.job and self.job['state'] == 'running':
            self.msg = t('job_busy')
            return
        want = 'debian' if ext == '.deb' else 'fedora'
        boxes = list_boxes()
        if boxes is None:
            self.msg = t('box_no_dbx')
            return
        if isinstance(box, dict):
            if box['family'] != want:
                self.msg = t('box_wrongfam')
                return
        else:
            cands = [bx for bx in boxes if bx['family'] == want]
            cands.sort(key=lambda bx: not bx['status'].lower().startswith('up'))
            if not cands:
                self.msg = t('box_nobox', ext=ext, fam=want)
                return
            box = cands[0]
        name = box['name']
        enter = ['distrobox', 'enter', name, '--', 'sudo']
        if want == 'debian':
            steps = [(t('st_update'), enter + ['apt-get', 'update'], 1),
                     (t('st_pkg'), enter + ['apt-get', 'install', '-y', full], 3)]
        else:
            steps = [(t('st_pkg'), enter + ['dnf', 'install', '-y', full], 1)]
        self.pick_box = None
        self.start_job(t('job_pkg', name=os.path.basename(full)), steps)

    def start_job(self, title, steps, after=None):
        self._remember()
        self.job = {'title': title, 'steps': steps, 'pct': 0.0, 'step': '',
                    'state': 'running', 'log': [], 'after': after}
        self.mode = 'JOB'
        threading.Thread(target=self._job_run, daemon=True).start()

    def _job_run(self):
        j = self.job
        total = sum(w for _, _, w in j['steps']) or 1
        done = 0
        for label, argv, w in j['steps']:
            j['step'] = label
            j['log'].append('» ' + label)
            if argv is None:
                j['log'].append('  ' + t('skipped'))
                done += w
                j['pct'] = done / total
                continue
            try:
                proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1, env=job_env())
            except OSError as e:
                j['log'].append(str(e))
                j['state'] = 'error'
                j['step'] = label + '  ✗'
                return
            n = 0
            for line in proc.stdout:
                j['log'].append(line.rstrip())
                del j['log'][:-500]
                n += 1
                j['pct'] = (done + w * min(0.95, n / 80)) / total
            if proc.wait() != 0:
                j['log'].append(t('job_failed', code=proc.returncode))
                j['state'] = 'error'
                j['step'] = label + '  ✗'
                return
            done += w
            j['pct'] = done / total
        if j['after']:
            j['after']()
        j['pct'] = 1.0
        j['state'] = 'ok'
        j['step'] = t('job_done')

    def job_key(self, code, ch):
        if code == 27 or ch == 'q':
            self.leave_screen()
            return True
        if code in (10, 13, curses.KEY_ENTER) and self.job and self.job['state'] != 'running':
            self.leave_screen()
        return True

    def draw_job(self):
        j = self.job
        if j is None:
            return
        w = self.width
        acc = self.colors.style('accent') | curses.A_BOLD
        com = self.colors.style('com')
        text = self.colors.style('text')
        warn = self.colors.style('kw') | curses.A_BOLD
        self.draw_title(j['title'])
        top = self.body_top()
        bw = max(10, w - 24)
        pct = max(0.0, min(1.0, j['pct']))
        filled = int(bw * pct)
        self.put(top, 4, '█' * filled + '░' * (bw - filled), acc)
        self.put(top, 4 + bw + 2, f'{int(pct * 100):3d}%', acc)
        self.put(top + 1, 4, j['step'], warn if j['state'] == 'error' else text)
        label = t('console')
        self.put(top + 2, 2, '── ' + label + ' ' + '─' * max(0, w - 8 - len(label)), acc)
        avail = self.height - 2 - (top + 3)
        if avail > 0:
            for k, line in enumerate(j['log'][-avail:]):
                self.put(top + 3 + k, 4, line, com)

    def install_hint_done(self):
        return bool(self.job) and self.job['state'] != 'running'

    # ---- girdi

    def key(self):
        try:
            k = self.scr.get_wch()
        except curses.error:
            return True
        if isinstance(k, str):
            code, ch = ord(k), k
        else:
            code, ch = k, ''
        if code == curses.KEY_RESIZE:
            return True
        if code == curses.KEY_MOUSE:
            return self.mouse_event()
        self.msg = ''
        if self.help:
            self.help = False
            return True
        m = self.mode
        if m == 'SPLASH':
            return self.splash_key(code, ch)
        if m == 'DROP':
            return self.drop_key(code, ch)
        if m == 'PALETTE':
            return self.palette_key(code, ch)
        if m in ('NORMAL', 'INSERT'):
            if self.side_focus and self.ide_on():
                return self.side_key(code, ch)
            if self.ide_global_key(code):
                return True
        if m == 'JOB':
            return self.job_key(code, ch)
        if m == 'LIST':
            return self.list_key(code, ch)
        if m == 'OPEN':
            return self.open_key(code, ch)
        if m == 'SETTINGS':
            return self.settings_key(code, ch)
        if m == 'MENU':
            return self.menu_key(code, ch)
        if m in ('SEARCH', 'CMD'):
            return self.input_key(code, ch)
        if m == 'INSERT':
            return self.insert_key(code, ch)
        return self.normal_key(code, ch)

    def splash_key(self, code, ch):
        n = len(SPLASH_ITEMS)
        if code == curses.KEY_UP:
            self.sp_idx = (self.sp_idx - 1) % n
            return True
        if code == curses.KEY_DOWN:
            self.sp_idx = (self.sp_idx + 1) % n
            return True
        if code in (10, 13, curses.KEY_ENTER):
            return self.splash_run(SPLASH_ITEMS[self.sp_idx][0])
        if code == 14:
            return self.splash_run('new')
        if code == 15:
            return self.splash_run('open')
        if code == 6:
            return self.splash_run('find')
        if code == 17:
            return self.splash_run('quit')
        if code == 19:
            self.mode = 'INSERT'
            self.write()
            return True
        if ch == '+':
            return self.splash_run('code')
        if ch == '.':
            return self.splash_run('settings')
        self.mode = 'INSERT'
        return self.insert_key(code, ch)

    def menu_key(self, code, ch):
        if code == 27 or ch == 'q':
            self.mode = self.menu_back
            return True
        if ch == 'j' or code == curses.KEY_DOWN:
            self.menu_idx = (self.menu_idx + 1) % self.MENU_N
        elif ch == 'k' or code == curses.KEY_UP:
            self.menu_idx = (self.menu_idx - 1) % self.MENU_N
        elif code in (10, 13, curses.KEY_ENTER) or ch in (' ', 'l'):
            self.cycle_setting(self.menu_idx)
        return True

    def open_menu(self):
        self.menu_back = 'NORMAL' if self.mode == 'NORMAL' else 'INSERT'
        self.mode = 'MENU'
        self.menu_idx = 0

    def cycle_setting(self, idx):
        if idx == 0:
            names = list(THEMES)
            cur = names.index(SETTINGS['theme'])
            SETTINGS['theme'] = names[(cur + 1) % len(names)]
            self.colors.reset()
            self.msg = t('theme_set', name=THEMES[SETTINGS['theme']]['label'])
        else:
            cycle_lang(1)
            self.msg = t('lang_set', name=LANG_NAMES[SETTINGS['lang']])
        self.msg += '  ·  ' + persist()

    def new_buffer(self):
        pristine = len(self.bufs) == 1 and self.bufs[0].path is None and not self.bufs[0].modified
        if not pristine:
            self.bufs.append(Buffer(None))
            self.bi = len(self.bufs) - 1
        self.mode = 'INSERT'

    def redraw(self):
        self.scr.clear()
        self.msg = t('redrawn')

    def enter_insert(self):
        self.b.snapshot()
        self.mode = 'INSERT'

    def insert_key(self, code, ch):
        if self.comp and self.ide_on():
            c = self.comp
            if code == curses.KEY_DOWN:
                c['idx'] = (c['idx'] + 1) % len(c['items'])
                return True
            if code == curses.KEY_UP:
                c['idx'] = (c['idx'] - 1) % len(c['items'])
                return True
            if code in (9, 10, 13, curses.KEY_ENTER):
                self.accept_comp()
                return True
            if code == 27:
                self.comp = None
                return True
        r = self.insert_key_base(code, ch)
        typed = (ch and ch.isprintable() and not ch.isspace() and ch not in '()[]{},;:.') or code in (8, 127, curses.KEY_BACKSPACE)
        self.comp = self.make_comp() if (r and typed and self.mode == 'INSERT' and self.ide_on()) else None
        return r

    def insert_key_base(self, code, ch):
        b = self.b
        if code == 27:
            self.mode = 'NORMAL'
            self.clamp(False)
            return True
        if code == 19:                   # Ctrl-S
            self.write()
            return True
        if code == 17:                   # Ctrl-Q
            return self.quit_app(False)
        if code in (6, 28, 31):          # Ctrl-F, Ctrl-/ : ara
            self.prompt_back = 'INSERT'
            self.mode, self.prefix, self.buf = 'SEARCH', '/', ''
            return True
        if code == 7:                    # Ctrl-G : satıra git
            self.prompt_back = 'INSERT'
            self.mode, self.buf = 'CMD', ''
            return True
        if code == 14:                   # Ctrl-N
            self.new_buffer()
            return True
        if code == 15:                   # Ctrl-O
            self.prompt_back = 'INSERT'
            self.enter_open()
            return True
        if code == 16:                   # Ctrl-P
            self.open_list('ring')
            return True
        if code == 18:                   # Ctrl-R: çalıştır
            self.run_code()
            return True
        if code == curses.KEY_F5:
            self.run_code()
            return True
        if code == curses.KEY_F6:
            self.toggle_panel()
            return True
        if code == 11:                   # Ctrl-K: satır sil
            self.del_line()
            return True
        if code == 4:                    # Ctrl-D: satır kopyala
            self.dup_line()
            return True
        if code == 12:                   # Ctrl-L
            self.redraw()
            return True
        if code in (10, 13, curses.KEY_ENTER):
            indent = re.match(r'[ \t]*', b.lines[b.cur]).group(0) if self.opts.get('autoindent') else ''
            b.split_line()
            if indent:
                b.insert_text(indent)
        elif code in (8, 127, curses.KEY_BACKSPACE):
            b.backspace()
        elif code == 9:
            b.insert_text(' ' * self.opts.get('tabsize', 4))
        elif code == curses.KEY_LEFT:
            b.cc = max(0, b.cc - 1)
        elif code == curses.KEY_RIGHT:
            b.cc += 1
        elif code == curses.KEY_UP:
            b.cur = max(0, b.cur - 1)
        elif code == curses.KEY_DOWN:
            b.cur = min(len(b.lines) - 1, b.cur + 1)
        elif code == curses.KEY_HOME:
            b.cc = 0
        elif code == curses.KEY_END:
            b.cc = len(b.lines[b.cur])
        elif ch and ch.isprintable():
            nxt = b.lines[b.cur][b.cc:b.cc + 1]
            if self.opts.get('autoclose') and ch in PAIRS:
                b.insert_text(ch + PAIRS[ch])
                b.cc -= 1
            elif self.opts.get('autoclose') and ch in RPAIRS and nxt == ch:
                b.cc += 1
            else:
                b.insert_text(ch)
        self.clamp(True)
        return True

    def normal_key(self, code, ch):
        b = self.b
        if code == curses.KEY_F1:
            self.help = True
            return True
        if code == 27:
            self.count = ''
            self.pending = ''
            return True
        if self.pending:
            p = self.pending
            self.pending = ''
            n_raw = self.pcount
            self.pcount = 0
            self.count = ''
            self.pending_action(p, ch, n_raw)
            return True

        if ch and ch.isdigit() and (self.count or ch != '0'):
            self.count += ch
            return True

        n_raw = int(self.count) if self.count else 0
        n = n_raw or 1
        self.count = ''
        self.msg = ''
        line = b.lines[b.cur]
        last = max(0, len(line) - 1)

        # Ctrl tuşları
        if code == 19:                       # Ctrl-S
            self.write()
        elif code == 15:                     # Ctrl-O
            self.enter_open()
        elif code == 14:                     # Ctrl-N
            self.new_buffer()
        elif code in (18, curses.KEY_F5):
            self.run_code()
        elif code == curses.KEY_F6:
            self.toggle_panel()
        elif code == 16:                     # Ctrl-P
            self.open_list('ring')
        elif code == 12:                     # Ctrl-L
            self.redraw()
        elif code == 17:                     # Ctrl-Q
            return self.quit_app(False)
        elif code == 3:                      # Ctrl-C (raw modda gelir)
            self.msg = t('ctrl_c')
        elif ch == 'q':
            return self.quit_app(False)
        elif ch == 'j' or code == curses.KEY_DOWN:
            self.goto(b.cur + n)
        elif ch == 'k' or code == curses.KEY_UP:
            self.goto(b.cur - n)
        elif ch == 'h' or code == curses.KEY_LEFT:
            b.cc = max(0, b.cc - n)
        elif ch == 'l' or code == curses.KEY_RIGHT:
            b.cc = min(last, b.cc + n)
        elif ch == '0' or code == curses.KEY_HOME:
            b.cc = 0
        elif ch == '^':
            m = re.search(r'\S', line)
            b.cc = m.start() if m else 0
        elif ch == '$' or code == curses.KEY_END:
            b.cc = last
        elif ch == 'w':
            self.word_fwd(n)
        elif ch == 'b':
            self.word_back(n)
        elif ch == 'e':
            self.word_end(n)
        elif ch == '}':
            self.para(n, 1)
        elif ch == '{':
            self.para(n, -1)
        elif ch == 'G':
            self.goto(n_raw - 1 if n_raw else len(b.lines) - 1)
        elif ch in ('g', 'y', 'z', 'm', "'", 'd'):
            self.pending = ch
            self.pcount = n_raw
            self.count = ''
        elif ch in ('H', 'M', 'L'):
            top = b.top
            bottom = min(len(b.lines) - 1, top + self.rows - 1)
            target = {'H': top, 'M': (top + bottom) // 2, 'L': bottom}[ch]
            self.goto(target)
        elif code == 4:                      # Ctrl-d
            self.scroll(self.rows // 2 * n)
        elif code == 21:                     # Ctrl-u
            self.scroll(-(self.rows // 2) * n)
        elif code == 6:                      # Ctrl-f
            self.scroll(max(1, self.rows - 2) * n)
        elif code == 2:                      # Ctrl-b
            self.scroll(-max(1, self.rows - 2) * n)
        elif code == 5:                      # Ctrl-e
            b.top = min(len(b.lines) - 1, b.top + n)
            if b.cur < b.top:
                self.goto(b.top)
        elif code == 25:                     # Ctrl-y
            b.top = max(0, b.top - n)
            bottom = min(len(b.lines) - 1, b.top + self.rows - 1)
            if b.cur > bottom:
                self.goto(bottom)
        elif ch == '/' or ch == '?':
            self.prompt_back = 'NORMAL'
            self.mode, self.prefix, self.buf = 'SEARCH', ch, ''
        elif ch == ':':
            self.prompt_back = 'NORMAL'
            self.mode, self.buf = 'CMD', ''
        elif ch in ('n', 'N'):
            fwd = self.search_fwd if ch == 'n' else not self.search_fwd
            if not self.search:
                self.msg = t('no_search')
            else:
                self.nohl = False
                self.do_search(self.search, fwd)
        elif ch in ('*', '#'):
            self.star(ch == '*')
        elif ch == 'Y':
            self.yank(n)
        elif ch == 'i':
            self.enter_insert()
        elif ch == 'a':
            b.cc = min(len(line), b.cc + 1)
            self.enter_insert()
        elif ch == 'I':
            m = re.search(r'\S', line)
            b.cc = m.start() if m else 0
            self.enter_insert()
        elif ch == 'A':
            b.cc = len(line)
            self.enter_insert()
        elif ch == 'o' or ch == 'O':
            b.snapshot()
            b.open_line(ch == 'o')
            self.mode = 'INSERT'
        elif ch == 'x':
            b.snapshot()
            b.delete_char(n)
            self.clamp()
        elif ch == 'p' or ch == 'P':
            self.paste(ch == 'p')
        elif ch == 'u':
            self.undo()
        return True

    def pending_action(self, p, ch, n_raw):
        b = self.b
        n = n_raw or 1
        if p == 'g':
            if ch == 'g':
                self.goto(n_raw - 1 if n_raw else 0)
            elif ch == 't':
                self.switch(n_raw - 1 if n_raw else self.bi + 1)
            elif ch == 'T':
                self.switch(self.bi - 1)
        elif p == 'y':
            if ch == 'y':
                self.yank(n)
        elif p == 'd':
            if ch == 'd':
                b.snapshot()
                chunk = b.delete_lines(n)
                self.reg_lines = chunk
                self.push_ring('\n'.join(chunk))
                self.msg = t('deleted', n=len(chunk))
                self.clamp()
        elif p == 'z':
            if ch == 'z':
                b.top = max(0, b.cur - self.rows // 2)
            elif ch == 't':
                b.top = b.cur
            elif ch == 'b':
                b.top = max(0, b.cur - self.rows + 1)
        elif p == 'm':
            if ch.isalpha():
                b.marks[ch] = (b.cur, b.cc)
                self.msg = t('mark_set', ch=ch)
        elif p == "'":
            if ch in b.marks:
                b.cur, b.cc = b.marks[ch]
                b.cur = min(b.cur, len(b.lines) - 1)
                self.clamp()
            else:
                self.msg = t('mark_missing', ch=ch)

    def paste(self, below):
        if not self.reg_lines:
            self.msg = t('empty_reg')
            return
        b = self.b
        b.snapshot()
        at = b.cur + 1 if below else b.cur
        b.lines[at:at] = list(self.reg_lines)
        b.cur = at
        b.cc = 0
        b.touch()
        self.msg = t('pasted', n=len(self.reg_lines))

    def undo(self):
        if self.b.undo_pop():
            self.clamp()
            self.msg = t('undone')
        else:
            self.msg = t('undo_none')

    # ---- hareketler

    def word_fwd(self, n):
        b = self.b
        for _ in range(n):
            line = b.lines[b.cur]
            nxt = [m.start() for m in WORD_RE.finditer(line) if m.start() > b.cc]
            if nxt:
                b.cc = nxt[0]
                continue
            for j in range(b.cur + 1, len(b.lines)):
                st = [m.start() for m in WORD_RE.finditer(b.lines[j])]
                if st:
                    b.cur, b.cc = j, st[0]
                    break
            else:
                b.cc = max(0, len(line) - 1)
                break
        self.clamp()

    def word_back(self, n):
        b = self.b
        for _ in range(n):
            line = b.lines[b.cur]
            prv = [m.start() for m in WORD_RE.finditer(line) if m.start() < b.cc]
            if prv:
                b.cc = prv[-1]
                continue
            for j in range(b.cur - 1, -1, -1):
                st = [m.start() for m in WORD_RE.finditer(b.lines[j])]
                if st:
                    b.cur, b.cc = j, st[-1]
                    break
            else:
                b.cc = 0
                break
        self.clamp()

    def word_end(self, n):
        b = self.b
        for _ in range(n):
            line = b.lines[b.cur]
            ends = [m.end() - 1 for m in WORD_RE.finditer(line) if m.end() - 1 > b.cc]
            if ends:
                b.cc = ends[0]
                continue
            for j in range(b.cur + 1, len(b.lines)):
                en = [m.end() - 1 for m in WORD_RE.finditer(b.lines[j])]
                if en:
                    b.cur, b.cc = j, en[0]
                    break
            else:
                break
        self.clamp()

    def para(self, n, d):
        b = self.b
        i = b.cur
        for _ in range(n):
            j = i + d
            while 0 <= j < len(b.lines) and b.lines[j].strip() != '':
                j += d
            i = max(0, min(j, len(b.lines) - 1))
        self.goto(i)
        b.cc = 0

    # ---- arama

    def do_search(self, pat, fwd, inclusive=False):
        b = self.b
        n = len(b.lines)
        rx = re.compile(re.escape(pat), re.I if self.opts['ignorecase'] else 0)
        for off in range(n + 1):
            idx = b.cur + off if fwd else b.cur - off
            i = idx % n
            line = b.lines[i]
            if fwd:
                start = (b.cc if inclusive else b.cc + 1) if off == 0 else 0
                m = rx.search(line, start) if start <= len(line) else None
                p = m.start() if m else -1
            else:
                if off == 0:
                    cand = [m.start() for m in rx.finditer(line) if m.start() < b.cc]
                else:
                    cand = [m.start() for m in rx.finditer(line)]
                p = cand[-1] if cand else -1
            if p >= 0:
                wrapped = idx >= n or idx < 0
                b.cur, b.cc = i, p
                self.clamp()
                self.msg = ('/' if fwd else '?') + pat + (t('wrapped') if wrapped else '')
                return True
        self.msg = t('not_found', pat=pat)
        return False

    def star(self, fwd):
        b = self.b
        line = b.lines[b.cur]
        for m in WORD_RE.finditer(line):
            if m.start() <= b.cc < m.end():
                self.search = m.group(0)
                self.search_fwd = fwd
                self.nohl = False
                self.do_search(self.search, fwd)
                return
        self.msg = t('no_word')

    # ---- kopyalama ve yazma

    def copy_clip(self, text):
        self.reg = text
        for cmd in (['wl-copy'], ['xclip', '-selection', 'clipboard'],
                    ['xsel', '--clipboard', '--input']):
            if shutil.which(cmd[0]):
                try:
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                    p.communicate(text.encode('utf-8'), timeout=2)
                    if p.returncode == 0:
                        return t('clip_sys')
                except (OSError, subprocess.SubprocessError):
                    pass
        return t('clip_int')

    def yank(self, n):
        b = self.b
        chunk = b.lines[b.cur:b.cur + n]
        self.reg_lines = list(chunk)
        self.push_ring('\n'.join(chunk))
        where = self.copy_clip('\n'.join(chunk))
        self.msg = t('copied', n=len(chunk), where=where)

    def write(self, arg=''):
        """Geçerli buffer'ı yazar. Başarılıysa True döner."""
        b = self.b
        target = os.path.expanduser(arg) if arg else b.path
        if not target:
            self.msg = t('noname_write')
            return False
        if b.binary:
            self.msg = t('binary_write')
            return False
        if self.opts.get('trimws'):
            b.lines = [l.rstrip() for l in b.lines]
            b.touch()
        try:
            n = b.save(target, self.opts.get('finalnl', True))
        except OSError as e:
            self.msg = t('write_fail', err=e.strerror or str(e))
            return False
        self.msg = t('written', name=os.path.basename(target), n=n)
        if self.opts.get('snapshots', True):
            try:
                take_snapshot(target, '\n'.join(b.lines) + '\n')
            except OSError:
                pass
        return True

    def write_all(self):
        count = 0
        for b in self.bufs:
            if b.path and b.modified and not b.binary:
                try:
                    b.save()
                    count += 1
                except OSError as e:
                    self.msg = t('write_fail', err=e.strerror or str(e))
                    return False
        self.msg = t('wrote_all', n=count)
        return True

    def quit_app(self, force):
        """True: uygulama açık kalır. False: çık."""
        if not force and self.opts.get('confirmquit', True) and any(b.modified for b in self.bufs):
            self.msg = t('quit_modified')
            return True
        return False

    def quit_buffer(self, force):
        b = self.b
        if b.modified and not force:
            self.msg = t('quit_modified')
            return True
        if len(self.bufs) == 1:
            return False
        del self.bufs[self.bi]
        self.bi = min(self.bi, len(self.bufs) - 1)
        return True

    # ---- buffer yönetimi

    def switch(self, idx):
        self.bi = idx % len(self.bufs)
        self.msg = ''

    def open_file(self, path):
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            self.msg = t('isdir', path=path)
            return
        full = os.path.abspath(path)
        for k, b in enumerate(self.bufs):
            if b.path and os.path.abspath(b.path) == full:
                self.bi = k
                self.msg = t('opened', path=path)
                return
        nb = Buffer(path)
        if nb.binary:
            self.msg = t('binary')
        if len(self.bufs) == 1 and self.bufs[0].path is None and not self.bufs[0].modified:
            self.bufs = []
        self.bufs.append(nb)
        self.bi = len(self.bufs) - 1
        self.msg = t('newfile', name=path) if nb.is_new else t('opened', path=path)

    def reload(self):
        b = self.b
        if not b.path or not os.path.isfile(b.path):
            self.msg = t('nofile', path=b.path or '')
            return
        b.load()
        self.clamp()
        self.msg = t('reloaded', name=b.name)

    # ---- giriş satırı (/ ? :)

    def input_key(self, code, ch):
        b = self.b
        if self.mode == 'SEARCH' and self.search_origin is None:
            self.search_origin = (b.cur, b.cc)
        if code == 27:
            if self.mode == 'SEARCH':
                self.search_restore()
                self.search_origin = None
            self.mode, self.buf = self.prompt_back, ''
            return True
        if code in (10, 13, curses.KEY_ENTER):
            mode, text = self.mode, self.buf
            self.mode, self.buf = self.prompt_back, ''
            if mode == 'SEARCH':
                self.search_done(text)
                return True
            self.search_origin = None
            return self.command(text)
        if code in (8, 127, curses.KEY_BACKSPACE):
            if self.buf:
                self.buf = self.buf[:-1]
                if self.mode == 'SEARCH':
                    self.live_search()
            else:
                if self.mode == 'SEARCH':
                    self.search_restore()
                    self.search_origin = None
                self.mode = self.prompt_back
            return True
        if ch and ch.isprintable():
            self.buf += ch
            if self.mode == 'SEARCH':
                self.live_search()
        return True

    def set_opts(self, args):
        alias = {'nu': 'number', 'rnu': 'relativenumber', 'ic': 'ignorecase',
                 'hls': 'hlsearch', 'syn': 'syntax', 'cul': 'cursorline'}
        out = []
        for a in args:
            if a == 'all':
                continue
            query = a.endswith('?')
            a = a.rstrip('?')
            bang = a.endswith('!')
            a = a.rstrip('!')
            neg = False
            name = alias.get(a, a)
            if name not in self.opts and a.startswith('no'):
                cand = alias.get(a[2:], a[2:])
                if cand in self.opts:
                    name, neg = cand, True
            if name not in self.opts:
                out.append(t('bad_opt', a=a))
                continue
            if query:
                out.append(('' if self.opts[name] else 'no') + name)
            elif bang:
                self.opts[name] = not self.opts[name]
            else:
                self.opts[name] = not neg
        if out:
            self.msg = '  '.join(out)

    def set_theme_cmd(self, arg):
        if not arg:
            self.msg = t('theme_list', list=', '.join(THEMES))
        elif arg in THEMES:
            SETTINGS['theme'] = arg
            self.colors.reset()
            self.msg = t('theme_set', name=THEMES[arg]['label']) + '  ·  ' + persist()
        else:
            self.msg = t('bad_theme', name=arg, list=', '.join(THEMES))

    def set_lang_cmd(self, arg):
        if arg in STR:
            SETTINGS['lang'] = arg
            self.msg = t('lang_set', name=LANG_NAMES[arg]) + '  ·  ' + persist()
        else:
            self.msg = t('bad_lang', name=arg or '?')

    def command(self, text):
        text = text.strip()
        if not text:
            return True
        if text.isdigit():
            self.goto(int(text) - 1)
            return True
        handled = self.extra_command(text)
        if handled is not None:
            return True
        parts = text.split(None, 1)
        name = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ''
        bang = name.endswith('!')
        base = name.rstrip('!')

        if base in ('w', 'write', 'update'):
            self.write(arg)
        elif base in ('wa', 'wall'):
            self.write_all()
        elif base in ('wq', 'x', 'xit', 'exit'):
            if self.write(arg):
                return self.quit_buffer(True)
        elif base in ('q', 'quit', 'clo', 'close', 'bd', 'bdelete'):
            return self.quit_buffer(bang)
        elif base in ('qa', 'qall', 'cq'):
            return self.quit_app(bang)
        elif base in ('open', 'o', 'ac'):
            if arg:
                self.open_path(arg)
            else:
                self.enter_open()
        elif base in ('box', 'kur', 'nbox'):
            self.open_list('boxmenu')
        elif base in ('pkg', 'paket'):
            self.pick_package()
        elif base in ('play', 'playground', 'test'):
            try:
                os.makedirs(PLAYGROUND, exist_ok=True)
            except OSError:
                pass
            self.ob_dir = PLAYGROUND
            self.prompt_back = self.mode
            self.enter_open()
        elif base == 'ide':
            self.opts['ide'] = not self.opts.get('ide', True)
            self.msg = t('ide_on') if self.opts['ide'] else t('ide_off')
        elif base in ('explorer', 'sidebar', 'tree'):
            self.ide_global_key(curses.KEY_F2)
        elif base in ('run', 'calistir', 'calistır'):
            self.run_code()
        elif base in ('panel', 'cikti', 'çıktı'):
            self.toggle_panel()
        elif base in ('kod', 'code'):
            self.open_list('lang')
        elif base in ('zaman', 'timeline', 'snap'):
            self.open_list('timeline')
        elif base in ('pano', 'ring', 'clip'):
            self.open_list('ring')
        elif base in ('hedef', 'goal'):
            if arg.isdigit():
                self.opts['wordgoal'] = int(arg)
                self.msg = t('goal_set', n=arg) + '  ·  ' + persist(self.opts)
            else:
                self.msg = t('bad_num', a=arg or '?')
        elif base in ('e', 'edit'):
            if arg:
                self.open_file(arg)
            elif bang:
                self.reload()
            else:
                self.msg = t('usage_e')
        elif base in ('bn', 'bnext'):
            self.switch(self.bi + 1)
        elif base in ('bp', 'bprevious', 'bN'):
            self.switch(self.bi - 1)
        elif base in ('ls', 'buffers', 'files'):
            self.msg = '  '.join(f'{k + 1}:{b.bufname()}' for k, b in enumerate(self.bufs))
        elif base in ('set', 'se'):
            self.set_opts(arg.split())
        elif base in ('noh', 'nohlsearch'):
            self.nohl = True
        elif base in ('h', 'help'):
            self.help = True
        elif base in ('redraw', 'redr'):
            self.redraw()
        elif base == 'theme':
            self.set_theme_cmd(arg)
        elif base in ('lang', 'language'):
            self.set_lang_cmd(arg)
        elif base in ('ayar', 'ayarlar', 'settings', 'config'):
            self.enter_settings()
        elif base in ('u', 'undo'):
            self.undo()
        elif base in ('version', 'ver'):
            self.msg = t('version_line', v=VERSION, name=VERSION_NAME)
        elif base in ('reg', 'registers'):
            shown = '\n'.join(self.reg_lines)[:60] or '-'
            self.msg = t('reg_show', text=shown)
        else:
            self.msg = t('unknown_cmd', name=name)
        return True


# ------------------------------------------------------------------ read modu

def render(b, i, color, numw):
    """Bir satırı (ANSI renkli ya da düz) metne çevirir."""
    line = b.lines[i]
    if not color:
        prefix = (str(i + 1).rjust(numw) + '  ') if numw else ''
        return prefix + line
    names = ['text'] * len(line)
    for s, e, kind in b.spans(i):
        for k in range(s, min(e, len(line))):
            names[k] = kind
    parts = []
    if numw:
        parts.append(ansi('ln') + str(i + 1).rjust(numw) + '  ')
    k = 0
    while k < len(line):
        j = k + 1
        while j < len(line) and names[j] == names[k]:
            j += 1
        parts.append(ansi(names[k]) + line[k:j])
        k = j
    parts.append(RESET)
    return ''.join(parts)


def read_mode(args):
    plain = False
    files = []
    for a in args:
        if a == '--plain':
            plain = True
        elif a in ('-h', '--help'):
            print(t('read_usage'))
            return 0
        elif a.startswith('-') and a != '-':
            print(t('bad_option', a=a), file=sys.stderr)
            return 1
        else:
            files.append(a)
    if not files:
        print(t('read_usage'), file=sys.stderr)
        return 1
    color = (not plain) and sys.stdout.isatty()
    rc = 0
    for path in files:
        if path == '-':
            b = Buffer(None)
            b.set_text(sys.stdin.buffer.read().decode('utf-8', errors='replace'))
            name = '-'
        else:
            if not os.path.isfile(path):
                print(t('bad_file', path=path), file=sys.stderr)
                rc = 1
                continue
            b = Buffer(path)
            if b.binary:
                print(t('bin_skip', path=path), file=sys.stderr)
                rc = 1
                continue
            name = path
        if len(files) > 1:
            header = f'==> {name} <=='
            print(ansi('accent') + header + RESET if color else header)
        numw = 0 if plain else len(str(len(b.lines)))
        for i in range(len(b.lines)):
            print(render(b, i, color, numw))
        if len(files) > 1:
            print()
    return rc


# ------------------------------------------------------------------ giriş

def run(scr, paths, splash, colors_on):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    try:
        curses.raw()        # Ctrl-S/Ctrl-Q akış kontrolüne takılmasın
    except curses.error:
        pass
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.mouseinterval(0)
    except curses.error:
        pass
    ok = False
    big = False
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        ok = True
        big = curses.COLORS >= 256
    scr.timeout(200)  # iş ilerlemesi için periyodik yenileme
    app = App(scr, paths, splash, Colors(ok, big))
    while True:
        app.draw()
        if not app.key():
            break


USAGE = ''


def main(argv):
    global USAGE
    load_config()
    USAGE = t('usage')
    if argv and argv[0] == 'read':
        return read_mode(argv[1:])
    if argv and argv[0] == 'open':
        START['mode'] = 'OPEN'
        argv = argv[1:]

    splash = True
    paths = []
    theme = lang = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('-h', '--help'):
            print(USAGE)
            return 0
        if a == '--version':
            print(t('version_line', v=VERSION, name=VERSION_NAME))
            return 0
        if a == '--no-splash':
            splash = False
        elif a in ('--theme', '--lang'):
            i += 1
            if i >= len(argv):
                print(USAGE, file=sys.stderr)
                return 1
            if a == '--theme':
                theme = argv[i]
            else:
                lang = argv[i]
        elif a.startswith('--theme='):
            theme = a.split('=', 1)[1]
        elif a.startswith('--lang='):
            lang = a.split('=', 1)[1]
        elif a.startswith('-') and a != '-':
            print(t('bad_option', a=a) + '\n' + USAGE, file=sys.stderr)
            return 1
        else:
            paths.append(a)
        i += 1

    if theme is not None:
        if theme not in THEMES:
            print(t('bad_theme', name=theme, list=', '.join(THEMES)), file=sys.stderr)
            return 1
        SETTINGS['theme'] = theme
    if lang is not None:
        if lang not in STR:
            print(t('bad_lang', name=lang), file=sys.stderr)
            return 1
        SETTINGS['lang'] = lang

    if START.get('mode') == 'OPEN' and len(paths) == 1 and os.path.isdir(paths[0]):
        START['dir'] = os.path.abspath(paths[0])
        paths = []
    if paths:
        START['mode'] = None
    for p in paths:
        if os.path.isdir(p):
            print(t('isdir', path=p), file=sys.stderr)
            return 1

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(t('no_tty'), file=sys.stderr)
        return 1

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        pass
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(run, paths, splash, True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
