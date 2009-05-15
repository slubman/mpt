#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Copyright (C) 2008 Grégoire Menuel <xmpp:omega@im.apinc.org>

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License only.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import mpt_publish
import mpd
import time
from socket import error as socketerror

import mpt_config

WAIT_RECONNECT=30
WAIT_SEND=10

class MpdConnector:

  def __init__(self):
    self.mpd=None
    self.lastchange=0

  def connect(self):
    try:
      self.mpd=mpd.MPDClient()
      self.mpd.connect(host = mpt_config.mpd_host, port = mpt_config.mpd_port)
    except socketerror:
      return False
    return True

  def disconnect(self):
    try:
      self.mpd.disconnect()
    except EOFError:
      pass

  def is_connected(self):
    if not self.mpd:
      return False
    try:
      self.mpd.ping()
    except EOFError:
      return False
    return True

  def is_playing(self):
    play=self.mpd.status()['state']
    if (play == 'play') :
      return True
    else:
      return False

  def has_waited_enough(self):
    if (time.time()-self.lastchange>WAIT_SEND):
      self.lastchange=time.time()
      return True
    else:
      return False


  # return False if something went wrong
  def main_loop(self,pub):
    if not self.mpd:
      return False
    if not self.has_waited_enough():
      return True
    try:
      chan=self.mpd.currentsong()
      play=self.is_playing()
    except EOFError:
      return False
  #  if (chan==pub.song && chan.artist==pub.song.artist && chan.title==pub.song.title && chan.song.album==pub.song.album && chan.track==pub.song.track && chan.duration==pub.song.duration && play==pub.playing):
    if play and (chan.has_key('title') or chan.has_key('name')) and pub.song:
      if (chan['file'] != pub.song['file'] or play!=pub.playing):
        pub.song=chan
        pub.playing=play
        pub.publish()
    else:
      if (play!=pub.playing):
        pub.song=chan
        pub.playing=play
        pub.publish()
    return True

pub=mpt_publish.publish(mpt_config.jid, mpt_config.password, mpt_config.ressource)
mpd_con = MpdConnector()
if not pub.connect():
  print "Unable to connect to XMPP, exiting"
  sys.exit(1)
if not mpd_con.connect():
  print "Unable to connect to MPD, exiting"
  pub.disconnect()
  sys.exit(2)

def try_connect_mpd():
  while(not mpd_con.connect()):
    time.sleep(WAIT_RECONNECT)
  pub.connect()

def try_connect_xmpp():
  while(not pub.connect()):
    time.sleep(WAIT_RECONNECT)
  mpd_con.connect()


while(1):
  try:
    if not mpd_con.main_loop(pub):
      print "Connexion with the mpd server lost, waiting "+str(WAIT_RECONNECT)+"s before trying to reconnect."
      time.sleep(WAIT_RECONNECT)
      if not mpd_con.connect():
        print "MPD server still gone, disconnecting from XMPP, will reconnect when MPD server will be available."
        pub.disconnect()
        time.sleep(WAIT_RECONNECT)
        try_connect_mpd()

    if pub.con.Process(1) is None:
      print "Connexion with the XMPP server lost, waiting "+str(WAIT_RECONNECT)+"s before trying to reconnect."
      time.sleep(WAIT_RECONNECT)
      if not pub.connect():
        print "XMPP server still gone, disconnecting from MPD, will reconnect when XMPP server will be available."
        mpd_con.disconnect()
        time.sleep(WAIT_RECONNECT)
        try_connect_xmpp()
    time.sleep(1)
  except KeyboardInterrupt:
    print "Exiting..."
    break
  
pub.disconnect()
mpd_con.disconnect()
