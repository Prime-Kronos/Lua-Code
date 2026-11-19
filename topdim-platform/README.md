# Topdim backend

Node.js 20 + Express + PostgreSQL. The API fails closed: without a configured persistent database, public submissions are unavailable.

## Runtime setup
```sh
npm install
npm start
```

## Environment variables
- `DATABASE_URL`: PostgreSQL connection string. Production must use a provider/region approved after legal and contractual review.
- `RATE_LIMIT_SECRET`: required in production; random secret of at least 32 characters. Used only for one-way client-IP hashing.
- `ADMIN_EMAIL`: initial owner admin email, set only in the hosting provider's secret environment settings.
- `ADMIN_PASSWORD`: initial owner password, at least 14 characters. Set out-of-band by the account owner/guardian; never send it in chat or commit it.
- `DATABASE_SSL`: leave unset for normal TLS verification. Disable TLS only after verifying a private local network and the provider's security design.
- `PG_POOL_MAX`: optional database connection pool size.

The first owner account is bootstrapped only when the admin table is empty. The password is derived with scrypt and a random salt. No public endpoint can create additional admins. Do not set initial admin credentials on a European demo database.

## Admin authentication
- `POST /api/admin/login` — JSON `{"email":"...","password":"..."}`; rate-limited, issues an HttpOnly, SameSite=Strict session cookie and CSRF token.
- `GET /api/admin/me` — current session.
- `POST /api/admin/logout` — expires session; send returned CSRF token in `X-CSRF-Token`.
- `GET /api/admin/submissions` — authenticated pending queue.
- `GET /api/admin/submissions/:id/photo` — authenticated pending photo.
- `PATCH /api/admin/submissions/:id` — authenticated JSON `{"status":"approved"}` or `{"status":"rejected"}`; send `X-CSRF-Token`.

Session lifetime is 8 hours. Admin sessions are stored as token hashes and can be invalidated server-side. Use HTTPS in production. The first account is owner; additional account-management UI and named moderator invitations are not yet implemented.

## Public API
- `GET /api/health` — readiness and database state (no secrets).
- `GET /api/listings?q=&category=&kind=` — approved listings only.
- `GET /api/listings/:id/photo` — approved photo only.
- `POST /api/listings` — multipart fields `photo`, `title`, `category`, `kind`, `area`, `date`, `description`, `consent=yes`.

## Security included
- Parameterized SQL; strict allowlists and schema validation.
- Image allowlist, upload/pixel limits, decode and WebP re-encoding.
- Pending items are private; public responses expose approved records only.
- Database-backed rate limits, request IDs, security headers and no wildcard CORS.
- Admin scrypt password derivation, HttpOnly sessions, CSRF token check, origin check, expiry and audit log.
- No public phone numbers or exact coordinates.

## Remaining production gates
No user accounts, password reset, claim/ownership verification, SMS, editing, report/appeal workflow, malware scanning, object storage migration, automated backup/restore test, admin management UI, formal penetration test or independent security review. Photos currently reside as BYTEA in PostgreSQL; move to private object storage before scaling. Admin login endpoints exist, but there is not yet a complete visual admin dashboard.

## Data protection
The Uzbekistan personal-data law was amended by Law No. ZRU-1125, effective 27 March 2026. The amended Article 27¹ contains specific in-country storage requirements and conditional routes for other cross-border processing. Applicability, database registration, operator duties, lawful basis and hosting arrangements require local legal review before collecting real user data. This README is not legal advice. See https://www.lex.uz/ru/docs/8104580

Draft documents:
- `PRIVACY_POLICY_DRAFT.md`
- `TERMS_DRAFT.md`
- `BACKUP_RUNBOOK.md`
- `DEPLOYMENT_UZ.md`

Do not enable public writes until a local production database and storage are configured, backups are restored successfully in a test environment, admin credentials are set in the provider's secret manager, legal documents are approved, and the complete flow has been tested. Involve a parent/guardian in provider accounts, contracts and payments.
