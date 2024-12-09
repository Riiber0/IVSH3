import os

#os.system("route")

##client
##creat tables
##net['client'].cmd('ifconfig client-eth1 10.0.2.2')
#net['client'].cmd('ip rule add from 10.0.1.2 table 1')
#net['client'].cmd('ip rule add from 10.0.2.2 table 2')

##table config
#net['client'].cmd("ip route add 10.0.1.0/24 dev client-eth0 scope link table 1")
#net['client'].cmd("ip route add default via 10.0.1.1 dev client-eth0 table 1")


#net['client'].cmd("ip route add 10.0.2.0/24 dev client-eth1 scope link table 2")
#net['client'].cmd("ip route add default via 10.0.2.1 dev client-eth1 table 2")


##default route
#net['client'].cmd("ip route add default scope global nexthop via 10.0.1.1 dev client-eth0")

"""
os.system('sudo ifconfig ingress-cell 127.0.0.1')

print('sudo ip rule add from 127.0.0.1 table 2')
os.system('sudo ip rule add from 127.0.0.1 table 2')

print("sudo ip route add 127.0.0.1 dev ingress-cell scope link table 2")
os.system("sudo ip route add 127.0.0.1 dev ingress-cell scope link table 2")

print("sudo ip route add default via 127.0.0.1 dev ingress-cell table 2")
os.system("sudo ip route add default via 127.0.0.1 dev ingress-cell table 2")

print("sudo ip route add default scope global nexthop via 127.0.0.1 dev ingress-cell")
os.system("sudo ip route add default scope global nexthop via 127.0.0.1 dev ingress-cell")

#os.system("ip link show")
#os.system("route")
"""

#os.system("ifconfig")
#os.system("ping 10.0.2.15")
#os.system("iperf3 -c 127.0.0.1")
os.system("curl -k https://10.0.2.15:4242/dash_tiled.mpd")

