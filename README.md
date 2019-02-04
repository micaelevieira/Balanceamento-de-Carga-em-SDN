# Balanceamento-de-Carga-em-SDN

- ip_loadbalance_random.py: código para o balanceamento de carga aleatório
- ip_loadbalance_rr: código para balanceamento de carga com round robin.
  -Exemplo de uso: pox/pox.py log.level --DEBUG misc.ip_loadbalancer_random --ip=10.0.1.1 --servers=10.0.0.2,10.0.0.3,10.0.0.4,10.0.0.5 --dpid=00-00-00-00-00-04

  Importante passar o caminho certo do arquivo, nesse caso está dentro da pasta misc, dentro concontrolador pox.


- scripts run run1 run2 run3: realizam repetidas requisições http.

- A pasta topologia contém 3 diferentes topologias para serem executadas no mininet.
Exemplo: sudo mn --custom ~/caminho/topo-1cli-4serv.py --topo 1cli4serv --controller=remote,port=6633

