## src/upower_listener.py
##
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
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


supported = False

from gajim.common import dbus_support
from gajim.common import app

def on_suspend(*args, **kwargs):
    for name, conn in app.connections.items():
        if app.account_is_connected(name):
            conn.old_show = app.SHOW_LIST[conn.connected]
            st = conn.status
            conn.change_status('offline', _('Machine going to sleep'))
            conn.status = st
            conn.time_to_reconnect = 5

if dbus_support.supported:
    try:
        from gajim.common.dbus_support import system_bus
        bus = system_bus.bus()
        if 'org.freedesktop.UPower' in bus.list_names():
            up_object = bus.get_object('org.freedesktop.UPower',
                '/org/freedesktop/UPower')
            bus.add_signal_receiver(on_suspend, 'Sleeping',
                'org.freedesktop.UPower', 'org.freedesktop.UPower',
                '/org/freedesktop/UPower')
            supported = True
    except Exception:
        pass
