##	chat_control.py
##
## Copyright (C) 2005-2006 Travis Shirk <travis@pobox.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import gtk.glade
import pango
import gobject
import gtkgui_helpers
import message_window

from common import gajim
from message_window import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'

class ChatControlBase(MessageControl):
	# FIXME
	'''TODO
	Contains a banner, ConversationTextview, MessageTextView
	'''
	
	def draw_banner(self):
		self._paint_banner()
		self._update_banner_state_image()
		# Derived types SHOULD implement this
	def update_state(self):
		self.draw_banner()
		# Derived types SHOULD implement this
	def draw_widgets(self):
		self.draw_banner()
		# Derived types MUST implement this
	def repaint_themed_widgets(self):
		self.draw_banner()
		# NOTE: Derived classes MAY implement this
	def _update_banner_state_image(self):
		pass # Derived types MAY implement this

	def __init__(self, parent_win, widget_name, contact, acct):
		MessageControl.__init__(self, parent_win, widget_name, contact, acct);

		# FIXME: These are hidden from 0.8 on, but IMO all these things need
		#        to be shown optionally.  Esp. the never-used Send button
		for w in ('bold_togglebutton', 'italic_togglebutton',
			'underline_togglebutton'):
			self.xml.get_widget(w).set_no_show_all(True)

		# Create textviews and connect signals
		self.conv_textview = ConversationTextview(None) # FIXME: remove account arg
		self.conv_textview.show_all()
		scrolledwindow = self.xml.get_widget('conversation_scrolledwindow')
		scrolledwindow.add(self.conv_textview)
		self.conv_textview.connect('key_press_event',
				self.on_conversation_textview_key_press_event)
		# add MessageTextView to UI and connect signals
		message_scrolledwindow = self.xml.get_widget('message_scrolledwindow')
		self.msg_textview = MessageTextView()
		self.msg_textview.connect('mykeypress',
					self.on_message_textview_mykeypress_event)
		message_scrolledwindow.add(self.msg_textview)
		self.msg_textview.connect('key_press_event',
					self.on_message_textview_key_press_event)

		# the following vars are used to keep history of user's messages
		self.sent_history = []
		self.sent_history_pos = -1
		self.typing_new = False
		self.orig_msg = ''

		self.nb_unread = 0

	def _paint_banner(self):
		'''Repaint banner with theme color'''
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
		textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
		# the backgrounds are colored by using an eventbox by
		# setting the bg color of the eventbox and the fg of the name_label
		banner_eventbox = self.xml.get_widget('banner_eventbox')
		banner_name_label = self.xml.get_widget('banner_name_label')
		if bgcolor:
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, 
				gtk.gdk.color_parse(bgcolor))
		else:
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, None)
		if textcolor:
			banner_name_label.modify_fg(gtk.STATE_NORMAL,
				gtk.gdk.color_parse(textcolor))
		else:
			banner_name_label.modify_fg(gtk.STATE_NORMAL, None)


	def on_conversation_textview_key_press_event(self, widget, event):
		'''Handle events from the ConversationTextview'''
		print "ChatControl.on_conversation_textview_key_press_event", event
		if event.state & gtk.gdk.CONTROL_MASK:
			# CTRL + l|L
			if event.keyval == gtk.keysyms.l or event.keyval == gtk.keysyms.L:
				self.conv_textview.get_buffer().set_text('')
			# CTRL + v
			elif event.keyval == gtk.keysyms.v:
				if not self.msg_textview.is_focus():
					self.msg_textview.grab_focus()
				self.msg_textview.emit('key_press_event', event)

	def on_message_textview_key_press_event(self, widget, event):
		print "ChatControl.on_message_textview_key_press_event", event

		if event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				self.conv_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				self.conv_textview.emit('key_press_event', event)

	def on_message_textview_mykeypress_event(self, widget, event_keyval,
						event_keymod):
		'''When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation'''

		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_tab(). for this singal see message_textview.py
		jid = self.contact.jid
		message_textview = widget
		message_buffer = message_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False).decode('utf-8')

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		if event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+UP
				self.sent_messages_scroll(jid, 'up', widget.get_buffer())
				return
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+Down
				self.sent_messages_scroll(jid, 'down', widget.get_buffer())
				return
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			# NOTE: SHIFT + ENTER is not needed to be emulated as it is not
			# binding at all (textview's default action is newline)

			if gajim.config.get('send_on_ctrl_enter'):
				# here, we emulate GTK default action on ENTER (add new line)
				# normally I would add in keypress but it gets way to complex
				# to get instant result on changing this advanced setting
				if event.state == 0: # no ctrl, no shift just ENTER add newline
					end_iter = message_buffer.get_end_iter()
					message_buffer.insert_at_cursor('\n')
					send_message = False
				elif event.state & gtk.gdk.CONTROL_MASK: # CTRL + ENTER
					send_message = True
			else: # send on Enter, do newline on Ctrl Enter
				if event.state & gtk.gdk.CONTROL_MASK: # Ctrl + ENTER
					end_iter = message_buffer.get_end_iter()
					message_buffer.insert_at_cursor('\n')
					send_message = False
				else: # ENTER
					send_message = True
				
			if gajim.connections[self.account].connected < 2: # we are not connected
				dialogs.ErrorDialog(_('A connection is not available'),
					_('Your message can not be sent until you are connected.')).get_response()
				send_message = False

			if send_message:
				self.send_message(message) # send the message

	def _process_command(self, message):
		if not message:
			return False
		if message == '/clear':
			self.conv_textview.clear() # clear conversation
			# FIXME: Need this function
			self.clear(self.msg_textview) # clear message textview too
			return True
		elif message == '/compact':
			# FIXME: Need this function
			self.set_compact_view(not self.compact_view_current_state)
			# FIXME: Need this function
			self.clear(self.msg_textview)
			return True
		else:
			return False

	def send_message(self, message, keyID = '', chatstate = None):
		'''Send the given message to the active tab'''
		if not message or message == '\n':
			return

		if not self._process_command(message):
			MessageControl.send_message(self, message, keyID, chatstate)
			# Record message history
			self.save_sent_message(message)

		# Clear msg input
		message_buffer = self.msg_textview.get_buffer()
		message_buffer.set_text('') # clear message buffer (and tv of course)

	def save_sent_message(self, message):
		#save the message, so user can scroll though the list with key up/down
		size = len(self.sent_history)
		#we don't want size of the buffer to grow indefinately
		max_size = gajim.config.get('key_up_lines')
		if size >= max_size:
			for i in xrange(0, size - 1): 
				self.sent_history[i] = self.sent_history[i + 1]
			self.sent_history[max_size - 1] = message
		else:
			self.sent_history.append(message)
			self.sent_history_pos = size + 1

		self.typing_new = True
		self.orig_msg = ''

	def print_conversation_line(self, text, kind, name, tim,
				other_tags_for_name = [], other_tags_for_time = [], 
				other_tags_for_text = [], count_as_new = True, subject = None):
		'''prints 'chat' type messages'''
		jid = self.contact.jid
		textview = self.conv_textview
		end = False
		if textview.at_the_end() or kind == 'outgoing':
			end = True
		textview.print_conversation_line(text, jid, kind, name, tim,
			other_tags_for_name, other_tags_for_time, other_tags_for_text, subject)

		if not count_as_new:
			return
		if kind == 'incoming_queue':
			gajim.last_message_time[self.account][jid] = time.time()
		urgent = True
		if (jid != self.parent_win.get_active_jid() or \
		   not self.parent_win.is_active() or not end) and\
		   	kind in ('incoming', 'incoming_queue'):
			self.nb_unread += 1
			if gajim.interface.systray_enabled and\
				gajim.config.get('trayicon_notification_on_new_messages'):
				gajim.interface.systray.add_jid(jid, self.account,
								self.get_message_type(jid))
			self.redraw_tab(jid)
			self.show_title(urgent)

class ChatControl(ChatControlBase):
	'''A control for standard 1-1 chat'''
	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, parent_win, 'chat_child_vbox', contact, acct);
		self.compact_view = gajim.config.get('always_compact_view_chat')

		# chatstate timers and state
		self._schedule_activity_timers()
		self.reset_kbd_mouse_timeout_vars()

	def _schedule_activity_timers(self):
		self.possible_paused_timeout_id = gobject.timeout_add(5000,
				self.check_for_possible_paused_chatstate, None)
		self.possible_inactive_timeout_id = gobject.timeout_add(30000,
				self.check_for_possible_inactive_chatstate, None)

	def draw_widgets(self):
		# The name banner is drawn here
		ChatControlBase.draw_widgets(self)

	def _update_banner_state_image(self):
		contact = self.contact
		show = contact.show
		jid = contact.jid

		# Set banner image
		img_32 = gajim.interface.roster.get_appropriate_state_images(jid,
									size = '32')
		img_16 = gajim.interface.roster.get_appropriate_state_images(jid)
		if img_32.has_key(show) and img_32[show].get_pixbuf():
			# we have 32x32! use it!
			banner_image = img_32[show]
			use_size_32 = True
		else:
			banner_image = img_16[show]
			use_size_32 = False

		banner_status_img = self.xml.get_widget('banner_status_image')
		if banner_image.get_storage_type() == gtk.IMAGE_ANIMATION:
			banner_status_img.set_from_animation(banner_image.get_animation())
		else:
			pix = banner_image.get_pixbuf()
			if use_size_32:
				banner_status_img.set_from_pixbuf(pix)
			else: # we need to scale 16x16 to 32x32
				scaled_pix = pix.scale_simple(32, 32,
								gtk.gdk.INTERP_BILINEAR)
				banner_status_img.set_from_pixbuf(scaled_pix)

		self._update_gpg()

	def draw_banner(self):
		'''Draw the fat line at the top of the window that 
		houses the status icon, name, jid, and avatar'''
		ChatControlBase.draw_banner(self)

		contact = self.contact
		jid = contact.jid

		banner_name_label = self.xml.get_widget('banner_name_label')
		name = gtkgui_helpers.escape_for_pango_markup(contact.name)
		
		status = contact.status
		if status is not None:
			banner_name_label.set_ellipsize(pango.ELLIPSIZE_END)
			status = gtkgui_helpers.reduce_chars_newlines(status, 0, 2)
		status = gtkgui_helpers.escape_for_pango_markup(status)

		#FIXME: uncomment me when we support sending messages to specific resource
		# composing full jid
		#fulljid = jid
		#if self.contacts[jid].resource:
		#	fulljid += '/' + self.contacts[jid].resource
		#label_text = '<span weight="heavy" size="x-large">%s</span>\n%s' \
		#	% (name, fulljid)
		
		st = gajim.config.get('chat_state_notifications')
		cs = contact.chatstate
		if cs and st in ('composing_only', 'all'):
			if contact.show == 'offline':
				chatstate = ''
			elif st == 'all':
				chatstate = helpers.get_uf_chatstate(cs)
			else: # 'composing_only'
				if chatstate in ('composing', 'paused'):
					# only print composing, paused
					chatstate = helpers.get_uf_chatstate(cs)
				else:
					chatstate = ''
			label_text = \
			'<span weight="heavy" size="x-large">%s</span> %s' % (name,
										chatstate)
		else:
			label_text = '<span weight="heavy" size="x-large">%s</span>' % name
		
		if status is not None:
			label_text += '\n%s' % status

		# setup the label that holds name and jid
		banner_name_label.set_markup(label_text)

	def _update_gpg(self):
		tb = self.xml.get_widget('gpg_togglebutton')
		if self.contact.keyID: # we can do gpg
			tb.set_sensitive(True)
			tt = _('OpenPGP Encryption')
		else:
			tb.set_sensitive(False)
			#we talk about a contact here
			tt = _('%s has not broadcasted an OpenPGP key nor you have '\
				'assigned one') % self.contact.name
		gtk.Tooltips().set_tip(self.xml.get_widget('gpg_eventbox'), tt)

	def send_message(self, message, keyID = '', chatstate = None):
		'''Send a message to contact'''
		if not message or message == '\n' or self._process_command(message):
			return

		contact = self.contact
		jid = self.contact.jid

		keyID = ''
		encrypted = False
		if self.xml.get_widget('gpg_togglebutton').get_active():
			keyID = contact.keyID
			encrypted = True


		chatstates_on = gajim.config.get('chat_state_notifications') != 'disabled'
		chatstate_to_send = None
		if chatstates_on and contact is not None:
			if contact.our_chatstate is None:
				# no info about peer
				# send active to discover chat state capabilities
				# this is here (and not in send_chatstate)
				# because we want it sent with REAL message
				# (not standlone) eg. one that has body
				chatstate_to_send = 'active'
				contact.our_chatstate = 'ask' # pseudo state
			# if peer supports jep85 and we are not 'ask', send 'active'
			# NOTE: first active and 'ask' is set in gajim.py
			elif contact.our_chatstate not in (False, 'ask'):
				#send active chatstate on every message (as JEP says)
				chatstate_to_send = 'active'
				contact.our_chatstate = 'active'

				gobject.source_remove(self.possible_paused_timeout_id)
				gobject.source_remove(self.possible_inactive_timeout_id)
				self._schedule_activity_timers()
				
		ChatControlBase.send_message(self, message, keyID, chatstate_to_send)
		self.print_conversation(message, self.contact.jid, encrypted = encrypted)

	def check_for_possible_paused_chatstate(self, arg):
		''' did we move mouse of that window or write something in message
		textview in the last 5 seconds?
		if yes we go active for mouse, composing for kbd
		if no we go paused if we were previously composing '''
		contact = self.contact
		jid = contact.jid
		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		message_buffer = self.msg_textview.get_buffer()
		if self.kbd_activity_in_last_5_secs and message_buffer.get_char_count():
			# Only composing if the keyboard activity was in text entry
			# FIXME: Need send_chatstate
			self.send_chatstate('composing')
		elif self.mouse_over_in_last_5_secs and\
			jid == self.parent_win.get_active_jid():
			self.send_chatstate('active')
		else:
			if current_state == 'composing':
				self.send_chatstate('paused') # pause composing

		# assume no activity and let the motion-notify or 'insert-text' make them True
		# refresh 30 seconds vars too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever		

	def check_for_possible_inactive_chatstate(self, arg):
		''' did we move mouse over that window or wrote something in message
		textview in the last 30 seconds?
		if yes we go active
		if no we go inactive '''
		contact = self.contact
		jid = contact.jid

		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		if self.mouse_over_in_last_5_secs or self.kbd_activity_in_last_5_secs:
			return True # loop forever

		if not self.mouse_over_in_last_30_secs or self.kbd_activity_in_last_30_secs:
			self.send_chatstate('inactive', jid)

		# assume no activity and let the motion-notify or 'insert-text' make them True
		# refresh 30 seconds too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever

	def reset_kbd_mouse_timeout_vars(self):
		self.kbd_activity_in_last_5_secs = False
		self.mouse_over_in_last_5_secs = False
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False


	def print_conversation(self, text, frm = '', tim = None,
		encrypted = False, subject = None):
		'''Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is set to print_queue: it is incomming from queue
		if contact is not set: it's an incomming message'''
		contact = self.contact
		jid = contact.jid

		if frm == 'status':
			kind = 'status'
			name = ''
		else:
			ec = gajim.encrypted_chats[self.account]
			if encrypted and jid not in ec:
				msg = _('Encryption enabled')
				ChatControlBase.print_conversation_line(self, msg, 
					'status', '', tim)
				ec.append(jid)
			if not encrypted and jid in ec:
				msg = _('Encryption disabled')
				ChatControlBase.print_conversation_line(self, msg,
					'status', '', tim)
				ec.remove(jid)
			self.xml.get_widget('gpg_togglebutton').set_active(encrypted)
			if not frm:
				kind = 'incoming'
				name = contact.name
			elif frm == 'print_queue': # incoming message, but do not update time
				kind = 'incoming_queue'
				name = contact.name
			else:
				kind = 'outgoing'
				name = gajim.nicks[self.account] 
		ChatControlBase.print_conversation_line(self, text, kind, name, tim,
			subject = subject)

