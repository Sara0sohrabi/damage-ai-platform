
CREATE TABLE IF NOT EXISTS prediction_requests (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE,
    customer_claim_id VARCHAR(100) NOT NULL,
    request_payload JSONB NOT NULL,
    model_version VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prediction_requests_claim
ON prediction_requests(customer_claim_id);

CREATE INDEX IF NOT EXISTS idx_prediction_requests_model
ON prediction_requests(model_version);


CREATE TABLE IF NOT EXISTS prediction_results (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE,
    model_version VARCHAR(100) NOT NULL,

    predicted_paid_loss NUMERIC(20,2) NOT NULL,

    model_mae NUMERIC(20,4),
    model_rmse NUMERIC(20,4),
    model_r2 NUMERIC(12,8),

    model_business_accuracy_percent NUMERIC(10,4),
    model_within_10pct_percent NUMERIC(10,4),
    model_within_20pct_percent NUMERIC(10,4),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_prediction_result_request
        FOREIGN KEY (request_id)
        REFERENCES prediction_requests(request_id)
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS claim_payment_results (
    id BIGSERIAL PRIMARY KEY,

    request_id UUID NOT NULL UNIQUE,

    claim_id VARCHAR(100) NOT NULL,

    payment_status VARCHAR(30) NOT NULL,

    paid_amount NUMERIC(20,2),

    prediction_amount NUMERIC(20,2),

    absolute_error NUMERIC(20,2),

    relative_error_percent NUMERIC(10,4),

    prediction_accuracy_percent NUMERIC(10,4),

    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_payment_result_request
        FOREIGN KEY (request_id)
        REFERENCES prediction_requests(request_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_payment_status
        CHECK (
            payment_status IN (
                'OPEN',
                'PAID',
                'PARTIALLY_PAID',
                'REJECTED',
                'CANCELLED'
            )
        )
);


CREATE INDEX IF NOT EXISTS idx_claim_payment_claim
ON claim_payment_results(claim_id);

CREATE INDEX IF NOT EXISTS idx_claim_payment_status
ON claim_payment_results(payment_status);


CREATE OR REPLACE VIEW prediction_comparison AS
SELECT
    pr.request_id,
    pr.customer_claim_id,
    pr.created_at,

    p_result.model_version,
    p_result.predicted_paid_loss,

    payment.payment_status,
    payment.paid_amount,

    payment.absolute_error,
    payment.relative_error_percent,
    payment.prediction_accuracy_percent,

    payment.received_at

FROM prediction_requests pr

LEFT JOIN prediction_results p_result
    ON pr.request_id = p_result.request_id

LEFT JOIN claim_payment_results payment
    ON pr.request_id = payment.request_id;

