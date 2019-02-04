"""
Random load balancer

Run it with --ip=<Service IP> --servers=IP1,IP2,...

"""

from pox.core import core
import pox
log = core.getLogger("iplb")

from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.util import str_to_bool, dpid_to_str, str_to_dpid
from pox.forwarding.l2_learning import LearningSwitch

import pox.openflow.libopenflow_01 as of

import time
import random

FLOW_IDLE_TIMEOUT = 10
FLOW_MEMORY_TIMEOUT = 60 * 5

selected_server = 0



class MemoryEntry (object):
  """
  Record for flows we are balancing

  Table entries in the switch "remember" flows for a period of time, but
  rather than set their expirations to some long value (potentially leading
  to lots of rules for dead connections), we let them expire from the
  switch relatively quickly and remember them here in the controller for
  longer.

  """
  def __init__ (self, server, first_packet, client_port):
    self.server = server
    self.first_packet = first_packet
    self.client_port = client_port
    self.refresh()


  def refresh (self):
    self.timeout = time.time() + FLOW_MEMORY_TIMEOUT

  @property
  def is_expired (self):
    return time.time() > self.timeout

  @property
  def key1 (self):
    ethp = self.first_packet
    ipp = ethp.find('ipv4')
    tcpp = ethp.find('tcp')

    return ipp.srcip,ipp.dstip,tcpp.srcport,tcpp.dstport

  @property
  def key2 (self):
    ethp = self.first_packet
    ipp = ethp.find('ipv4')
    tcpp = ethp.find('tcp')

    return self.server,ipp.srcip,tcpp.dstport,tcpp.srcport


class iplb (object):
  """
  IP load balancer

  """
  def __init__ (self, connection, service_ip, servers = []):
    self.service_ip = IPAddr(service_ip)
    self.servers = [IPAddr(a) for a in servers]
    self.con = connection
    self.mac = self.con.eth_addr
    self.live_servers = {} # IP -> MAC,port
    self.servers_map = {}

    try:
      self.log = log.getChild(dpid_to_str(self.con.dpid))
    except:
      
      self.log = log

    self.outstanding_probes = {} # IP -> expire_time

    # expected time of an ARP response before we consider a dead server.
    self.probe_cycle_time = 5

    # How long do we wait for an ARP reply before we consider a server dead?
    self.arp_timeout = 3

    # We remember where we directed flows so that if they start up again,
    # we can send them to the same server if it's still up.
    self.memory = {} # (srcip,dstip,srcport,dstport) -> MemoryEntry

    self._do_probe() 


  def _do_expire (self):
    """
    Expire probes and "memorized" flows

    """
    t = time.time()

    # Expire probes
    for ip,expire_at in self.outstanding_probes.items():
      if t > expire_at:
        self.outstanding_probes.pop(ip, None)
        if ip in self.live_servers:
          self.log.warn("Server %s down", ip)
          del self.live_servers[ip]

    # Expire old flows
    c = len(self.memory)
    self.memory = {k:v for k,v in self.memory.items()
                   if not v.is_expired}
    if len(self.memory) != c:
      self.log.debug("Expired %i flows", c-len(self.memory))

  def _do_probe (self):
    """
    Send an ARP to a server to see if it's still up
    """
    self._do_expire()

    server = self.servers.pop(0)
    self.servers.append(server)

    r = arp()
    r.hwtype = r.HW_TYPE_ETHERNET
    r.prototype = r.PROTO_TYPE_IP
    r.opcode = r.REQUEST
    r.hwdst = ETHER_BROADCAST
    r.protodst = server
    r.hwsrc = self.mac
    r.protosrc = self.service_ip
    e = ethernet(type=ethernet.ARP_TYPE, src=self.mac,
                 dst=ETHER_BROADCAST)
    e.set_payload(r)
    #self.log.debug("ARPing for %s", server)
    msg = of.ofp_packet_out()
    msg.data = e.pack()
    msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
    msg.in_port = of.OFPP_NONE
    self.con.send(msg)

    self.outstanding_probes[server] = time.time() + self.arp_timeout

    core.callDelayed(self._probe_wait_time, self._do_probe)

  @property
  def _probe_wait_time (self):
    """
    Time to wait between probes
    """
    r = self.probe_cycle_time / float(len(self.servers))
    r = max(.25, r) # Cap it at four per second
    return r

  def _pick_server (self, key, inport):
    #choosing server with round robin
    global selected_server
    a=self.live_servers.keys()
    if selected_server==len(self.live_servers):
        selected_server=0
    b=a[selected_server]
    selected_server+=1
    return b


  def _handle_PacketIn (self, event):
    inport = event.port
    packet = event.parsed

    def drop ():
      if event.ofp.buffer_id is not None:
        # Kill the buffer
        msg = of.ofp_packet_out(data = event.ofp)
        self.con.send(msg)
      return None

    tcpp = packet.find('tcp')
    if not tcpp:
      arpp = packet.find('arp')
      if arpp:
        # Handle replies to our server-liveness probes
        if arpp.opcode == arpp.REPLY:
          if arpp.protosrc in self.outstanding_probes:
        
            del self.outstanding_probes[arpp.protosrc]
            if (self.live_servers.get(arpp.protosrc, (None,None))
                == (arpp.hwsrc,inport)):
              
              pass
            else:
              # detecting new server.
              self.live_servers[arpp.protosrc] = arpp.hwsrc,inport
              self.log.info("Server %s up", arpp.protosrc)
        return

      # Not TCP and not ARP. Drop it.
      return drop()

    # It's TCP.

    ipp = packet.find('ipv4')

    if ipp.srcip in self.servers:
      # It's FROM one of our balanced servers.
      # Rewrite it BACK to the client

      key = ipp.srcip,ipp.dstip,tcpp.srcport,tcpp.dstport
      entry = self.memory.get(key)

      if entry is None:
        # We either didn't install it, or we forgot about it.
        self.log.debug("No client for %s", key)
        return drop()

      # Refresh time timeout and reinstall.
      entry.refresh()

      #self.log.debug("Install reverse flow for %s", key)

      # Install reverse table entry
      mac,port = self.live_servers[entry.server]

      actions = []
      actions.append(of.ofp_action_dl_addr.set_src(self.mac))
      actions.append(of.ofp_action_nw_addr.set_src(self.service_ip))
      actions.append(of.ofp_action_output(port = entry.client_port))
      match = of.ofp_match.from_packet(packet, inport)

      msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                            idle_timeout=FLOW_IDLE_TIMEOUT,
                            hard_timeout=of.OFP_FLOW_PERMANENT,
                            data=event.ofp,
                            actions=actions,
                            match=match)
      self.con.send(msg)

    elif ipp.dstip == self.service_ip:
      # it's for our service IP and needs to be load balanced

      # Do we already know this flow?
      key = ipp.srcip,ipp.dstip,tcpp.srcport,tcpp.dstport
      entry = self.memory.get(key)
      if entry is None or entry.server not in self.live_servers:
        # Don't know it (hopefully it's new!)
        if len(self.live_servers) == 0:
          self.log.warn("No servers!")
          return drop()

        # Pick a server for this flow
        server = self._pick_server(key, inport)
        if server not in self.servers_map:
            self.servers_map[server] = 1
        else:
            self.servers_map[server] += 1
        self.log.debug(self.servers_map)
        self.log.debug("Directing traffic to %s", server)
        entry = MemoryEntry(server, packet, inport)
        self.memory[entry.key1] = entry
        self.memory[entry.key2] = entry

      # Update timestamp
      entry.refresh()

      # Set up table entry towards selected server
      mac,port = self.live_servers[entry.server]

      actions = []
      actions.append(of.ofp_action_dl_addr.set_dst(mac))
      actions.append(of.ofp_action_nw_addr.set_dst(entry.server))
      actions.append(of.ofp_action_output(port = port))
      match = of.ofp_match.from_packet(packet, inport)

      msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                            idle_timeout=FLOW_IDLE_TIMEOUT,
                            hard_timeout=of.OFP_FLOW_PERMANENT,
                            data=event.ofp,
                            actions=actions,
                            match=match)
      self.con.send(msg)


# Remember which DPID we're operating on (first one to connect)
_dpid = None


def launch (ip, servers, dpid = None):
  global _dpid
  if dpid is not None:
    _dpid = str_to_dpid(dpid)

  servers = servers.replace(","," ").split()
  servers = [IPAddr(x) for x in servers]
  ip = IPAddr(ip)
  

  from proto.arp_responder import ARPResponder
  old_pi = ARPResponder._handle_PacketIn
  def new_pi (self, event):
    if event.dpid == _dpid:
      # Yes, the packet-in is on the right switch
      return old_pi(self, event)
  ARPResponder._handle_PacketIn = new_pi

  # Hackery done.  Now start it.
  from proto.arp_responder import launch as arp_launch
  arp_launch(eat_packets=False,**{str(ip):True})
  import logging
  logging.getLogger("proto.arp_responder").setLevel(logging.WARN)


  def _handle_ConnectionUp (event):
    global _dpid
    if _dpid is None:
      _dpid = event.dpid

    if _dpid != event.dpid:
      log.warn("Ignoring switch %s", event.connection)
      LearningSwitch(event.connection, False)
    else:
      if not core.hasComponent('iplb'):
        # Need to initialize first...
        core.registerNew(iplb, event.connection, IPAddr(ip), servers)
	#log.info("DPID:", _dpid)
        log.info("IP Load Balancer Ready.")
      log.info("Load Balancing on %s", event.connection)

      # Gross hack
      core.iplb.con = event.connection
      event.connection.addListeners(core.iplb)


  core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
