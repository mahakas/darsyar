# Phase 9: Production Hardening & Release

**Status:** Planned; before public launch  
**Dependencies:** All in-scope MVP phases

## Goal

Prove operational reliability, privacy, security and recoverability before exposure to real students.

## In scope

- [ ] Security review, dependency/image pinning and supply-chain checks.
- [ ] Load tests against R-025 targets; costs and provider failure drills.
- [ ] Encrypted off-host PostgreSQL backups and tested restore.
- [ ] Retention/delete/export, privacy consent and refund policy approval.
- [ ] HTTPS/CSP/headers, graceful shutdown, alerting and incident runbooks.
- [ ] Production transaction and SMS tests with authorized credentials.

## Out of scope

- Claiming legal compliance without owner/legal review

## Acceptance criteria

- [ ] All hard gates in AGENTS v4 Appendix C pass.
- [ ] No accepted high-severity unresolved risks.
- [ ] Backup restore demonstrated.
- [ ] Owner approves consent/privacy/refund and source licenses.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.


## Implemented verification slice — 2026-11-12 (not phase acceptance)

- Nginx reverse-proxy template adds `X-Frame-Options: DENY` in addition to CSP `frame-ancestors 'none'`.
- API proxy responses use `Cache-Control: no-store`.
- Production static frontend marks `index.html` as `no-store`.
- New CI job validates both Nginx configurations with the same `nginx:1.28-alpine` image used by the frontend production image, then runs an HTTP response-header smoke test for the static frontend.

Still NOT RUN / not established: production HTTPS/TLS certificate/domain, HSTS at the real TLS terminator, full CSP report-only/violation validation across OAuth/payment flows, dependency/image vulnerability scan, load/provider failure drills, encrypted off-host backup and restore test, privacy/legal approvals, production SMS/payment tests and owner production approval. Phase 9 remains Planned.


## Supply-chain reporting baseline — 2026-11-12 (report-only; not phase acceptance)

- CI job `supply-chain` uses Trivy Action pinned to the verified immutable commit `ed142fd0673e97e23eac54620cfb913e5ce36c25` (release v0.36.0) and Trivy binary `v0.76.2`.
- It scans repository files for vulnerabilities, misconfiguration and secrets, then scans the exact digest-resolved base images for pgvector/PostgreSQL, Redis, Nginx, Python and Node.
- The resolved `RepoDigests` are logged for every scan and Trivy JSON reports are uploaded as a 30-day workflow artifact.
- **Initial policy is report-only:** Trivy uses `exit-code: 0` so baseline findings can be triaged and recorded before a defensible severity threshold/allowlist is adopted. This does not mean any finding is accepted or safe.
- Dockerfile base references are still version tags rather than digest-pinned references; this job records the immutable digests actually scanned but does not yet change build inputs.

Remaining: triage each finding, decide severity/false-positive policy, pin production base images by digest after compatibility review, generate and verify SBOM/provenance attestations, and add an enforced gate only after the baseline is reviewed. Phase 9 remains Planned.
