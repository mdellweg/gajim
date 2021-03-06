# -*- coding:utf-8 -*-
## src/common/passwords.py
##
## Copyright (C) 2006 Gustavo J. A. M. Carneiro <gjcarneiro AT gmail.com>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (c) 2009 Thorsten Glaser <t.glaser AT tarent.de>
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

import os
import logging
import gi

from gi.repository import GLib

from gajim.common import app

__all__ = ['get_password', 'save_password']

log = logging.getLogger('gajim.password')

keyring = None
if os.name == 'nt':
    try:
        import keyring
    except ImportError:
        log.debug('python-keyring missing, falling back to plaintext storage')


class PasswordStorage(object):
    """Interface for password stores"""
    def get_password(self, account_name):
        """Return the password for account_name, or None if not found."""
        raise NotImplementedError
    def save_password(self, account_name, password):
        """Save password for account_name. Return a bool indicating success."""
        raise NotImplementedError


class LibSecretPasswordStorage(PasswordStorage):
    """Store password using libsecret"""
    identifier = 'libsecret:'
    def __init__(self):
        gi.require_version('Secret', '1')
        gir = __import__('gi.repository', globals(), locals(), ['Secret'], 0)
        self.Secret = gir.Secret
        self.GAJIM_SCHEMA = self.Secret.Schema.new(
            "org.gnome.keyring.NetworkPassword",
            self.Secret.SchemaFlags.NONE,
            {
                'user': self.Secret.SchemaAttributeType.STRING,
                'server':  self.Secret.SchemaAttributeType.STRING,
                'protocol': self.Secret.SchemaAttributeType.STRING,
            }
        )

    def get_password(self, account_name):
        server = app.config.get_per('accounts', account_name, 'hostname')
        user = app.config.get_per('accounts', account_name, 'name')
        password = self.Secret.password_lookup_sync(self.GAJIM_SCHEMA,
            {'user': user, 'server': server, 'protocol': 'xmpp'}, None)
        return password

    def save_password(self, account_name, password, update=True):
        server = app.config.get_per('accounts', account_name, 'hostname')
        user = app.config.get_per('accounts', account_name, 'name')
        display_name = _('XMPP account %s') % user + '@' + server
        attributes = {'user': user, 'server': server, 'protocol': 'xmpp'}
        try:
            return self.Secret.password_store_sync(
                self.GAJIM_SCHEMA, attributes, self.Secret.COLLECTION_DEFAULT,
                display_name, password or '', None)
        except GLib.Error as error:
            log.error(error)
            return False


class SecretWindowsPasswordStorage(PasswordStorage):
    """ Windows Keyring """
    identifier = 'winvault:'

    def __init__(self):
        self.win_keyring = keyring.get_keyring()

    def save_password(self, account_name, password):
        try:
            self.win_keyring.set_password('gajim', account_name, password)
            return True
        except:
            log.exception('error:')
            return False

    def get_password(self, account_name):
        log.debug('getting password')
        return self.win_keyring.get_password('gajim', account_name)

class PasswordStorageManager(PasswordStorage):
    """Access all the implemented password storage backends, knowing which ones
    are available and which we prefer to use.
    Also implements storing directly in gajim config (former
    SimplePasswordStorage class)."""

    def __init__(self):
        self.preferred_backend = None

        self.libsecret = None
        self.winsecret = None

        self.connect_backends()
        self.set_preferred_backend()

    def connect_backends(self):
        """Initialize backend connections, determining which ones are available.
        """
        # TODO: handle disappearing backends

        if app.config.get('use_keyring'):
            if os.name == 'nt' and keyring:
                self.winsecret = SecretWindowsPasswordStorage()
            else:
                try:
                    self.libsecret = LibSecretPasswordStorage()
                except (ValueError, AttributeError) as e:
                    log.debug("Could not connect to libsecret: %s" % e)

    def get_password(self, account_name):
        pw = app.config.get_per('accounts', account_name, 'password')
        if not pw:
            return pw
        if pw.startswith(LibSecretPasswordStorage.identifier) and \
        self.libsecret:
            backend = self.libsecret
        elif pw.startswith(SecretWindowsPasswordStorage.identifier) and \
        self.winsecret:
            backend = self.winsecret
        else:
            backend = None

        if backend:
            pw = backend.get_password(account_name)
        if backend != self.preferred_backend:
            # migrate password to preferred_backend
            self.preferred_backend.save_password(account_name, pw)
            # TODO: remove from old backend
        return pw

    def save_password(self, account_name, password):
        if self.preferred_backend:
            if self.preferred_backend.save_password(account_name, password):
                app.config.set_per('accounts', account_name, 'password',
                    self.preferred_backend.identifier)
                if account_name in app.connections:
                    app.connections[account_name].password = password
                return True

        app.config.set_per('accounts', account_name, 'password', password)
        if account_name in app.connections:
            app.connections[account_name].password = password
        return True

    def set_preferred_backend(self):
        if self.libsecret:
            self.preferred_backend = self.libsecret
        elif self.winsecret:
            self.preferred_backend = self.winsecret
        else:
            self.preferred_backend = None

    def has_keyring(self):
        """Is there a real password storage backend? Else, passwords are stored
        plain in gajim config"""
        return bool(self.preferred_backend)

passwordStorageManager = None

def get_storage():
    global passwordStorageManager
    if not passwordStorageManager:
        passwordStorageManager = PasswordStorageManager()
    return passwordStorageManager

def get_password(account_name):
    return get_storage().get_password(account_name)

def save_password(account_name, password):
    if account_name in app.connections:
        app.connections[account_name].set_password(password)
    return get_storage().save_password(account_name, password)
