## src/gtkspell.py
##
## (C) 2008 Thorsten P. 'dGhvcnN0ZW5wIEFUIHltYWlsIGNvbQ==\n'.decode("base64")
## (C) 2015 Yann Leboulanger <asterix AT lagaule.org>
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

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
import gi
try:
    gi.require_version('GtkSpell', '3.0')
    from gi.repository import GtkSpell
    HAS_GTK_SPELL = True
except (ImportError, ValueError):
    HAS_GTK_SPELL = False


def ensure_attached(func):
    def f(self, *args, **kwargs):
        if self.spell:
            func(self, *args, **kwargs)
        else:
            raise RuntimeError("Spell object is already detached")
    return f


class Spell(GObject.GObject):
    __gsignals__ = {
        'language_changed': (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }

    def __init__(self, textview, language=None, create=True, jid=None,
    per_type=None):
        GObject.GObject.__init__(self)
        if not isinstance(textview, Gtk.TextView):
            raise TypeError("Textview must be derived from Gtk.TextView")
        spell = GtkSpell.Checker.get_from_text_view(textview)
        if create:
            if spell:
                raise RuntimeError("Textview has already a Spell obj attached")
            self.spell = GtkSpell.Checker.new()

            try:
                self.spell.set_language(language)
            except GLib.GError as error:
                if error.domain == 'gtkspell-error-quark':
                    raise OSError("Unable to set language: '%s'" % language)

            self.spell.connect('language-changed', self.on_language_changed)

        else:
            if spell:
                self.spell = spell
            else:
                raise RuntimeError("Textview has no Spell object attached")

    def on_language_changed(self, spell, lang):
        self.emit('language_changed', lang)

    @ensure_attached
    def set_language(self, language):
        if not self.spell.set_language(language):
            raise OSError("Unable to set language: '%s'" % language)

    @ensure_attached
    def recheck_all(self):
        self.spell.recheck_all()

    def detach(self):
        if self.spell is not None:
            self.spell.detach()

    def attach(self, textview):
        spell = GtkSpell.Checker.get_from_text_view(textview)
        if spell is None:
            print('attached')
            self.spell.attach(textview)


GObject.type_register(Spell)


def test_language(lang):
    spell = GtkSpell.Checker.new()
    try:
        spell.set_language(lang)
    except GLib.GError as error:
        if error.domain == 'gtkspell-error-quark':
            return False
    return True
