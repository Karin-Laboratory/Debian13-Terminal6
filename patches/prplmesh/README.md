# Local prplMesh patch provenance

- Upstream: `https://gitlab.com/prpl-foundation/prplmesh/prplMesh`
- Revision: `5ba21ee04a3b34f0d99635eeacd547d78cb67efe` (prplMesh 6.0.1)
- Upstream license: BSD-2-Clause-Patent, see upstream `LICENSE`.
- Patch: `0001-linux-bpl-configurable-radios-and-secure-security-modes.patch`

The patch changes the Linux BPL radio-name lookup to permit two private platform-database mappings and rejects unsupported wireless security labels instead of silently treating them as open. It does not contain vendor binaries, device data, credentials, or full upstream source files. Apply only to the exact revision above and retain the upstream license notice when distributing a built product.
