Real integrations plan

This file outlines how to move from mocks to real public APIs for company verification.

1) VIES (VAT Information Exchange System)
   - Adapter: SOAP using `zeep`.
   - Config: set `VIES_ENABLED=True` in .env to enable.
   - Notes: VIES has countryCode and vatNumber parameters; some countries restrict access.

2) Unternehmensregister / Handelsregister
   - Sources: national registers; many have different APIs or require scraping.
   - Consider OpenCorporates as a unified API (requires API key).

3) Sanctions lists
   - EU consolidated list: maintained by the EU (CSV/JSON) or use existing libraries.
   - OFAC SDN: public CSV/JSON from US Treasury.
   - UK sanctions: public lists.
   - Implementation: download and cache lists or query official endpoints.

4) WHOIS / SSL Labs
   - WHOIS: use `python-whois` or direct whois lookups (may be rate-limited).
   - SSL Labs: use SSL Labs API for cert and grade info.

5) Implementation plan
   - Add env vars and credentials to .env
   - Implement adapters with real HTTP/soap calls, add retries and rate limit handling
   - Add caching and backoff for external calls
   - Add integration tests using recorded responses (VCR-like) rather than mocks

6) Security and privacy
   - When passing requester data to external APIs, ensure consent and privacy policy compliance.

Quick start — enable real integrations and run a smoke check

1. Install runtime dependencies:

```powershell
pip install -r requirements.txt
pip install zeep lxml pandas rapidfuzz requests
```

2. Copy `.env.example` to `.env` and enable the integrations you need (example minimal):

```
VIES_ENABLED=True
SANCTIONS_EU_ENABLED=True
OPENCORP_ENABLED=True
OPENCORP_API_KEY=your_key_here
CACHE_DIR=./app/data
```

3. Start the Flask app and run a smoke lookup (or POST to `/lookup` via curl/Invoke-RestMethod):

```powershell
# start app (development)
$env:FLASK_APP='app'; flask run
# in another shell, run a lookup for a known VAT
Invoke-RestMethod -Uri http://127.0.0.1:5000/lookup -Method Post -Body @{ vat_number='DE811220642'; country='DE' }
```

Notes:
- If VIES calls fail due to network or SOAP errors, check logs; the adapter now returns explicit error statuses.
- For production usage, add proper secret management, caching (Redis or filesystem) and rate limiting.
