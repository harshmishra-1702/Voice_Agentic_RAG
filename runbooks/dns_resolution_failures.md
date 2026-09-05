# Runbook: DNS Resolution & Name Service Recovery

**Document ID:** RB-DNS-002  
**Severity:** SEV-1 (Total Service Degradation) / SEV-2 (Degraded Lookup)  
**Service:** Internal CoreDNS / Unbound & Public Route53  
**Owner:** Core Infrastructure SRE  
**Escalation:** `@infra-oncall` (Slack `#dns-incidents`), Escalation: `@systems-lead`

---

## 1. Incident Indicators
- `DNSResolutionTimeout` firing across Kubernetes clusters.
- Microservices logging `getaddrinfo EAI_AGAIN` or `NXDOMAIN`.
- Inter-service gRPC RPCs failing with connection refused.

## 2. Immediate Diagnostic Steps
Determine whether resolution failure is local, recursive, or authoritative:

```bash
# 1. Query local node-cache resolver
dig +timeout=2 +tries=2 api.prod.internal @127.0.0.53

# 2. Query upstream authoritative resolver directly
dig @10.0.0.2 api.prod.internal A +trace

# 3. Check for DNSSEC validation errors (SERVFAIL with DO bit set)
dig api.prod.internal +dnssec +multiline
dig api.prod.internal +cdflag  # Checking Disabled: if CD succeeds, DNSSEC is failing
```

## 3. Remediation & Cache Flush Procedures
### A. Flush Local Node & Systemd Caches
Execute across impacted nodes via Ansible or ad-hoc SSH:
```bash
# Systemd-resolved systems
sudo resolvectl flush-caches
sudo resolvectl statistics

# CoreDNS daemonset reload (Kubernetes)
kubectl rollout restart daemonset coredns -n kube-system
```

### B. Upstream / Split-Horizon Mismatch
If public resolution returns stale IP while internal resolves split-horizon records incorrectly:
1. Verify zone serial synchronization between masters:
   ```bash
   dig @ns1.infra.internal prod.internal SOA +short
   dig @ns2.infra.internal prod.internal SOA +short
   ```
2. Inspect negative TTL caching: if an NXDOMAIN was cached, purge specific record:
   ```bash
   rndc flushname api.prod.internal
   ```

## 4. Verification
- Validate latency and return codes:
  ```bash
  for i in {1..10}; do dig +noall +stats api.prod.internal | grep "Query time"; done
  ```
- Target: Query time < 15ms with `status: NOERROR`.

## 5. Escalation Path
- If upstream root/TLD latency > 500ms: activate secondary DNS provider via AWS Route53 traffic policy.
- Contact external registrar / DNS managed service: ticket priority P1 if DNSSEC keys expired.
