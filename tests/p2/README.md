# P2 disposable HTTPS/mTLS verification

From the repository root, with Python, Docker Desktop/Linux containers and Node.js:

```powershell
python -m pip install -r docker/pki-requirements.txt
Set-Location frontend
npm ci
Set-Location ..
python tests/p2/run.py
```

This runs the **main deployment**, with P1/P2 test overlays: unique Compose project,
new isolated volumes, random file secrets and development PKI in a temporary directory.
Never point it at an existing deployment. No shared production volume/network is used.
Only an ephemeral loopback HTTPS port is published for the gateway host/Vite checks.
The privileged test container and all test credentials/certificates are disposable.

Execution: complete P0 + P1 pytest, original 16 P1 host checks with verified readiness
transport, P2 socket tests + actual HTTPS business tests, then Kong negative TLS,
enrollment, CA/leaf/edge rotation/recovery, runtime mount/log and Vite trust tests.
The unchanged Kong rate limiter is exhausted explicitly by P0; HTTPS business checks
are spaced to honor the same limit. Unexpected 429 responses still fail business tests.

Ignored local outputs: `artifacts/junit.xml`, `p2-junit.xml`, pytest and host reports,
safe TLS evidence, command inventory, inspected container metadata and `run.json`.
`run.json` must have exit_code=0 and cleanup_completed=true for acceptance. Success
requires every unexpected failure/error count to be zero, not merely a healthy stack.
Six existing strict defects are repeated through HTTPS; the original seven remain in
the full P0 suite. Remote HTTPS cannot monkeypatch DNS or the server's clock, so exact
DNS/IP and timestamp-boundary cases remain in P0's real-DB TestClient tests; P2 also
checks real public DNS, blocked targets and signed webhook cases over HTTPS.

No keys/certificates are committed, no verification is bypassed, and the runner's
`finally` cleans only its random Compose project's containers/networks/volumes.
See [trust/rotation/recovery](../../docs/deployment/p2-tls.md) and
[execution record](../../docs/testing/p2-results.md).
