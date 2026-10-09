# Prototype Instructions

Merge supplementary claim fields into the main «اطلاعات خسارت» section; keep financial information separate. Quality summaries should follow these two sections.
Do not show the redundant insured_item_type free-text field; retain the database-backed damaged_item_code selector.
The visible damaged-item selector uses eight deduplicated claim categories: codes 1-4 bodily (death, medical expense, disability, incapacity) and codes 5-8 financial (building, installations, household contents, documents).
Claim fields appear in decision order: insurance type, financial/bodily scope, damage type, then the scoped damaged item.
The redundant damage_type_code field is removed from the form; the Prediction database table remains pending explicit DDL execution.
Financial damage fields are shown only when damage_scope is financial; the fire insurance type selector controls the policy subtype context.
Hide placeholder titles matching `Value <number>` from all UI option lists while retaining database rows and codes.
Remove the redundant property_type field from the visible claim form; retain ownership_type as the only ownership-related field.
Hide occupation_code for residential fire insurance (insurance_type_code 1); keep it available for industrial and non-industrial policies.
Policyholder identity fields (national ID, birth year, policyholder code) are optional case metadata and are persisted in request_payload, never used as model features.

Label risk_density_code as «تراکم ریسک منطقه جغرافیایی» in the claim form.

The claim form uses an optional single-line text field labeled «آدرس محل مورد خسارت» (loss_location_address) instead of the loss_location_code selector. Store the address with the request; do not convert address text into a model category code.

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

Use one Persian incident_date (YYYY/MM/DD) input instead of separate year/month fields. Backend derives year/month and records registration timestamp.
Incident date must offer a Persian calendar picker, not only text entry.

Replace the comparison navigation tab with a BI report backed by saved Prediction database records. History reads request_payload and joins prediction_results and latest claim_payment_results. BI totals cover all records, not only the current history page.

Initial claim intake is for automated assessment. Do not request an expert report in this form; expert referral is a separate future stage. Preserve item details and supporting documents.
