"""Network Topology

The topology consists of one client, two switches and four servers. 
n addition to a controller connected to the swtiches to control the network.

   client --- switch --- switch --- serv1
                  |       |       |
                  |       |       |serv2
                 controller       |
                                  |serv3
                                  |
                                  |serv4
"""

from mininet.topo import Topo

class MyTopo( Topo ):
    

  def __init__( self ):

    # Initialize topology
    Topo.__init__( self )

    # Adding hosts and switches
    client = self.addHost( 'client' )
    server1 = self.addHost( 'serv1' )
    server2 = self.addHost('serv2')
    server3 = self.addHost('serv3')
    server4 = self.addHost('serv4')
    leftSwitch = self.addSwitch( 's3' )
    rightSwitch = self.addSwitch( 's4' )

    # Adding links
    self.addLink( client, leftSwitch )
    self.addLink( leftSwitch, rightSwitch )
    self.addLink( rightSwitch, server1 )
    self.addLink( rightSwitch, server2 )
    self.addLink( rightSwitch, server3 )
    self.addLink( rightSwitch, server4 )


topos = { '1cli4serv': ( lambda: MyTopo() ) }
