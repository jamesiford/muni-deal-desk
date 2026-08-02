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
authentication. The Foundry account is created with `networkInjections` targeting a
dedicated subnet, so managed evaluations and hosted workloads have an outbound private
path while the portal remains reachable from the presenter's browser. Blob Storage is
private: public and shared-key access are disabled, Azure AI Search uses a shared private
link, and corpus seeding runs as a short-lived ACI in a persistent delegated subnet.

Inbound Foundry private endpoints, VPN access and API Management are **presented as
production architecture**, not deployed in the demo environment.

## Consequences

Interactive surfaces are reachable from any machine with the right identity, which
removes the largest avoidable failure mode on the day. Corpus content remains behind a
private storage endpoint.

The deployment adds one VNet, three subnets, one Blob private endpoint and one private
DNS zone. These resources are persistent and idempotent under `azd up`; repeat corpus
uploads create only a short-lived container group.

The deployment is **not** a template for the customer's production environment, and must
not be presented as one. When network isolation is discussed, the honest statement is
that this environment trades isolation for presentability, and that the production
pattern is the one on the reference architecture slide. Saying otherwise to a regulated
financial institution would be a material misrepresentation.

Mitigations that keep the posture defensible despite public access:

- `disableLocalAuth: true` on the Foundry account; no API keys exist to leak.
- Public Foundry ingress is Entra-protected; outbound evaluation access is VNet-injected.
- `publicNetworkAccess: 'Disabled'` and `allowSharedKeyAccess: false` on storage.
- An approved Search shared private link to the Blob subresource.
- A dedicated uploader identity with only `Storage Blob Data Contributor` and `AcrPull`.
- Managed identity for every service-to-service call.
- Role assignments at the narrowest practical scope; no runtime identity holds `Owner`
  or `Contributor`.
- Synthetic data only, so a disclosure would expose nothing real.
