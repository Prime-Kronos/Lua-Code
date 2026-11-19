# Topdim — Uzbekistan deployment plan

Status: architecture plan only. No production account, server, database, domain, or customer data has been provisioned by this document.

## Deployment decision

The selected target is an in-country deployment in Uzbekistan. Keep the current Render service as a public demo only until the application, database, storage, contracts, and privacy notice have been reviewed. The current Render service is configured for Frankfurt, so it is not the production host for a localization-first deployment.

## Target architecture

- **Web/API:** Node.js 20 + Express, deployed in a Tashkent data centre.
- **Database:** PostgreSQL in the same provider/region, private network only; no public database port.
- **Photos:** S3-compatible object storage in Uzbekistan. Store object keys and metadata in PostgreSQL, not image bytes in database rows, before production scale.
- **Backups:** automated daily backups plus a separately stored encrypted backup; test restores on a schedule.
- **Operations:** HTTPS, firewall allowlist for database access, SSH keys, MFA for provider accounts, secret rotation, uptime/health monitoring, and deployment rollback.
- **Admin:** replace the single shared bearer token with named admin accounts, password hashing, MFA, role separation, session expiry, and auditable moderation before a public launch.

## Provider shortlist to evaluate

These are candidates, not endorsements. Confirm the exact service, physical data-centre location, contract, data-processing terms, backup location, access controls, incident notification, and export/exit process directly with each provider.

1. **UzCloud** — advertises local PostgreSQL DBaaS, managed backups/failover, S3-compatible object storage, and local infrastructure. Its public pricing page lists VM unit prices, but DBaaS pricing needs a quote.
2. **UniSphere Cloud** — advertises apps/containers and VPS in a Tashkent data centre, with public entry-level prices. Confirm whether PostgreSQL is offered as a managed service or must be operated on a separate VM, and confirm backup/restore guarantees.
3. **ServerPlus** — advertises VPS in a Tashkent data centre. This is a possible lower-cost self-managed route, but the team would be responsible for PostgreSQL patching, monitoring, access control, and tested backups.

## Questions to ask each provider

- Can you confirm in writing that the primary database, replicas, logs, backups, and object storage remain physically in Uzbekistan?
- Which legal entity signs the contract, and can you provide the data-processing agreement and security/incident terms?
- Is PostgreSQL managed? Which versions, TLS options, private networking, point-in-time recovery, and backup retention are included?
- Are backups encrypted, isolated from the production account, and restorable by the customer?
- Who can access production data, how is support access approved, and are admin actions logged?
- What are the monthly costs including storage, backups, traffic, public IP, VAT, and support?
- Can all data and photos be exported in standard formats when leaving the provider?

## Launch gates

Do not accept real public submissions until all of these are complete:

- Local legal review of the applicable personal-data rules, the operator/controller role, privacy notice, consent text, and any required registration.
- Written confirmation of the provider's data locations and processing terms.
- Production secrets configured outside Git; unique strong admin credentials and a separate rate-limit secret.
- Private database networking and least-privilege database user.
- Object storage with private buckets and signed/controlled access.
- Automated backups with a successful restore test.
- Admin authentication and moderation workflow tested.
- Upload validation, rate limits, abuse reporting, retention/deletion process, and incident response reviewed.
- HTTPS, security headers, monitoring, logs without sensitive data, and rollback tested.

## Current demo status

The Render service `topdim-demo-nmyf` currently runs in the Frankfurt region on the free plan. Treat it as a demo only. Do not submit real names, phone numbers, exact addresses, identity documents, or other personal/sensitive information there. The application should remain closed to public writes until a compliant production environment is configured and verified.

## Sources checked

- UzCloud DBaaS: https://uzcloud.uz/cloud/dbaas
- UzCloud pricing: https://uzcloud.uz/prices
- UniSphere Cloud: https://dc.unisphere.systems/
- ServerPlus VPS: https://serverplus.uz/en/products/cloud-vds-vps-servers
- Uzbekistan personal-data law amendment (Law No. ZRU-1125): https://www.lex.uz/ru/docs/8104580

This document is a technical planning note, not legal advice or a claim that any provider is certified or automatically compliant for Topdim.
