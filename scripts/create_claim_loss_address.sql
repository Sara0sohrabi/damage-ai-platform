BEGIN;
CREATE TABLE IF NOT EXISTS public.claim_loss_address (
    request_id UUID PRIMARY KEY REFERENCES public.prediction_requests(request_id),
    address TEXT NOT NULL CHECK (btrim(address) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO public.claim_loss_address (request_id, address)
SELECT request_id, btrim(request_payload->>'loss_location_address')
FROM public.prediction_requests
WHERE nullif(btrim(request_payload->>'loss_location_address'), '') IS NOT NULL
ON CONFLICT (request_id) DO NOTHING;
COMMIT;
