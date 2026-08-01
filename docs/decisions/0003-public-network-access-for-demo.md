# 3. Hybrid network access for the demonstration deployment

Date: 2026-07-31
Status: Accepted

## Context

An existing internal reference implementation deploys Microsoft Foundry with VNet
injection, private endpoints, private DNS zones and `publicNetworkAccess: 'Disabled'`.
That is the correct posture for a regulated customer's production landing zone, and the
session's reference architecture material describes it.

This repository is a demonstration asset presented from a laptop over the public
internet on a fixed date. The two situations have different failure modes.

A fully private deployment would require VPN or bastion connectivity to reach the
Foundry portal data plane, the Search service and the agent endpoints from the
presenting machine. It also lengthens provisioning and introduces private DNS
resolution as a live dependency. In the reference implementation this topology
contributed to a deployment failure requiring retry.

## Decision

Interactive demonstration surfaces deploy with public network access and required Entra
authentication. Blob Storage is private: public and shared-key access are disabled,
Azure AI Search uses a shared private link, and corpus seeding runs through a transient
private endpoint.

Broader private networking is **presented as production architecture**, not fully
deployed. The session still covers VNet injection and API Management as an AI gateway in
its reference-architecture material.

## Consequences

Interactive surfaces are reachable from any machine with the right identity, which
removes the largest avoidable failure mode on the day. Corpus content remains behind a
private storage endpoint.

Provisioning is materially faster and has fewer moving parts, which matters against a
fixed deadline.

The deployment is **not** a template for the customer's production environment, and must
not be presented as one. When network isolation is discussed, the honest statement is
that this environment trades isolation for presentability, and that the production
pattern is the one on the reference architecture slide. Saying otherwise to a regulated
financial institution would be a material misrepresentation.

Mitigations that keep the posture defensible despite public access:

- `disableLocalAuth: true` on the Foundry account; no API keys exist to leak.
- `publicNetworkAccess: 'Disabled'` and `allowSharedKeyAccess: false` on storage.
- An approved Search shared private link to the Blob subresource.
- Managed identity for every service-to-service call.
- Role assignments at the narrowest practical scope; no runtime identity holds `Owner`
  or `Contributor`.
- Synthetic data only, so a disclosure would expose nothing real.
