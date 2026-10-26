# Kong OSS LTS upgrade / rollback gates

2026-10-26. **No upgrade or rollback drill was performed.** No qualifying official
OSS LTS artifact was selected. Active Compose pins and configuration remain at
the approved baseline; the local documentation commits do not activate images.

Baseline artifact:
`kong:3.9.3@sha256:92035d16d7ff86b7bc12fb1d0090d29357d924238b1880f78735f3f2fea6b631`.
Both inspected 3.9.4 artifacts were rejected as REL-001 remedies; see the
[assessment](../security/kong-oss-openssl-lts-remediation.md). No operational
rollback is necessary for this research. The newly downloaded vendor image remains
inactive in the local cache; no user volume, service or network was modified.

## Future candidate procedure — NOT EXECUTED

1. Verify an official OSS release, license, immutable linux/amd64 manifest, actual
   supported/patched OpenSSL linkage and current advisory scan. Do not infer OSS
   availability from Enterprise release notes or substitute Windows DLLs.
2. Establish safe physical host and Docker capacity for the full isolated baseline.
   Generate test credentials/PKI only in private disposable runtime directories.
   Use a unique Compose project with its own volumes; never attach user data.
3. Create a separate candidate overlay changing only the qualified image pin and
   any explicitly justified compatibility fields. Preserve original source/pins.
   Record matching DB-less declarative output, signing-key generation, CA trust,
   leaf/client enrollment, Lua modules, P5 settings, UID/key modes and prefix.
4. Validate configuration and startup, then all security groups in the
   [validation matrix](../testing/kong-oss-lts-validation.md), followed by the full
   unfiltered original P0–P7 runners. No runtime image-reference update is approved
   until mandatory acceptance passes.
5. In the same **disposable** environment, recreate only the gateway with the
   original image and matching config/enrollment. DB-less Kong needs no Kong DB
   migration; do not change application or identity database schema/data.
6. Reverify CA/SAN/EKU, invalid-client/server rejection, JWT and key rotation,
   rate-limit recovery, routes, backend authorization and log privacy/correlation.
   Do not restore revoked/expired signing keys or use TLS bypasses to recover.
7. Record image/config hashes, actual commands, exits, recovery timing and test
   evidence before declaring rollback demonstrated. Clean up only resources whose
   unique task labels/project ownership are confirmed; no global pruning.

Rollback to 3.9.3 restores the previous operational state, **not a supported crypto
lifecycle**. It does not close REL-001. Any custom maintained build, Enterprise
edition or gateway migration remains a separately scoped proposal requiring owner
decision. No such proposal was silently implemented; no Loki or Part B work began.
