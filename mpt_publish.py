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

import xmpp
import xmpp.features
import sys
import time


NS_TUNE = "http://jabber.org/protocol/tune"

class publish:
  def __init__(self,jid,secret,resource):
    self.jid=jid
    self.fulljid=jid+"/"+resource
    self.secret=secret
    self.resource=resource
    self.song=None
    self.lastchange=time.time()
    self.playing=False
    self.connected=False
    self.connectedResources=[]
    self.canPublish=False
  
  def connect(self):
    jid_parts=self.jid.split('@',1)
    self.host=jid_parts[1]
    self.con=xmpp.Client(jid_parts[1], debug=[])
    try:
      if not self.con.connect():
        print "Couldn't connect to host"
        return False
    except IOError, e:
        print "Couldn't connect: %s" % e
        return False
    else:
        print "Connected"
    if self.con.auth(jid_parts[0],self.secret,self.resource):
        print u"Logged in as %s to server %s" % ( jid_parts[0], jid_parts[1])
    else:
        print "eek -> ", self.con.lastErr, self.con.lastErrCode
        sys.exit(1)
    self.connected=True
    self.con.RegisterDisconnectHandler(self.disconnecthand)
    self.con.RegisterHandler('presence', self.presenceHandler)
    #check pep support
    if not self.checkSupport():
      print self.host+" doesn't seem to support PEP (XEP-0163), exiting ..."
      self.con.disconnect()
      sys.exit(2)
    # check for invisible list existence
    if not self.check_invisible_list():
      self.create_invisible_list()
    self.activate_invisible_list()
    pres = xmpp.Presence(priority=-100)
    self.con.send(pres)
    print "Waiting for connected resources before publishing tune."
    return True

  def disconnecthand(self):
    self.connected=False

  def presenceHandler(self, con, pres):
    fromjid=pres.getFrom()
    resource=fromjid.getResource()
    if fromjid.bareMatch(self.jid) and self.resource != resource and resource != "":
      if pres.getType() == 'unavailable' and resource in self.connectedResources:
        self.connectedResources.remove(resource)
      elif pres.getType() == None and resource not in self.connectedResources:
        self.connectedResources.append(resource)
      else:
        return
      if len(self.connectedResources) > 0:
        print "A resource is now connected, publishing tune..."
        self.canPublish=True
        self.publish()
      else:
        print "No more resource online, unpublishing tune..."
        self.canPublish=False
        self.unpublish()

  def disconnect(self):
    self.playing=False
    self.publish()
    self.con.disconnect()

  def checkSupport(self):
    info=xmpp.features.discoverInfo(self.con,self.host)
    ids=info[0]
    find=False
    for id in ids:
      if id.has_key('type') and id.has_key('category'):
        if id['category']=='pubsub' and id['type']=='pep':
          find=True
          break
    return find

  def check_invisible_list(self):
    request=xmpp.Iq(typ="get")
    request.addChild("query", namespace=xmpp.NS_PRIVACY)
    rep = self.con.SendAndWaitForResponse(request, timeout=25)
    children = rep.getQueryChildren()
    has_privacy=False
    if children is not None:
      for child in children:
        if child.getName() == "list" and child.getAttr("name") == "invisible":
          has_privacy=True
    return has_privacy

  def create_invisible_list(self):
    iq=xmpp.Iq(typ="set");
    iq.query=iq.addChild("query", namespace=xmpp.NS_PRIVACY)
    iq.query.list=iq.query.addChild("list", attrs={"name":"invisible"})
    iq.query.list.item=iq.query.list.addChild("item", attrs={"action":"deny", "order":"1"})
    iq.query.list.item.addChild("presence-out")
    self.con.send(iq)

  def activate_invisible_list(self):
    iq=xmpp.Iq(typ="set");
    iq.query=iq.addChild("query", namespace=xmpp.NS_PRIVACY)
    iq.query.addChild("active", attrs={"name":"invisible"})
    self.con.send(iq)

  def unpublish(self):
    iq=xmpp.Iq(typ="set")
    iq.pubsub=iq.addChild("pubsub",namespace=xmpp.NS_PUBSUB)
    iq.pubsub.publish=iq.pubsub.addChild("publish",attrs={"node":NS_TUNE})
    iq.pubsub.publish.item=iq.pubsub.publish.addChild("item",attrs={"id":"current"})
    tune=iq.pubsub.publish.item.addChild("tune")
    tune.setNamespace(NS_TUNE)
    self.con.send(iq)

  def publish(self):
    if not self.canPublish:
      return
    iq=xmpp.Iq(typ="set")
    iq.pubsub=iq.addChild("pubsub",namespace=xmpp.NS_PUBSUB)
    iq.pubsub.publish=iq.pubsub.addChild("publish",attrs={"node":NS_TUNE})
    iq.pubsub.publish.item=iq.pubsub.publish.addChild("item",attrs={"id":"current"})
    tune=iq.pubsub.publish.item.addChild("tune")
    tune.setNamespace(NS_TUNE)
    if self.song and self.playing:
      if self.song.has_key('title'):
        title = self.song['title']
      elif self.song.has_key('name'):
        title = self.song['name']
      else:
        title = self.song['file']
        if title.endswith('.mp3') or title.endswith('.ogg'):
          title = title[:-4]
      tune.addChild("title").addData(unicode(title,'utf8'))
      if (self.song.has_key('artist')):
        tune.addChild("artist").addData(unicode(self.song['artist'],'utf8'))
      if (self.song.has_key('album')):
        tune.addChild("source").addData(unicode(self.song['album'],'utf8'))
      if (self.song.has_key('pos') and self.song['pos'] > 0):
        tune.addChild("track").addData(str(self.song['pos']))
      if (self.song.has_key('time')):
        tune.addChild("length").addData(str(self.song['time']))
      print "Publishing song "+title
    else:
      print "Paused"

    #print iq.__str__().encode('utf8')
    self.con.send(iq)
