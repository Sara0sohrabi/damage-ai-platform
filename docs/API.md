# Prediction API

## Endpoint

`POST /api/v1/claim/predict`

The mobile/web app sends the 18 model inputs. `paid_loss` is never sent for a new prediction.

### Inputs

`coverage_code`, `event_type_code`, `province_code`, `city_code`, `loss_location_code`, `occupation_code`, `occupation_group_code`, `damaged_item_code`, `damage_type_code`, `financial_damage_type_code`, `property_type_code`, `structure_type_code`, `risk_density_code`, `ownership_type_code`, `premium`, `item_sum_insured`, `total_sum_insured`, `estimate_amount`.

### Success response

```json
{
  "success": true,
  "classification": {
    "cluster_id": 2,
    "category": "high_loss"
  },
  "prediction": {
    "predicted_loss": 123456789,
    "currency": "IRR"
  },
  "policy_limits": {
    "item_sum_insured": 1000000000,
    "total_sum_insured": 5000000000,
    "maximum_payable_loss": 1000000000
  }
}
```

`category` is derived from historical paid-loss severity inside the fitted clusters. It is not a manual insurance mapping and can later be replaced by a business-approved risk/category mapping without changing the API contract.
