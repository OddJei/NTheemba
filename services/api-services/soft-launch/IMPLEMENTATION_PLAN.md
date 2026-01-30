Affiliate Link → WhatsApp Token Bridge

Goal

Build a secure flow where a user clicks an affiliate link, the service validates the product and business, creates a short-lived token, and redirects the user to WhatsApp with the token prefilled so the business chatbot can resolve the token into product details.

High-level design

- Public GET route: `/a/{affiliate_code}`
  - Lookup `AffiliateLink` by `code` in DB.
  - Validate product and business via existing MSME and Catalog checks (reuse logic from `create_link`).
  - If valid, create a `AffiliateToken` record mapping token → link/product/business, with TTL and optional meta.
    - Redirect user (HTTP 302) to WhatsApp deep-link with token in the message body, e.g. `https://wa.me/<business_phone>?text=ace:<token>`.

Routing options (external first-click)

- External landing URL (preferred for your setup):
    - A separate static service receives the initial browser click (the public URL you control).
    - That service calls the affiliate engine API (e.g. `GET /a/{code}/resolve` or `POST /a/resolve`) with the affiliate code and client context.
    - The affiliate engine performs the same validation (product + business) and returns JSON indicating availability and the generated WhatsApp deep-link (or an error code).
    - The static service then either redirects the browser to the returned WhatsApp URL or renders a small static page showing product availability and a CTA that opens WhatsApp.

    This decouples the UI/static hosting from the affiliate engine and fits your requirement that "other service serve a static page".

- Bot side: provide an authenticated token-resolution endpoint (e.g., `POST /token/resolve`) that the chatbot can call with `ace:<token>` to get product details (product id, price, campaign, affiliate id).

Security considerations

- Tokens are short-lived (suggested TTL 5–15 minutes).
- Tokens should be single-use or have strict rate limits to avoid replay.
- Token lookup endpoint must be protected (API key / signed request) and log access.

Files to change / add

- `services/affiliate-engine/src/app/models.py` — add `AffiliateToken` model
- Add Alembic migration under `alembic/versions/` to create tokens table
- `services/affiliate-engine/src/app/main.py` — add `GET /a/{code}` handler and `POST /token/resolve` (or similar) for bot
- `services/affiliate-engine/src/app/schemas.py` — add request/response schemas for token creation/resolve
- `services/affiliate-engine/README.md` — document link format and bot integration
- Tests under `services/affiliate-engine/tests/` — add flow tests

Implementation checklist (detailed)

- [ ] 1. Add `AffiliateToken` model to `src/app/models.py` with fields: id, token (unique), link_id, affiliate_id, product_id, business_id, created_at, expires_at, used(boolean), meta(json).
- [ ] 2. Create and run Alembic migration to add tokens table (unique token index, TTL index if Postgres).
- [ ] 3. Add Pydantic schemas: `TokenOut`, `TokenResolveRequest`, `TokenResolveOut` in `src/app/schemas.py`.
- [ ] 4. Implement `@app.get('/a/{code}')` in `src/app/main.py`:
    - Lookup `AffiliateLink` by `code`.
    - If link missing → 404.
    - Validate business/product by calling MSME `/business/{id}/entitlements` and Catalog `/catalog/product/{id}` (reuse code from `create_link`).
    - If validation fails → 403/404 as appropriate.
    - Generate token using `_generate_code()` (or similar) and persist `AffiliateToken` with `expires_at = now + TTL`.
    - Build WhatsApp deep-link: `https://wa.me/<business_phone_or_number>?text=ace:<token>` (or documented business chat number).
    - Return `RedirectResponse(url=whatsapp_url)` (HTTP 302).
- [ ] 5. Implement `@app.post('/token/resolve')` for chatbot to exchange `ace:<token>` for link/product info:
    - Accept token string or prefixed message parse (strip `ace:`).
    - Lookup token record: ensure not expired and not used (or allow re-use depending on policy).
    - Optionally mark token used if single-use.
    - Return product details by fetching catalog `/catalog/product/{product_id}` and return structured payload for bot (title, price, product url, affiliate id, campaign).
    - Log and emit `AffiliateEvent` for token_resolve or chatbot_lookup.
- [ ] 6. Add auth on `/token/resolve` — require API key header or JWT shared with chatbot system.
- [ ] 7. Add unit tests covering:
    - Clicking `/a/{code}` creates token and returns a redirect.
    - Token resolution returns product details to bot and respects expiry/used flags.
- [ ] 8. Update `README.md` with examples:
    - Example affiliate short link: `https://nteemba.com/a/<code>`.
    - WhatsApp deep-link example: `https://wa.me/<business_phone>?text=ace:abcd1234`.
    - Bot call example to `POST /token/resolve { token: "abcd1234" }`.

Notes & choices

- WhatsApp deep-link target: choose `wa.me` with the business phone number the bot listens on. If the chatbot uses a shared number or a different integration, adapt the redirect target accordingly.
- Token TTL: default 10 minutes is a reasonable starting point for user convenience vs security.
- Single-use vs multi-use: single-use is more secure but may annoy users if they go back/forward; start with TTL + rate-limit and later tighten to single-use if needed.

Next steps I can take for you

- Implement the DB model and migration.
- Add the `/a/{code}` route and token-resolution endpoint in `src/app/main.py`.
- Add tests and update README.

If you want, I can start by adding the `IMPLEMENTATION_PLAN.md` (done) and then implement step 1 (add model) and step 3 (route) next—tell me which step to start. 