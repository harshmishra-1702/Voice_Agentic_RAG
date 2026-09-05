# Runbook: Primary Database Failover & Replication Recovery

**Document ID:** RB-DB-012  
**Severity:** SEV-1 (Data Layer Disruption)  
**Service:** Core PostgreSQL Cluster (Aurora / Patroni)  
**Owner:** Database Operations & SRE  
**Escalation:** `@dba-oncall` (PagerDuty: `svc-prod-db`), Secondary: `@sre-core-oncall`

---

## 1. Failure Detection & Assessment
Alerts: `PostgresPrimaryUnhealthy`, `ReplicationLagCritical` (>120s), or HTTP 500 spike on API gateways.

Run fast remote probe to verify primary unreachability:
```bash
# Check primary TCP responsiveness
pg_isready -h db-primary.internal -p 5432 -t 3
curl -f http://db-primary.internal:8008/health
```
If primary returns connection refused or times out for 3 consecutive polls:

## 2. Replication Lag Pre-Check
Inspect candidates before promotion to minimize Recovery Point Objective (RPO) loss:
```bash
# On replica node
patronictl -c /etc/patroni/db.yml list
# Or direct PostgreSQL query
psql -h db-replica-01.internal -U postgres -c \
  "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS bytes_behind FROM pg_stat_replication;"
```
*Rule: Promote candidate replica with lowest byte lag (< 16 MB).*

## 3. Promotion & VIP Switch
1. **Promote Standby Node:**
   ```bash
   # Patroni automatic / forced failover
   patronictl failover cluster-prod --candidate db-replica-01 --force
   # Manual standby promotion fallback
   pg_ctl promote -D /var/lib/postgresql/data
   ```
2. **Update Routing / PgBouncer:**
   Shift read-write Virtual IP (Keepalived/Consul) to promoted node:
   ```bash
   consul kv put service/postgres/primary "db-replica-01.internal"
   # Reload PgBouncer pool targets
   psql -p 6432 -U pgbouncer -c "RELOAD;"
   psql -p 6432 -U pgbouncer -c "SHOW POOLS;"
   ```

## 4. Rollback & Stale Primary Isolation
- Immediately STONITH / isolate the old primary to prevent split-brain:
  ```bash
  ssh db-primary.internal "sudo systemctl stop postgresql && sudo systemctl disable postgresql"
  ```
- Re-attach demoted host as read-only replica with `pg_rewind` after cluster stabilization.

## 5. Escalation & Sign-Off
- If replication lag exceeded 1 GB before failover: page `@lead-data-architect` for data divergence check.
- Notify `#incident-room` on Slack once write transactions succeed: `SELECT txid_current();`.
