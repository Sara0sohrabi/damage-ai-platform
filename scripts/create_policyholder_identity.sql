BEGIN;
CREATE TABLE IF NOT EXISTS public.policyholder_identity (
    request_id UUID PRIMARY KEY REFERENCES public.prediction_requests(request_id),
    national_id VARCHAR(10),
    birth_date VARCHAR(10),
    policyholder_code VARCHAR(100),
    full_name VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.policyholder_identity ADD COLUMN IF NOT EXISTS birth_date VARCHAR(10);
ALTER TABLE public.policyholder_identity ADD COLUMN IF NOT EXISTS full_name VARCHAR(200);
COMMIT;
