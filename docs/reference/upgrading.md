# Upgrade and migration guide

How to move between Quadkit versions deliberately. The policy this page
operationalizes lives in the [support matrix](support-matrix.md) (stability
tiers, deprecation windows); the compatibility rules live in
[stability](stability.md).

## Routine minor upgrade

1. **Read the release notes** for every version you cross — deprecations
   are announced there first, before removal.
2. **Bump all five distributions together.** Lockstep releases mean mixing
   versions is unsupported:
   ```bash
   pip install -U "quadkit==X.Y.Z" "quadkit-web==X.Y.Z" \
     "quadkit-testing==X.Y.Z" "quadkit-cli==X.Y.Z" "quadkit-contracts==X.Y.Z"
   ```
3. **Run your test suite before anything else.** Quadkit's own tests pass
   against the wheels in CI; if yours pass too, the documented surface is
   behaving identically for your use.
4. **Sweep deprecation warnings** emitted by your suite; each one names
   the replacement. A deprecated API stays functional for at least one
   full minor series, so you can migrate incrementally.
5. **Re-run the starter-template discipline**: config schema changes, if
   any, fail fast at boot with the offending section named — run one boot
   locally (`quadkit run` or your `main()`) rather than discovering it in
   production.

## Major version upgrade

Major versions may remove previously deprecated APIs. The sequence is the
same as above, plus:

- Expect to act on every deprecation warning your last passing suite
  printed on the previous major; they are the exact migration list.
- Re-check the [support matrix](support-matrix.md) — Python version floors
  can move on major versions.
- If you pinned integration extras, re-resolve them; extras are validated
  in CI but third-party pins may tighten.

## Staying current by construction

Every public release is reproducibly verified (wheel build, clean-env
install, module import walk, full public test suite, docs accuracy gates,
starter templates from the exported tree). CLI environment checks and
assisted upgrades are [roadmap candidates](../governance/roadmap.md) —
until they land, the five steps above are the supported path. Whether a
configuration is supported can also be verified against the
[secure configuration](../security/secure-configuration.md) checklist
after any upgrade touching deployment inputs.
