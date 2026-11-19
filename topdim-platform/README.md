# Topdim — full-stack prototype

Lost-and-found platform concept for Uzbekistan.

## Stack
- Node.js 20 + Express API
- PostgreSQL (optional; Neon-compatible)
- Responsive HTML/CSS/JS
- Custom SVG icon sprite based on the supplied Topdim icon direction

## Implemented
- Public catalogue with search and category/type filters
- Lost/found submission form
- Server-side validation, length limits, honeypot and basic per-IP rate limiting
- New submissions remain private (pending) until approved
- Admin moderation API protected by ADMIN_TOKEN
- /api/health reports runtime/database mode

## API
- GET /api/health
- GET /api/listings?q=&category=&kind=
- POST /api/listings — creates a pending submission
- GET /api/admin/submissions — requires x-admin-token
- PATCH /api/admin/submissions/:id with {"status":"approved"|"rejected"} — requires x-admin-token

## Local run
npm install && npm start

Set DATABASE_URL to PostgreSQL to persist submissions. Without it, submissions are stored in process memory and are lost when the service restarts. Set a long random ADMIN_TOKEN in hosting secret environment variables before enabling moderation.

## Important limits
This is a prototype, not a public production service. It has no user accounts, claim workflow, private messaging, image uploads, or organization portal yet. Do not publish real personal information. Do not add phone numbers, emails, exact addresses, ID data, or unique identifying details to public descriptions. The previously created Neon database is in the EU; review Uzbekistan's personal-data and localization requirements with a qualified local professional before processing real residents' personal data. Since the project owner is under 18, involve a parent or guardian in hosting accounts, contracts, payments and public launch.


## White redesign and map
- Four live interface locales: Russian, Uzbek Latin, Uzbek Cyrillic, and English.
- Responsive language selector in the top navigation.
- Interactive Leaflet map with 14 administrative unit polygons, region selection and search.
- Basemap tiles from CARTO using OpenStreetMap data; visible attribution is included.
- Administrative GeoJSON from akbartus/GeoJSON-Uzbekistan (GPL-3.0); see `public/data/UZBEKISTAN-GEOJSON-LICENSE.txt`.
- GSAP and CSS reveal animations with reduced-motion support.

Map boundary data is an open community dataset, not a cadastral/legal boundary source. Do not use it for legal or surveying decisions.
