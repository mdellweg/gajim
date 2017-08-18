# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
from enum import IntEnum
from datetime import datetime, timedelta, timezone

import nbxmpp
from gi.repository import Gtk, GLib

from common import gajim
from common import ged
from gtkgui_helpers import get_icon_pixmap

log = logging.getLogger('gajim.c.message_archiving')

class Pages(IntEnum):
    TIME = 0
    SYNC = 1
    SUMMARY = 2

class ArchiveState(IntEnum):
    NEVER = 0
    ALL = 1

class HistorySyncAssistant(Gtk.Assistant):
    def __init__(self, account, parent):
        Gtk.Assistant.__init__(self)
        self.set_title(_('Synchronise History'))
        self.set_resizable(False)
        self.set_default_size(300, -1)
        self.set_name('HistorySyncAssistant')
        self.set_transient_for(parent)
        self.account = account
        self.con = gajim.connections[self.account]
        self.timedelta = None
        self.now = datetime.utcnow()
        self.query_id = None
        self.count_query_id = None
        self.start = None
        self.end = None
        self.next = None
        self.hide_buttons()

        mam_start = gajim.config.get_per('accounts', account, 'mam_start_date')
        if not mam_start or mam_start == ArchiveState.NEVER:
            self.current_start = self.now
        elif mam_start == ArchiveState.ALL:
            self.current_start = datetime.utcfromtimestamp(0)
        else:
            self.current_start = datetime.fromtimestamp(mam_start)

        self.select_time = SelectTimePage(self)
        self.append_page(self.select_time)
        self.set_page_type(self.select_time, Gtk.AssistantPageType.INTRO)

        self.download_history = DownloadHistoryPage(self)
        self.append_page(self.download_history)
        self.set_page_type(self.download_history, Gtk.AssistantPageType.PROGRESS)
        self.set_page_complete(self.download_history, True)

        self.summary = SummaryPage(self)
        self.append_page(self.summary)
        self.set_page_type(self.summary, Gtk.AssistantPageType.SUMMARY)
        self.set_page_complete(self.summary, True)

        gajim.ged.register_event_handler('archiving-finished',
                                         ged.PRECORE,
                                         self._nec_archiving_finished)
        gajim.ged.register_event_handler('raw-mam-message-received',
                                         ged.PRECORE,
                                         self._nec_mam_message_received)

        self.connect('prepare', self.on_page_change)
        self.connect('destroy', self.on_destroy)
        self.connect("cancel", self.on_close_clicked)
        self.connect("close", self.on_close_clicked)

        if mam_start == ArchiveState.ALL:
            self.set_current_page(Pages.SUMMARY)
            self.summary.nothing_to_do()

        if self.con.mam_query_id:
            self.set_current_page(Pages.SUMMARY)
            self.summary.query_already_running()

        self.show_all()

    def hide_buttons(self):
        '''
        Hide some of the standard buttons that are included in Gtk.Assistant
        '''
        if self.get_property('use-header-bar'):
            action_area = self.get_children()[1]
        else:
            box = self.get_children()[0]
            content_box = box.get_children()[1]
            action_area = content_box.get_children()[1]
        for button in action_area.get_children():
            button_name = Gtk.Buildable.get_name(button)
            if button_name == 'back':
                button.connect('show', self._on_show_button)
            elif button_name == 'forward':
                self.next = button
                button.connect('show', self._on_show_button)

    @staticmethod
    def _on_show_button(button):
        button.hide()

    def prepare_query(self):
        if self.timedelta:
            self.start = self.now - self.timedelta
        self.end = self.current_start

        log.info('config: get mam_start_date: %s', self.current_start)
        log.info('now: %s', self.now)
        log.info('start: %s', self.start)
        log.info('end: %s', self.end)

        self.query_count()

    def query_count(self):
        self.count_query_id = self.con.connection.getAnID()
        self.con.request_archive(self.count_query_id,
                                 start=self.start,
                                 end=self.end,
                                 max_=0)

    def query_messages(self, last=None):
        self.query_id = self.con.connection.getAnID()
        self.con.request_archive(self.query_id,
                                 start=self.start,
                                 end=self.end,
                                 after=last,
                                 max_=30)

    def on_row_selected(self, listbox, row):
        self.timedelta = row.get_child().get_delta()
        if row:
            self.set_page_complete(self.select_time, True)
        else:
            self.set_page_complete(self.select_time, False)

    def on_page_change(self, assistant, page):
        if page == self.download_history:
            self.next.hide()
            self.prepare_query()

    def on_destroy(self, *args):
        gajim.ged.remove_event_handler('archiving-finished',
                                       ged.PRECORE,
                                       self._nec_archiving_finished)
        gajim.ged.remove_event_handler('raw-mam-message-received',
                                       ged.PRECORE,
                                       self._nec_mam_message_received)
        del gajim.interface.instances[self.account]['history_sync']

    def on_close_clicked(self, *args):
        self.destroy()

    def _nec_mam_message_received(self, obj):
        if obj.conn.name != self.account:
            return

        if obj.result.getAttr('queryid') != self.query_id:
            return

        log.debug('received message')
        GLib.idle_add(self.download_history.set_fraction)

    def _nec_archiving_finished(self, obj):
        if obj.conn.name != self.account:
            return

        if obj.query_id not in (self.query_id, self.count_query_id):
            return

        set_ = obj.fin.getTag('set', namespace=nbxmpp.NS_RSM)
        if not set_:
            log.error('invalid result')
            log.error(obj.fin)
            return

        if obj.query_id == self.count_query_id:
            count = set_.getTagData('count')
            log.info('message count received: %s', count)
            if count:
                self.download_history.count = int(count)
            self.query_messages()
            return

        if obj.query_id == self.query_id:
            last = set_.getTagData('last')
            complete = obj.fin.getAttr('complete')
            if not last and complete != 'true':
                log.error('invalid result')
                log.error(obj.fin)
                return

            if complete != 'true':
                self.query_messages(last)
            else:
                log.info('query finished')
                GLib.idle_add(self.download_history.finished)
                if self.start:
                    timestamp = self.start.timestamp()
                else:
                    timestamp = ArchiveState.ALL
                gajim.config.set_per('accounts', self.account,
                                     'mam_start_date', timestamp)
                log.debug('config: set mam_start_date: %s', timestamp)
                self.set_current_page(Pages.SUMMARY)
                self.summary.finished()


class SelectTimePage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant
        label = Gtk.Label(label=_('How far back do you want to go?'))

        listbox = Gtk.ListBox()
        listbox.set_hexpand(False)
        listbox.set_halign(Gtk.Align.CENTER)
        listbox.add(TimeOption(_('One Month'), 1))
        listbox.add(TimeOption(_('Three Months'), 3))
        listbox.add(TimeOption(_('One Year'), 12))
        listbox.add(TimeOption(_('Everything')))
        listbox.connect('row-selected', assistant.on_row_selected)

        for row in listbox.get_children():
            option = row.get_child()
            if not option.get_delta():
                continue
            if assistant.now - option.get_delta() > assistant.current_start:
                row.set_activatable(False)
                row.set_selectable(False)

        self.pack_start(label, True, True, 0)
        self.pack_start(listbox, False, False, 0)

class DownloadHistoryPage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant
        self.count = 0
        self.received = 0

        pix = get_icon_pixmap('folder-download-symbolic', size=64)
        image = Gtk.Image()
        image.set_from_pixbuf(pix)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text(_('Connecting...'))
        self.progress.set_pulse_step(0.1)
        self.progress.set_vexpand(True)
        self.progress.set_valign(Gtk.Align.CENTER)

        self.pack_start(image, False, False, 0)
        self.pack_start(self.progress, False, False, 0)

    def set_fraction(self):
        self.received += 1
        if self.count:
            self.progress.set_fraction(self.received / self.count)
            self.progress.set_text(_('%s of %s' % (self.received, self.count)))
        else:
            self.progress.pulse()
            self.progress.set_text(_('Downloaded %s Messages' % self.received))

    def finished(self):
        self.progress.set_fraction(1)

class SummaryPage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant

        self.label = Gtk.Label()
        self.label.set_name('FinishedLabel')
        self.label.set_valign(Gtk.Align.CENTER)

        self.pack_start(self.label, True, True, 0)

    def finished(self):
        received = self.assistant.download_history.received
        finished = _('''
        Finshed synchronising your History. 
        {received} Messages downloaded.
        '''.format(received=received))
        self.label.set_text(finished)

    def nothing_to_do(self):
        nothing_to_do = _('''
        Gajim is fully synchronised 
        with the Archive.
        ''')
        self.label.set_text(nothing_to_do)

    def query_already_running(self):
        already_running = _('''
        There is already a synchronisation in 
        progress. Please try later.
        ''')
        self.label.set_text(already_running)

class TimeOption(Gtk.Label):
    def __init__(self, label, months=None):
        super().__init__(label=label)
        self.date = months
        if months:
            self.date = timedelta(days=30*months)

    def get_delta(self):
        return self.date