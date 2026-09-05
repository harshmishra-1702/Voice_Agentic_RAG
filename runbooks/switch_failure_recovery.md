# Runbook: Top-of-Rack (ToR) Switch Failure Recovery

**Document ID:** RB-NET-004  
**Severity:** SEV-1 (Production Impacting)  
**Service:** Core Fabric / DataCenter Layer 2/3  
**Owner:** Network Engineering & SRE  
**Escalation:** `@netops-oncall` (Slack `#prod-net-incidents`), Escalation Mgr: `@duty-sre-lead`

---

## 1. Symptoms & Detection
- Alert `SwitchPortFlapping` or `InterfaceDown` triggered on Prometheus/Alertmanager.
- High rate of SNMP traps (`linkDown`, `ospfIfStateChange`).
- Sudden packet drop (>5%) or host unreachability in rack unit `rack-[a-z][0-9]+`.

## 2. Immediate Triage (0-5 minutes)
Log into the peer or affected ToR switch via out-of-band console (`console.oob.dc1.internal`):

```bash
# Check port status and flapping history
show interface status | grep -E "down|flap"
show logging last 100 | grep -i "link-down"

# Inspect optical DOM metrics and SFP module health
show interfaces transceiver detail
show environment
```
- **Action:** If light levels (`Rx Power`) are below -18 dBm, inspect physical LC fiber patch and reseat SFP+ module.
- If control-plane CPU is pinned at 100%, check for spanning-tree loops:
```bash
show spanning-tree active
```

## 3. Recovery Procedure
If the hardware or line card is non-responsive, trigger manual failover to the redundant leaf switch (`sw-tor-b`):

1. **Shift Traffic (MLAG/LACP Force-Down):**
   ```bash
   configure terminal
   interface port-channel 10
   shutdown
   exit
   ```
2. **Reconfigure VLAN Tagging & STP Root Guard:**
   Confirm secondary switch assumed active forwarding:
   ```bash
   show mlag
   show spanning-tree vlan 100,200 detail
   ```
3. **Flush Stale ARP & MAC Tables:**
   ```bash
   # On switch and gateway
   clear mac address-table dynamic
   clear ip arp
   # On Linux edge nodes in rack
   ip neigh flush all
   ```

## 4. Post-Incident Verification
- Verify edge servers restored connectivity: `ping -c 5 -I eth0 10.0.0.1`
- Confirm zero dropped packets on active interface: `show interface counters errors`
- Ensure BGP/OSPF peerings restored: `show ip bgp summary`

## 5. Escalation Criteria
- If secondary switch fails to take active forwarding within 60s: page `@network-architect`.
- If physical chassis failure is verified: dispatch `@datacenter-ops` for emergency hot-swap (SLA: 45 min).
