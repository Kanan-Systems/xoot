# Security Policy

## Supported versions

None yet. xoot is pre-alpha and has no released versions.

## Reporting a vulnerability

Report vulnerabilities through GitHub private vulnerability reporting
(the "Report a vulnerability" button on this repository's Security tab).
Do not open a public issue.

## Threat model

xoot is a local-only tracker. All state lives on the user's machine and is
never stored in this repository. No state is sent to a remote service. The
server exposes no filesystem or shell tools. A client can only read and
write xoot's own tracker records, so a compromised or misbehaving client
cannot use xoot to reach arbitrary files or run commands. The main risks in
scope are corrupting or leaking the local tracker data. Anyone with access
to the user's account already has that data, so that attacker is out of scope.
