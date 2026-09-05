# Runbook: Network Outage & Layer 2/3 Diagnostics

**Document ID:** RB-NET-009  
**Severity:** SEV-1 / SEV-2  
**Service:** WAN Edge, Transit Routers & VPC Peering  
**Owner:** Network Reliability Engineering  
**Escalation:** `@netops-oncall` (Slack `#edge-net-fire`), Escalation: `@network-sec-lead`

---

## 1. Diagnostic Matrix
Triggers: `BlackHoleTrafficAlert`, `BgpPeerStateDown`, or cross-region packet loss > 2%.

Identify failure layer immediately:
- **Total disconnect / timeout:** Check physical link & BGP peers.
- **Intermittent stall / partial payload loss:** Check Path MTU & DSCP tagging.
- **Single subnet reachability drop:** Check VLAN tags & 802.1Q trunking.

## 2. Layer 3 Diagnostics & BGP Session Checks
Run hop-by-hop latency and packet loss analysis:
```bash
# Detailed MTR report (100 packets, non-blocking)
mtr --report --report-cycles 100 --no-dns 10.100.20.1

# TCP traceroute to bypass ICMP deprioritization
traceroute -T -p 443 10.100.20.1
```
Check edge router BGP neighbor state via FRRouting/Cisco CLI:
```bash
vtysh -c "show ip bgp summary"
vtysh -c "show ip bgp neighbors 198.51.100.1 advertised-routes"
```
*Action:* If neighbor state is `Active` or `Idle`, clear BGP session gracefully:
```bash
vtysh -c "clear ip bgp 198.51.100.1 soft in"
```

## 3. MTU & Fragmentation Verification
Verify Path MTU blackholing (common after tunnel or overlay reconfiguration):
```bash
# Test 1500 byte payload with Don't Fragment (DF) bit set
ping -c 4 -M do -s 1472 10.100.20.1

# If failing, test standard overlay MTU (VXLAN/Geneve = 1450)
ping -c 4 -M do -s 1422 10.100.20.1
```
If drops occur at 1472, adjust ingress MSS clamping on the border router:
```bash
iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```

## 4. VLAN & Trunk Integrity Checks
Inspect switch trunk interfaces for VLAN drop counters:
```bash
show interfaces trunk
show mac address-table vlan 400
```
Ensure native VLAN mismatch does not trigger STP blockage.

## 5. Escalation Threshold
- Transit ISP degradation > 10m: page transit carrier NOC with circuit ID from `/etc/circuits.conf`.
- Routing table flap frequency > 5/min: page `@netops-lead`.
