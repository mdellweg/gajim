# -*- coding:utf-8 -*-
## src/shortcuts_window.py
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from gi.repository import Gtk

from gajim import gtkgui_helpers

from gajim.common import helpers

__all__ = ['show']

class ShortcutsWindow:
    def __init__(self):
        self.window = None

    def show(self, parent=None):
        if self.window is None:
            builder = gtkgui_helpers.get_gtk_builder('shortcuts_window.ui')
            self.window = builder.get_object('shortcuts_window')
            self.window.connect('destroy', self._on_window_destroy)
        self.window.set_transient_for(parent)
        self.window.show_all()
        self.window.present()

    def _on_window_destroy(self, widget):
        self.window = None

def show_shortcuts_webpage(self, parent=None):
    helpers.launch_browser_mailer('url',
        'https://dev.gajim.org/gajim/gajim/wikis/help/keyboardshortcuts')

if (3, 19) <= (Gtk.get_major_version(), Gtk.get_minor_version()):
    show = ShortcutsWindow().show
else:
    show = show_shortcuts_webpage
