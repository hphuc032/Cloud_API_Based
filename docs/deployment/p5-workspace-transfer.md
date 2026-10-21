# P5 Workspace B transfer

Workspace A creates a local commit and verified bundle only. No push, credential change or P0–P4 rewrite is part of P5. The transfer manifest beside `cloud-api-p5.bundle` records the exact commit, tree, bundle SHA-256 and successful verification/import checks. The P5 commit must have parent `11136585a0bade4144976bd3a0500d6f36503f28`.

Read the P5 results and acceptance limitations before promoting this candidate. DNS failures are not approval for production rollout. A local-only commit's restoration through environment publication is not established; keep the bundle and manifest outside the ephemeral workspace.

In Workspace B, use a clean checkout with the approved P4 base available. Verify the received bundle SHA-256 against the manifest, then:

```sh
git status --short
git bundle verify /path/to/cloud-api-p5.bundle
git fetch /path/to/cloud-api-p5.bundle \
  refs/heads/migration/cloud-api-security:refs/remotes/p5-transfer/migration/cloud-api-security
git merge-base --is-ancestor 11136585a0bade4144976bd3a0500d6f36503f28 \
  refs/remotes/p5-transfer/migration/cloud-api-security
git switch migration/cloud-api-security
git merge --ff-only refs/remotes/p5-transfer/migration/cloud-api-security
git rev-parse HEAD HEAD^{tree} HEAD^
```

Compare all three SHAs with the manifest. Stop for missing prerequisites, local edits or divergence; do not reset, cherry-pick, rewrite or force-push automatically. Earlier P4 `f48dff3` has the same source tree but a different commit identity and is not the bundle's required parent.

Only in the separately authorized Workspace B, after reviewing the candidate and confirming existing GitHub permissions:

```sh
git fetch origin
git merge-base --is-ancestor origin/migration/cloud-api-security HEAD
# Continue only when the preceding command exits 0.
git push origin migration/cloud-api-security
git ls-remote origin refs/heads/migration/cloud-api-security
```

The remote SHA must equal the manifest's P5 commit. No force option is needed. Commit author/committer email is `nhpntd@gmail.com`; this metadata does not determine which GitHub account authenticates a push.
