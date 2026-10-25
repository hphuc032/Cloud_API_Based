# Git evidence integrity repair — 2026-10-25

This repair concerns evidence portability only. It changes no application,
authentication, deployment, scanner findings or historical test results. The
previous four commits remain unchanged. No push, merge or production operation
is authorized by this record. The security release remains **BLOCKED** by the
previously documented unresolved advisory/lifecycle risks; that is separate
from the integrity gate for transferring the branch to GitHub.

## Root cause and original generation

The pre-repair revision is `0ccdaac26253645dd3eee687fe65831c0aec791d`, descending
from the approved remote baseline
`0b86cf04b471662f7731efac8f2cb34066752441`. Its manifest has149 entries.
All149 matched the Windows working files, but only92 matched Git blob bytes.
For each of the57 mismatches, converting the corresponding committed LF bytes
to CRLF reproduced the complete Windows file, including its recorded SHA256
and length. All34 raw SARIF/SPDX records already matched the committed bytes.

The local configuration has `core.autocrlf=true`. Existing `.gitattributes`
only pins shell scripts to LF. Git normalized the57 text files on staging,
after their Windows working-file hashes had been recorded.

The old ad hoc manifest-generation command was not preserved as a standalone
tracked generator. Inspection of the available ignored publisher found the
curation logic, not manifest generation. The old manifest's measured semantics
are exactly `len(path.read_bytes())` and
`hashlib.sha256(path.read_bytes()).hexdigest()` for all149 original working
files. This is a reproducible diagnosis, not a claim that the historical
command text has been recovered. The tracked utility below now provides the
exact generation and verification commands.

## Integrity model

- **Git blob SHA256:** `sha256` and `bytes` in the schema-v2 manifest mean the
  SHA256 and length of the exact Git blob payload. This is a content digest,
  distinct from Git's own object ID, which also hashes an object header.
- **Working-tree SHA256:** a hash of `Path.read_bytes()` describes that checkout
  only. It can differ because of CRLF/LF conversion. It is not the authoritative
  manifest check and is never substituted for a blob digest.
- **External archive SHA256:** no archive is introduced by this repair. A future
  archive needs a separate digest of the archive bytes and member-byte manifest;
  those values must not silently replace Git blob digests.
- Paths remain relative to the manifest's directory. Its149-member set is
  unchanged. The manifest excludes itself to avoid recursive hashing. This new
  note and the utility/tests are outside that historical evidence-member set.
- The old manifest and its original working-file hashes remain available in the
  previous commit. Historical bytes/provenance are not rewritten.
- The manifest establishes content consistency, not a signature or independent
  attestation of the source commit's authenticity.

Neither `.gitattributes` nor `core.autocrlf` is changed. Historical scanner output
is not rewritten or normalized. Committed blob verification works regardless
of a reader's checkout newline settings.

## Tracked utility and future staging workflow

[Verifier/generator](../../tests/p7/verify_manifest.py) uses only Python's standard
library and Git. Verification is read-only. It reads both the manifest and all
evidence from the selected Git target, never from arbitrary checkout files.
Revision mode resolves one immutable tree; index mode captures stage-0 path/OID
mappings once, so later index changes cannot mix the selected blob contents.
Unmerged indexes, missing blobs, wrong counts, duplicate/unsafe paths,
self-reference and incorrect length/digest fail closed.

```sh
# Verify the committed manifest and evidence in the same HEAD tree.
python -B tests/p7/verify_manifest.py --revision HEAD

# Generate from the intended future index, not an outdated HEAD.
# First stage only the specifically reviewed evidence changes, if any.
python -B tests/p7/verify_manifest.py --index --write
git add -- docs/security/final-image-evidence-20261025/manifest.json
python -B tests/p7/verify_manifest.py --index

# Independently exercise failure cases in throwaway Git repositories.
python -B tests/p7/test_manifest_integrity.py
```

`--write` writes only the working manifest and does not stage it. Verification
before restaging would read the old staged manifest; therefore the intervening
`git add` is mandatory. Any later evidence staging requires regeneration and
another index check. Do not regenerate an archive manifest from checkout bytes.

## Executed candidate validation

| Check | Result | Exit code |
|---|---|---:|
| Original Windows working files |149/149; diagnostic only|0|
| Original committed blobs |92/149;57 newline-only mismatches|0, diagnostic assertions passed|
| Windows `--index --write` |149-member manifest generated from index blobs|0|
| Windows `--index` after staging |149/149 valid|0|
| Windows standalone utility tests, Python3.14.2 |9/9 PASS|0|
| Native clean WSL candidate clone, Python3.12.3, `--index` |149/149 valid|0|
| Native clean WSL utility tests |9/9 PASS|0|
| All57 previously mismatching entries |57/57 match corrected blob digests|0|
| Historical raw SARIF/SPDX |34/34 byte-identical to pre-repair Git blobs|0|
| Native LF checkout diagnostic |149/149 working bytes match canonical blob hashes|0|
| Untracked files in candidate clone |0|0|
| Staged Gitleaks8.30.1, default rules, no allowlist |0 findings|0|
| Staged `git diff --check` |PASS|0|
| Relevant staged Markdown links |31 checked,0 broken|0|

The initial sandboxed Windows fixture run could not access its sandbox temporary
Git directories and failed setup/cleanup. WSL was also inaccessible from that
sandbox. Both were rerun with the authorized local access needed for disposable
repositories; the actual Windows and WSL tests above passed. No test assertion
was weakened to handle that environmental limitation.

The isolated native Linux candidate was created by these actual operations:
`git clone --no-hardlinks --no-checkout`, `git config core.autocrlf false`,
`git checkout --detach` at the pre-repair revision, and `git apply --index -`
with the exact staged binary diff. Both utility commands ran inside that clone.
No ignored wrapper, user document, Docker resource or production volume was used.

The final post-commit gate repeats the verifier against committed HEAD on
Windows and a fresh native Linux checkout, checks the57 repaired entries and34
unchanged raw blobs, and resolves local Markdown/evidence references. Its exact
commit SHA is reported after committing; it cannot be embedded in its own file.

## Privacy, preservation and scope

New tracked code/documentation includes no machine hostname, container ID,
absolute user-local path, credential, token or private key. The test identity
uses an `.invalid` email and newly allocated temporary repositories. Existing
environment metadata remains historical evidence; it is not recopied or
silently redacted by changing its bytes.

All raw scans, inventories, risk registers, source/security changes and prior
regression results remain in Git. No raw evidence is externalized. Only the57
incorrect manifest length/digest pairs and explicit integrity metadata change
inside the historical evidence directory. Local Git diff review and Gitleaks
cover the repair before committing; no scanner allowlist/suppression is added.
This evidence-only repair does not rerun or claim another P0–P7 application
regression or resolve the outstanding container-security release risks.
