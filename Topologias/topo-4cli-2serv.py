"""Network Topology

The topology consists of four clients, two switches and two servers. 
n addition to a controller connected to the swtiches to control the network.

   client1 --- switch --- switch --- serv1
          |        |       |       |
   client2|        |       |       |serv2
          |       controller       
   client3|                        
          |                        
   client4|                        
"""

from mininet.topo import Topo

class MyTopo( Topo ):
    

  def __init__( self ):

    # Initialize topology
    Topo.__init__( self )

    # Adding hosts and switches
    client1 = self.addHost( 'client1' )
    client2 = self.addHost( 'client2' )
    client3 = self.addHost( 'client3' )
    client4 = self.addHost( 'client4' )
    server1 = self.addHost( 'serv1' )
    server2 = self.addHost('serv2')
    leftSwitch = self.addSwitch( 's3' )
    rightSwitch = self.addSwitch( 's4' )

    # Adding links
    self.addLink( client1, leftSwitch )
    self.addLink( client2, leftSwitch )
    self.addLink( client3, leftSwitch )
    self.addLink( client4, leftSwitch )
    self.addLink( leftSwitch, rightSwitch )
    self.addLink( rightSwitch, server1 )
    self.addLink( rightSwitch, server2 )


topos = { '4cli2serv': ( lambda: MyTopo() ) }
