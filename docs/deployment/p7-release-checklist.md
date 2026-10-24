# P7 release checklist and transfer

**No production deployment, main merge or Workspace A push is approved.**
Read [the acceptance matrix](../testing/p7-results.md) before considering release.
The user deferred public-DNS tests, not the strict release gate. Current advisory
validation must also complete; offline audit0 is not a clean vulnerability scan.

## Operator gate

- Verify exact P6 base, P7 parent/tree, clean working tree and public source hashes.
- Inspect active P4/P5/P6 overlays; confirm OIDC-only authentication and no fallback.
- Match browser/IdP/API stable HTTPS origins, callbacks, audience, CA/SAN/enrollment.
- Preserve existing IDs, mappings, account flags and database-controlled roles.
- Require executed end-to-end/browser, RBAC/BOLA, HMAC/replay/concurrency, SSRF,
  validation, SQL input and rate-limit controls; correlate selected Loki events.
- Require verified TLS/mTLS negative/rotation and DB privilege/isolation checks.
- Rehearse paired backups/restores and a reviewed compatible rollback. Protect keys,
  secrets and receipts; define off-host recovery scope and objectives separately.
- Restore supported raw DNS, run the exact three affected IDs first, then full
  unfiltered candidate and legacy regressions. Do not add hosts records or mocks.
- Complete version-aware advisory/image scans, review high/critical reachability
  and remediate or explicitly block release. Do not silently upgrade infrastructure.
- Verify privacy, collector mounts after recreation, four dashboard query sets and
  six alert rules. External notification delivery needs separate configuration/test.
- Close every mandatory BLOCKED/FAIL/NOT EXECUTED entry before strict PASS.

## Workspace B import (commands to review, not executed here)

Use the external transfer manifest for the exact bundle SHA256 and P7 tip; do not
substitute a short hash based solely on this example. First verify a clean checkout,
correct branch and remote. Fetch before choosing the approved remote base.

```sh
sha256sum /path/to/cloud-api-p7.bundle
git bundle verify /path/to/cloud-api-p7.bundle
git fetch origin
git switch migration/cloud-api-security
git status
git fetch /path/to/cloud-api-p7.bundle refs/heads/migration/cloud-api-security:refs/remotes/p7-transfer/migration/cloud-api-security
git merge-base --is-ancestor HEAD p7-transfer/migration/cloud-api-security
git merge --ff-only p7-transfer/migration/cloud-api-security
git log -3 --format=fuller
git diff --check origin/migration/cloud-api-security..HEAD
```

Stop on an ancestry mismatch; no reset, rebase, amend or force push. Independently
review changed files for secrets/private keys and confirm author/committer email
`nhpntd@gmail.com`. Only after separately authorized Workspace B approval:

```sh
git merge-base --is-ancestor origin/migration/cloud-api-security HEAD
git push origin migration/cloud-api-security
git ls-remote origin refs/heads/migration/cloud-api-security
```

The actual local bundle verification and fresh local import are recorded outside
the commit to avoid self-referential hashes. Publishing a candidate does not accept
it or authorize production deployment. Preserve all P0–P6 commits.
