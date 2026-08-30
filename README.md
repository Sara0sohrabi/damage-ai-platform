# Damage AI Platform v3

این نسخه برای معماری واقعی ارزیابی خسارت طراحی شده است: **Data Preparation یک مرحله مستقل و نسخه‌دار است؛ Training جداست؛ Prediction API فقط مدل آماده را مصرف می‌کند.**

## معماری
```text
Excel / historical claims
        │
        ├── raw_damage_data  (نسخه خام، بدون حذف)
        │
        └── Cleaning + Mapping + Validation + EDA  ← فقط هنگام آماده‌سازی
                     │
                     ▼
              clean_damage_data
                     │
                     ├── EDA report → eda_runs
                     │
                     └── Training 80/20 + KMeans + GradientBoosting
                                      │
                                      ├── model_runs
                                      ├── test_prediction_results
                                      └── models/damage_prediction.joblib

Application ──POST /api/v1/claim/predict──> FastAPI
                                             │
                                             ├── validate business rules
                                             ├── cluster assignment
                                             ├── predicted_loss
                                             ├── cap = min(item_sum_insured,total_sum_insured)
                                             └── prediction_requests + evidence + invoice items

بعد از پرداخت واقعی:
POST /api/v1/claim/{request_id}/finalize?actual_paid_loss=...
                                             │
                                             └── prediction_error و estimate_error
```

## نکات مهم
- `FireHvID`، شماره پرونده، کد رایانه و شناسه‌های سیستم بیمه‌گر **Feature نیستند** و وارد مدل نمی‌شوند.
- `paid_loss` فقط Target تاریخی است و در Prediction اولیه ارسال نمی‌شود.
- `estimate_amount` نگهداری می‌شود و به عنوان Feature استفاده می‌شود؛ بعداً با `paid_loss` و خروجی مدل مقایسه می‌شود.
- سقف پرداخت مدل `min(item_sum_insured,total_sum_insured)` است. اگر سرمایه مورد از سرمایه کل بیشتر باشد، Prediction رد می‌شود.
- عکس، متن، فاکتور و گزارش کارشناس در Prediction API قابل دریافت و ذخیره هستند. فعلاً آن‌ها به شکل metadata/text ذخیره می‌شوند؛ اتصال OCR/CV/LLM به عنوان مرحله بعدی می‌تواند به feature extraction اضافه شود.
- نرمال‌سازی عددی و One-Hot در Pipeline مدل انجام می‌شود و فقط روی train fit می‌شود تا leakage ایجاد نشود.

## اجرا روی Mac با Docker
> این نسخه پورت PostgreSQL را روی **5432** گذاشته چون پروژه فعلی شما همین پورت را در Docker دارد. اگر 5432 اشغال بود، در compose فقط سمت چپ را به 5433 تغییر دهید.

### 1. پاک‌سازی فقط در صورت شروع کاملاً تازه
```bash
docker compose -f infrastructure/docker-compose.yml down
```
برای حذف کامل داده‌های قبلی (اختیاری و مخرب):
```bash
docker compose -f infrastructure/docker-compose.yml down -v
```

### 2. PostgreSQL
```bash
docker compose -f infrastructure/docker-compose.yml up -d postgres
docker compose -f infrastructure/docker-compose.yml ps
```
باید `healthy` و `0.0.0.0:5432->5432/tcp` ببینی.

### 3. ساخت جدول‌ها
```bash
docker compose -f infrastructure/docker-compose.yml run --rm preparation python -m scripts.init_db
```

### 4. Mapping
```bash
docker compose -f infrastructure/docker-compose.yml run --rm preparation python -m scripts.load_mappings
```
Mappingهای فعلی seed شامل 6 نوع آسیب و 20 پوشش است. Mappingهای استان، شهر، مورد بیمه، حادثه و ... را می‌توانی به `mapping_seed.py` اضافه کنی.

### 5. وارد کردن داده تاریخی
```bash
docker compose -f infrastructure/docker-compose.yml run --rm preparation python -m scripts.import_clean_data --input /data/processed/damage_ai_kpi_model_dataset_final.xlsx --dataset-version dataset_001
```
این مرحله raw را نگه می‌دارد و clean را جدا ذخیره می‌کند.

### 6. EDA
```bash
docker compose -f infrastructure/docker-compose.yml run --rm preparation python -m scripts.run_eda --dataset-version dataset_001
```
گزارش در `reports/eda_dataset_001.json` و رکورد آن در `eda_runs` ذخیره می‌شود.

### 7. Training
```bash
docker compose -f infrastructure/docker-compose.yml run --rm training python -m scripts.train_model
```
خروجی: `models/damage_prediction.joblib` + metrics + test results + clusters در PostgreSQL.

### 8. Prediction API
```bash
docker compose -f infrastructure/docker-compose.yml up -d prediction
```
Swagger: http://localhost:8000/docs
Health: http://localhost:8000/health

### 9. تست Prediction
در Swagger، `POST /api/v1/claim/predict` را باز کن و `sample_request.json` را بده. پاسخ یک `request_id` می‌دهد. همان شناسه کل رکورد را در `prediction_requests` پیدا می‌کند.

### 10. ثبت خسارت پرداختی واقعی
وقتی پرونده نهایی شد:
```bash
curl -X POST "http://localhost:8000/api/v1/claim/<REQUEST_ID>/finalize?actual_paid_loss=735000000"
```
بعد می‌توانی `prediction_error` و `estimate_error` را در PostgreSQL مقایسه کنی.

## اتصال DBeaver / Azure Data Studio
```text
Host: localhost
Port: 5432
Database: damage_ai
User: damage
Password: damage_dev
SSL: disabled
```

## جدول‌های اصلی
- `raw_damage_data`: داده خام تاریخی
- `clean_damage_data`: داده تمیز و canonical برای مدل
- `mapping_values` و lookupهای domain: اطلاعات پایه و تفسیر کدها
- `eda_runs`: گزارش EDA
- `model_runs`: معیارهای Train/Test
- `cluster_results`: Cluster تاریخی
- `test_prediction_results`: خروجی تست 20%
- `prediction_requests`: هر درخواست وب‌سرویس + ورودی + خروجی + request_id + paid_loss نهایی
- `claim_evidence`: عکس/فاکتور/متن/گزارش کارشناس
- `claim_invoice_items`: اقلام فاکتور
