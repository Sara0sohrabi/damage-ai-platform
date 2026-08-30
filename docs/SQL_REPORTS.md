# گزارش‌های آماده PostgreSQL

## عملکرد مدل
```sql
SELECT model_version,dataset_version,train_rows,test_rows,mae,rmse,r2,within_10pct,within_20pct,cluster_count
FROM model_runs ORDER BY created_at DESC;
```

## تست‌ها
```sql
SELECT * FROM test_prediction_results ORDER BY id DESC;
```

## درخواست‌های وب‌سرویس
```sql
SELECT request_id,created_at,coverage_code,damage_type_code,item_sum_insured,total_sum_insured,estimate_amount,predicted_loss,actual_paid_loss,prediction_error,estimate_error,model_version,status
FROM prediction_requests ORDER BY created_at DESC;
```

## دقت عملیاتی بعد از ثبت paid_loss
```sql
SELECT
  COUNT(*) FILTER (WHERE actual_paid_loss IS NOT NULL) AS finalized,
  AVG(ABS(predicted_loss-actual_paid_loss)) FILTER (WHERE actual_paid_loss IS NOT NULL) AS model_mae,
  AVG(ABS(estimate_amount-actual_paid_loss)) FILTER (WHERE actual_paid_loss IS NOT NULL AND estimate_amount IS NOT NULL) AS estimate_mae
FROM prediction_requests;
```

## کنترل سقف سرمایه
```sql
SELECT COUNT(*) AS invalid
FROM prediction_requests
WHERE predicted_loss > LEAST(item_sum_insured,total_sum_insured);
```
