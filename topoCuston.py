from mininet.topo import Topo

class Extopo(Topo):
    def __init__(self, **opts):
        Topo.__init__(self)

        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        self.addLink(h1, s1, bw=20)
        self.addLink(h1, s2, bw=20)
        self.addLink(h2, s1, bw=20)
        self.addLink(h2, s2, bw=20)


topos = {'ex1': (lambda : Extopo())}
a = Extopo()
