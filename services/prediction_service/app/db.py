import os
import json

from sqlalchemy import create_engine, text


# ============================================================
# PREDICTION DATABASE
# ============================================================

DB = os.getenv(
    "PREDICTION_DATABASE_URL",
    "postgresql+psycopg://damage:damage_dev@prediction_db:5432/damage_prediction_db",
)

engine = create_engine(
    DB,
    pool_pre_ping=True,
)


# ============================================================
# SAVE PREDICTION
# ============================================================

def save_prediction(
    request_id,
    payload,
    predicted_loss,
    maximum_payable_loss,
    cluster=None,
    category=None,
    model_version=None,
    model_metrics=None,
):
    """
    Save one prediction request and its model result.

    IMPORTANT:
    This function writes ONLY to the prediction database.

    Tables:
        prediction_requests
        prediction_results
    """

    customer_claim_id = (
        payload.get("customer_claim_id")
        or payload.get("claim_id")
        or str(request_id)
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    model_metrics = model_metrics or {}

    with engine.begin() as conn:

        # ====================================================
        # 1. Save Prediction Request
        # ====================================================

        conn.execute(
            text(
                """
                INSERT INTO prediction_requests (
                    request_id,
                    customer_claim_id,
                    request_payload,
                    model_version
                )
                VALUES (
                    :request_id,
                    :customer_claim_id,
                    CAST(:request_payload AS jsonb),
                    :model_version
                )
                """
            ),
            {
                "request_id": str(request_id),
                "customer_claim_id": customer_claim_id,
                "request_payload": json.dumps(
                    payload,
                    ensure_ascii=False,
                    default=str,
                ),
                "model_version": model_version,
            },
        )

        # ====================================================
        # 2. Save Prediction Result
        # ====================================================

        conn.execute(
            text(
                """
                INSERT INTO prediction_results (
                    request_id,
                    model_version,
                    predicted_paid_loss,

                    model_mae,
                    model_rmse,
                    model_r2,

                    model_business_accuracy_percent,
                    model_within_10pct_percent,
                    model_within_20pct_percent
                )
                VALUES (
                    :request_id,
                    :model_version,
                    :predicted_paid_loss,

                    :model_mae,
                    :model_rmse,
                    :model_r2,

                    :model_business_accuracy_percent,
                    :model_within_10pct_percent,
                    :model_within_20pct_percent
                )
                """
            ),
            {
                "request_id": str(request_id),
                "model_version": model_version,
                "predicted_paid_loss": predicted_loss,

                "model_mae": model_metrics.get("mae"),

                "model_rmse": model_metrics.get("rmse"),

                "model_r2": model_metrics.get("r2"),

                "model_business_accuracy_percent":
                    model_metrics.get(
                        "business_accuracy_percent"
                    ),

                "model_within_10pct_percent":
                    model_metrics.get(
                        "within_10pct"
                    ),

                "model_within_20pct_percent":
                    model_metrics.get(
                        "within_20pct"
                    ),
            },
        )


# ============================================================
# SAVE REJECTED REQUEST
# ============================================================

def save_rejected_request(
    request_id,
    payload,
    error_code,
):
    """
    Save a rejected prediction request.

    The prediction database schema does not currently have
    a dedicated status column.

    Therefore rejection information is stored inside
    request_payload.
    """

    customer_claim_id = (
        payload.get("customer_claim_id")
        or payload.get("claim_id")
        or str(request_id)
    )

    rejected_payload = dict(payload)

    rejected_payload["_prediction_status"] = "REJECTED"
    rejected_payload["_error_code"] = error_code

    with engine.begin() as conn:

        conn.execute(
            text(
                """
                INSERT INTO prediction_requests (
                    request_id,
                    customer_claim_id,
                    request_payload,
                    model_version
                )
                VALUES (
                    :request_id,
                    :customer_claim_id,
                    CAST(:request_payload AS jsonb),
                    NULL
                )
                ON CONFLICT (request_id)
                DO NOTHING
                """
            ),
            {
                "request_id": str(request_id),
                "customer_claim_id": customer_claim_id,
                "request_payload": json.dumps(
                    rejected_payload,
                    ensure_ascii=False,
                    default=str,
                ),
            },
        )


# ============================================================
# FINALIZE PREDICTION
# ============================================================

def finalize_prediction(
    request_id,
    actual_paid_loss,
):
    """
    Finalize a prediction when the real payment amount
    becomes available.

    Calculates:

        absolute_error
        relative_error_percent
        prediction_accuracy_percent

    and stores them in:

        claim_payment_results
    """

    with engine.begin() as conn:

        # ====================================================
        # 1. Find Prediction
        # ====================================================

        row = conn.execute(
            text(
                """
                SELECT
                    pr.customer_claim_id,
                    pres.predicted_paid_loss
                FROM prediction_requests pr

                JOIN prediction_results pres
                    ON pr.request_id = pres.request_id

                WHERE pr.request_id = :request_id

                FOR UPDATE
                """
            ),
            {
                "request_id": str(request_id),
            },
        ).mappings().first()

        if not row:
            return False

        claim_id = row["customer_claim_id"]

        predicted = float(
            row["predicted_paid_loss"]
        )

        actual = float(
            actual_paid_loss
        )

        # ====================================================
        # 2. Calculate Errors
        # ====================================================

        absolute_error = abs(
            predicted - actual
        )

        if actual != 0:

            relative_error_percent = (
                absolute_error
                / abs(actual)
            ) * 100

            prediction_accuracy_percent = max(
                0.0,
                100.0 - relative_error_percent,
            )

        else:

            relative_error_percent = None
            prediction_accuracy_percent = None

        # ====================================================
        # 3. Save Actual Payment
        # ====================================================

        conn.execute(
            text(
                """
                INSERT INTO claim_payment_results (
                    request_id,
                    claim_id,
                    payment_status,
                    paid_amount,
                    prediction_amount,
                    absolute_error,
                    relative_error_percent,
                    prediction_accuracy_percent
                )
                VALUES (
                    :request_id,
                    :claim_id,
                    'PAID',
                    :paid_amount,
                    :prediction_amount,
                    :absolute_error,
                    :relative_error_percent,
                    :prediction_accuracy_percent
                )

                ON CONFLICT (request_id)

                DO UPDATE SET

                    payment_status =
                        'PAID',

                    paid_amount =
                        EXCLUDED.paid_amount,

                    prediction_amount =
                        EXCLUDED.prediction_amount,

                    absolute_error =
                        EXCLUDED.absolute_error,

                    relative_error_percent =
                        EXCLUDED.relative_error_percent,

                    prediction_accuracy_percent =
                        EXCLUDED.prediction_accuracy_percent,

                    received_at =
                        CURRENT_TIMESTAMP
                """
            ),
            {
                "request_id": str(request_id),
                "claim_id": claim_id,

                "paid_amount": actual,

                "prediction_amount": predicted,

                "absolute_error": absolute_error,

                "relative_error_percent":
                    relative_error_percent,

                "prediction_accuracy_percent":
                    prediction_accuracy_percent,
            },
        )

        return True