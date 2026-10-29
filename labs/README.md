# Topologia de pisos con OSPF multiarea

Laboratorio de Packet Tracer 9.0.1 con tres routers ISR4331, tres switches 2960-24TT y tres PCs.

## Archivos

- `topologia_pisos.pkt`: topologia visual, sin direccionamiento ni OSPF.
- `topologia_pisos_ospf.pkt`: topologia completa con IPs, gateways y OSPF multiarea.

## Direccionamiento

| Equipo | Interfaz | IP |
| --- | --- | --- |
| Router2 | GigabitEthernet0/0/0 | 192.168.30.1/24 |
| Router2 | Serial0/1/0 | 12.0.13.1/29 |
| Router1 | GigabitEthernet0/0/0 | 192.168.10.1/24 |
| Router1 | Serial0/1/0 | 12.0.13.2/29 |
| Router1 | Serial0/1/1 | 12.0.12.1/29 |
| Router0 | GigabitEthernet0/0/1 | 192.168.20.1/24 |
| Router0 | Serial0/1/0 | 12.0.12.2/29 |
| PC2 | FastEthernet0 | 192.168.30.10/24, gateway 192.168.30.1 |
| PC1 | FastEthernet0 | 192.168.10.10/24, gateway 192.168.10.1 |
| PC0 | FastEthernet0 | 192.168.20.10/24, gateway 192.168.20.1 |

## OSPF

Proceso `ospf 1`.

| Red | Area | Router |
| --- | --- | --- |
| 192.168.30.0/24 | 1 | Router2 |
| 12.0.13.0/29 | 1 | Router2 - Router1 |
| 192.168.10.0/24 | 0 | Router1 |
| 12.0.12.0/29 | 0 | Router1 - Router0 |
| 192.168.20.0/24 | 0 | Router0 |

Router1 es el ABR: `Serial0/1/0` queda en el Area 1 y `Serial0/1/1` mas la LAN en el Area 0.

Router2 y Router0 son DCE de los enlaces seriales (`clock rate 128000`).
