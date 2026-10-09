# Workspace A → B: reviewed P4 Git Bundle

Workspace A is authorized for local development, testing, commit and bundle only.
No push, force-push, remote credentials/account change or main merge was performed.
The approved bundle prerequisite is P3 evidence commit
`e6501b4d64e428e503db5ae2e624e8188ff8bfd7`; the branch is
`migration/cloud-api-security`. The exact P4 commit and bundle SHA-256 are supplied
in the completion report and the untracked transfer receipt alongside the bundle.
Bundle verification does not mean unconditional security acceptance; review the
P4 report and its remaining environmental gate before any deployment.

Workspace A creates and verifies a bundle containing only the approved-base range:

```sh
git merge-base --is-ancestor e6501b4d64e428e503db5ae2e624e8188ff8bfd7 HEAD
git bundle create /workspace/cloud-api-p4.bundle \
  e6501b4d64e428e503db5ae2e624e8188ff8bfd7..migration/cloud-api-security
git bundle verify /workspace/cloud-api-p4.bundle
git bundle list-heads /workspace/cloud-api-p4.bundle
sha256sum /workspace/cloud-api-p4.bundle
```

Import is also checked in a disposable bare repository initialized with the exact
approved prerequisite, followed by fetching the bundle and verifying its branch
head. No generated secrets, uncommitted files, private keys or ignored artifacts
are part of Git's bundle.

## Workspace B

Copy the bundle and receipt through the authorized file-transfer channel. Set
`P4_COMMIT` to the exact completion-report/receipt SHA, **not** an abbreviated or
guessed value. Check its bundle digest against the receipt before importing.
Preserve any local work; the following assumes a clean working tree.

```sh
git status --short
git fetch origin
git bundle verify /path/cloud-api-p4.bundle
git bundle list-heads /path/cloud-api-p4.bundle
git fetch /path/cloud-api-p4.bundle \
  refs/heads/migration/cloud-api-security:refs/heads/p4-import-review
test "$(git rev-parse p4-import-review)" = "$P4_COMMIT"
git merge-base --is-ancestor \
  e6501b4d64e428e503db5ae2e624e8188ff8bfd7 p4-import-review
git log --oneline origin/migration/cloud-api-security..p4-import-review
git diff --name-only origin/migration/cloud-api-security..p4-import-review
git diff --stat origin/migration/cloud-api-security..p4-import-review
```

Independently inspect changed contents for secrets/private keys, verify the tests
and acceptance classification, and compare any new remote commits. If the remote
has diverged, stop for review rather than rewriting its history. Once Workspace B
has authorization to synchronize this reviewed candidate:

```sh
git merge-base --is-ancestor origin/migration/cloud-api-security p4-import-review
git switch migration/cloud-api-security
git merge --ff-only p4-import-review
test "$(git rev-parse HEAD)" = "$P4_COMMIT"
git push -u origin migration/cloud-api-security
git ls-remote origin refs/heads/migration/cloud-api-security
```

The final remote SHA must equal the reviewed P4 SHA. These are instructions for
Workspace B; Workspace A stops after its local commit/bundle/report. No later
phase or production cutover is authorized by the transfer itself.
