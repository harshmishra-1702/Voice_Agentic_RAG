# Runbook: Load Balancer Health, Pool Draining & TLS Diagnostics

**Document ID:** RB-EDGE-005  
**Severity:** SEV-1 (Traffic Blackhole) / SEV-2 (Backend Flapping)  
**Service:** Edge Layer (HAProxy / Nginx Ingress)  
**Owner:** Traffic & Edge SRE  
**Escalation:** `@edge-oncall` (Slack `#edge-traffic-war-room`), Secondary: `@secops-oncall`

---

## 1. Initial Assessment
Alerts: `BackendPoolDegraded` (>30% nodes down), `Http5xxRateSpike`, or `TlsHandshakeErrors`.

Inspect runtime status via HAProxy admin socket or Nginx status:
```bash
# Query HAProxy backend pool status via socket
echo "show stat" | sudo socat stdio /var/run/haproxy.sock | cut -d ',' -f 1,2,18,37 | column -s ',' -t

# Or query local Nginx ingress controller status
curl -s http://127.0.0.1:10254/healthz
```

## 2. Backend Health Checks & Connection Draining
If specific backend instances fail health checks (`L7STS: HTTP 503` or timeout):
1. Test target backend node directly:
   ```bash
   curl -Iv -H "Host: api.internal" http://10.0.2.45:8080/healthz
   ```
2. **Gracefully Drain Unhealthy Node:**
   ```bash
   # Set state to DRAIN (completes existing connections, rejects new ones)
   echo "set server be_app_pool/app-node-03 state drain" | sudo socat stdio /var/run/haproxy.sock
   
   # After active connections reach zero:
   echo "set server be_app_pool/app-node-03 state maint" | sudo socat stdio /var/run/haproxy.sock
   ```

## 3. TLS / SSL Certificate Expiration & Handshake Failures
Verify certificate validity and chain completeness:
```bash
# Check remote cert expiry and issuer
echo | openssl s_client -servername api.service.com -connect 127.0.0.1:443 2>/dev/null | openssl x509 -noout -dates -issuer

# Check local cert bundle before reloading
openssl x509 -in /etc/ssl/certs/lb_bundle.crt -noout -enddate
```
If expired, hot-reload renewed certs without dropping sockets:
```bash
haproxy -f /etc/haproxy/haproxy.cfg -c && sudo systemctl reload haproxy
# Or Nginx:
nginx -t && sudo nginx -s reload
```

## 4. Emergency Rate Limiting Adjustment
If load balancer CPU spikes > 90% due to DDoS / aggressive scraper:
```bash
# Dynamically adjust stick-table rate limit window in HAProxy
echo "set table req_rate_limit value 500" | sudo socat stdio /var/run/haproxy.sock
```

## 5. Escalation
- All backends DOWN (`NOSRV` error): page `@backend-infra-lead`.
- Edge DDOS exceeding 50 Gbps: escalate to Cloudflare/Tier-1 DDoS mitigation provider.
