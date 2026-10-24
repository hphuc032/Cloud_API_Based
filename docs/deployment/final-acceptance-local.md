# Local final-acceptance runner

Use a fresh checkout/snapshot and disposable Compose projects. Never point these
runners at production volumes. P3 runs the historical legacy contract; P7 runs the
active OIDC candidate and inherited P4/P5/P6 groups. Neither is a production cutover.

## Linux and Docker Desktop / WSL

Use Linux Python, Node/npm, Docker Compose, Chromium and NSS/certutil. Install
the committed frontend lockfile with `npm ci --prefix frontend` in the disposable
checkout; Windows and Linux node_modules cannot be shared. Install the tooling
requirements in an isolated venv. The existing browser helpers expect
`/usr/lib/chromium/chromium`; configure the Linux test environment accordingly.
Do not disable certificate verification or change the host's personal CA store.

On native Linux, leave `CLOUD_API_DESKTOP_LOGS` unset. Log binds use stable service
targets so a changed backend CID replaces its old source when Compose merges
volumes. `docker/render_collector.py` continues selecting only backend, Kong and
Keycloak from the explicitly named project.

On Docker Desktop with Ubuntu WSL integration, opt in explicitly:

```sh
export CLOUD_API_DESKTOP_LOGS=1
export CLOUD_API_DESKTOP_BROWSER=1
# Optional when Docker Desktop is installed elsewhere:
export CLOUD_API_DESKTOP_DOCKER='/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe'
export CLOUD_API_KEEP_PROBES=1
export P3_RELEASE_BUILD_CACHE=0 P4_RELEASE_BUILD_CACHE=0
python tests/p3/run.py
python tests/p7/run.py
```

`tests/project_logs.py` uses the Windows Docker CLI to address real engine log
paths. WSL's Linux CLI translates `/var/lib/docker/containers` into the Ubuntu
filesystem, which may be empty. The adapter creates a stopped, no-network,
read-only holder with dropped capabilities, no secrets and exactly three read-only
log-directory binds. Compose inherits these using its supported
`container:<name>:ro` syntax. No collector receives a Docker socket, host-wide log
root or unrelated container logs. No log content is copied or synthesized.
The holder's mounts are checked before the collector can start.

After backend recreation, P7 replaces its single `collector.json`, refreshes the
holder and recreates Alloy. Appending another overlay can accumulate stale mounts
or duplicate `volumes_from`, so there must be one configuration owner. The holder
is removed after the owned Compose project is torn down. Existing observability
volumes retain collector positions and Grafana/Loki state during the recovery drill.

P3 uses the same opt-in adapter for the historical Promtail contract. Active P6/P7
continues using Alloy. Readiness alone is insufficient: original suites must prove
actual backend events reached Loki, including after backend recreation.

The operator running tests already needs Docker host authority. The adapter does
not grant this authority to application or collector containers. It is a test-only
Windows/WSL execution mode; normal Linux deployment does not require the holder.

The separate browser option requires Bubblewrap (`bwrap`). Docker Desktop's
engine-host network and WSL loopback are separate: a running engine-side CDP
listener is not necessarily accessible to the WSL Node runner. The adapter runs
Chromium in a private user/PID/mount namespace on WSL's network, with read-only
libraries, a cleared child environment and only its disposable profile writable.
It receives no application secrets, Docker socket or personal NSS store. Chromium
145 uses `/tmp/.pki/nssdb` when HOME is absent; that location is linked to the
generated trust database inside the private namespace. The host HOME is unchanged.
See the [Chromium NSS implementation](https://raw.githubusercontent.com/chromium/chromium/145.0.7632.6/crypto/nss_util.cc)
and [home-directory fallback](https://raw.githubusercontent.com/chromium/chromium/145.0.7632.6/base/files/file_util_posix.cc).

A disposable unprivileged TCP relay joins only the project's OIDC transport and
publishes an ephemeral loopback port. Chromium's private `identity-edge` alias
selects that port while preserving the original HTTPS origin, SNI, CA and SAN
verification. The relay forwards encrypted bytes and has no certificates, keys,
database membership or log-content processing. Public DNS and SSRF tests are not
substituted. Native Linux retains the existing container browser path. Both modes
retain the original browser assertions and must pass without TLS bypass flags.

For this constrained lab, a private Compose overlay sets
`KONG_NGINX_WORKER_PROCESSES=2`; production Compose remains unchanged. This bounds
test resource usage, not security policy. Record the overlay with each result and
do not infer production throughput from these local acceptance runs. Prefer a
native WSL filesystem for the disposable checkout and its Linux node_modules;
retain results separately before WSL shutdown.

P1's original image-layer secret check exports a full Docker image archive. On
hosts with limited system-drive space, set `P1_IMAGE_AUDIT_TMPDIR` to an existing
private directory on a spacious drive. Only archive storage changes; all original
images, layers and generated-secret checks still execute. The temporary archive
is removed by the test and must never be committed.

## Failure diagnosis and recovery

Kong's `kong health` checks process existence, which can precede the HTTPS
listener/configuration. P2 host checks now use bounded, certificate-verifying edge
HTTPS readiness, accepting upstream 502 only while a negative upstream TLS case
is staged. Original negative-certificate and final HTTP-status assertions remain.
Vite's host readiness loop also treats a socket-read timeout as pending startup,
within a fixed deadline; a wrong CA must still produce the original proxy 500.

Rate-limit recovery waits for the actual next wall-clock minute and rechecks it
after each wake, bounded by a monotonic deadline. A single relative sleep cannot
prove Kong's wall-clock bucket advanced on a VM. Response evidence records status,
Date, rate-limit headers and generated correlation IDs; it excludes Authorization,
tokens, response bodies and credentials. Limits and abuse assertions are unchanged.

If a run fails, retain its ignored artifacts before repeating. Teardown must be
restricted to the exact generated project and its labeled holder. Do not prune
globally, delete unrelated containers, or reuse old application/database volumes.
An incomplete/failed runner remains a failed run even when a later focus succeeds.

See [current remediation evidence](../testing/final-acceptance-remediation.md)
for exact executed versions, commands, outcomes and unresolved release risks.
