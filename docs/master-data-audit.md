# گزارش بررسی فقط‌خواندنی Master Dataهای Damage AI

تاریخ بررسی: ۲۰۲۶-۱۰-۰۴. همه پرس‌وجوهای این مرحله در تراکنش `BEGIN READ ONLY` اجرا شدند. هیچ CREATE، DROP، ALTER، INSERT یا UPDATE اجرا نشد. تنها این فایل گزارش روی دیسک نوشته شده است.

## اتصال‌های بررسی‌شده

| نقش | کانتینر | دیتابیس | پورت میزبان |
|---|---|---|---|
| مدل / آموزش | damage_ai_postgres | damage_ai | 5433 |
| Prediction | damage_prediction_db | damage_prediction_db | 5434 |

همه اشیای برنامه در schema `public` مشاهده شدند. دیتابیس Prediction دارای سه جدول و یک View است؛ هیچ Master Data مستقل ندارد. کد سرویس داخل پوشه فعلی، به‌صورت پیش‌فرض همان damage_ai را استفاده می‌کند؛ نباید آن را با دیتابیس مستقل Prediction اشتباه گرفت.

## نتیجه‌های اصلی

- استان و شهر جدول مستقل ندارند؛ نام و کد واقعی در JSON جدول `raw_damage_data` موجود است. ۳۲ جفت کد/نام استان و ۱۴۵ ترکیب کد/نام شهر/استان مشاهده شد.
- `occupation_mapping` خالی است؛ منبع فعالیت‌ها `occupation_activity_mapping` با ۲۱۰ رکورد است.
- بین `mapping_values` و جدول‌های domain هفت تعارض عنوان برای کد یکسان وجود دارد. انتخاب خودکار یکی از این منابع برای انتقال قابل تأیید نیست.
- در damage_ai هیچ Foreign Key ثبت‌شده‌ای وجود ندارد. رابطه شهر/استان و فعالیت/گروه فعلاً رابطه داده‌ای است.
- مدل ثبت‌شده در هر سه درخواست دیتابیس Prediction برابر `damagefire_001_gradient_boosting_raw_v2` است. فایل محلی `models/damage_prediction.joblib` نسخه `gboost_v2` و dataset برابر `dataset_001` دارد؛ تطابق دقیق آن با مدل سرویس Prediction تأیید نشده است.
- dataset ثبت‌شده در damage_ai برابر `damagefire_001` با ۵۷۲۱ سطر است؛ مقدار dataset_version ردیف model_runs برای `damagefire_001_gradient_boosting_raw_v2` خالی است.
- `Moredbime_Code` / `Moredbime` و `مورد بیمه_Code` / `مورد بیمه` دو مفهوم متفاوت‌اند. `clean_damage_data.insured_item_type_code` فقط کدهای 0 و 1 دارد؛ اما damaged_item_mapping دارای ۹۸ کد است. انتقال این دو به یک جدول بدون تعیین مفهوم صحیح مجاز فرض نشده است.

## استان و شهر

منبع فیزیکی: `public.raw_damage_data.raw_data` با نوع `json`. مقادیر استخراج‌شده با `->>` از نوع `text` هستند. ستون‌های متناظر `clean_damage_data.province_code` و `city_code` از نوع `varchar(100)` هستند. هر دو جدول ۵۷۲۱ رکورد دارند.

| مقصد پیشنهادی مرحله بعد | code | title/name | رابطه | تعداد یکتا |
|---|---|---|---|---|
| province | ProvinceName_Code | ProvinceName | — | 32 |
| city | CityName_Code | CityName | ProvinceName_Code → province.code | 145 |

در داده تمیز، ۱۴۵ جفت یکتای استان/شهر وجود دارد و هیچ city_code به بیش از یک province_code مرتبط نیست. این نتیجه از داده است و FK نیست. عنوان «بغداد» نیز در داده منبع استان وجود دارد؛ بنابراین جایگزینی با یک فهرست عمومی استان‌های ایران، کدهای آموزش را حفظ نمی‌کند. برخی عنوان‌ها نویسه جهت متن دارند؛ نسخه اصلی باید حفظ شود.

نمونه استان‌ها:

| code | title |
| --- | --- |
| 0 | البرز |
| 1 | بغداد |
| 10 | ‏خراسان جنوبي‏ |
| 11 | ‏خراسان رضوي‏ |
| 12 | ‏خراسان شمالي‏ |

نمونه شهرها:

| code | title | province_code |
| --- | --- | --- |
| 0 | آستانه اشرفيه | 31 |
| 1 | ابهر | 14 |
| 10 | اشنويه | 4 |
| 100 | محمد شهر | 0 |
| 101 | محمودآباد | 24 |

## جدول‌های اطلاعات پایه مدل

### public.coverage_mapping

تعداد رکورد: **20**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `coverage`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "1",
    "mapped_title": "آتش سوزی، صاعقه و انفجار",
    "source_value": "آتش سوزی، صاعقه و انفجار",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "2",
    "mapped_title": "آتش سوزی، صاعقه و انفجار",
    "source_value": "آتش سوزی، صاعقه و انفجار",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "3",
    "mapped_title": "آتش سوزی، صاعقه و انفجار",
    "source_value": "آتش سوزی، صاعقه و انفجار",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.damage_type_mapping

تعداد رکورد: **6**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `damage_type`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "1",
    "mapped_title": "مالی",
    "source_value": "مالی",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "2",
    "mapped_title": "سوختگی",
    "source_value": "سوختگی",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "3",
    "mapped_title": "دودزدگی و آلودگی",
    "source_value": "دودزدگی و آلودگی",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.damaged_item_mapping

تعداد رکورد: **98**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `insured_item (نیازمند تفکیک معنایی)`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "0",
    "mapped_title": "Value 0",
    "source_value": null,
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "5",
    "mapped_title": "اثاثيه",
    "source_value": "اثاثيه",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "36",
    "mapped_title": "ساختمان و تاسيسات",
    "source_value": "ساختمان و تاسيسات",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.event_type_mapping

تعداد رکورد: **2**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `event_type`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "0",
    "mapped_title": "آتش سوزي",
    "source_value": "آتش سوزي",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "1",
    "mapped_title": "صاعقه",
    "source_value": "صاعقه",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.financial_damage_type_mapping

تعداد رکورد: **4**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `financial_damage_type`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "3",
    "mapped_title": "انواع اثاثه و لوازم منزل",
    "source_value": "انواع اثاثه و لوازم منزل",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "2",
    "mapped_title": "تاسیسات",
    "source_value": "تاسیسات",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "1",
    "mapped_title": "ساختمان",
    "source_value": "ساختمان",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.insurance_type_mapping

تعداد رکورد: **13**. فیلد code: `insurance_type_code`؛ فیلد نام: `insurance_type_name`. مقصد پیشنهادی: `insurance_type (تکمیلی)`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| activity_group | varchar(255) | NO |
| insurance_type_code | varchar(50) | NO |
| insurance_type_name | varchar(255) | NO |
| created_at | timestamp with time zone | NO |

قیود واقعی: `UNIQUE (activity_group)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

رابطه متنی احتمالی `activity_group` با عنوان گروه فعالیت؛ `insurance_type_code` یکتا نیست و این جدول را نباید lookup ساده code/name فرض کرد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 4,
    "activity_group": "مسکونی",
    "insurance_type_code": "1",
    "insurance_type_name": "آتش‌سوزی مسکونی",
    "created_at": "2026-08-30T08:04:07.232539+00:00"
  },
  {
    "id": 5,
    "activity_group": "صنعتی و کارخانجات",
    "insurance_type_code": "2",
    "insurance_type_name": "آتش‌سوزی صنعتی",
    "created_at": "2026-08-30T08:04:07.232539+00:00"
  },
  {
    "id": 6,
    "activity_group": "انبار و لجستیک",
    "insurance_type_code": "2",
    "insurance_type_name": "آتش‌سوزی صنعتی",
    "created_at": "2026-08-30T08:04:07.232539+00:00"
  }
]
```

### public.loss_location_mapping

تعداد رکورد: **965**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `loss_location`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "883",
    "mapped_title": "منزل مسکوني",
    "source_value": "منزل مسکوني",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "885",
    "mapped_title": "مهمانسراي کيش",
    "source_value": "مهمانسراي کيش",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "793",
    "mapped_title": "ساختمان اداري",
    "source_value": "ساختمان اداري",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.mapping_values

تعداد رکورد: **26**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `منبع عمومی با تعارض`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | integer | NO |
| mapping_version | varchar(100) | YES |
| mapping_name | varchar(100) | YES |
| source_value | varchar(500) | YES |
| mapped_code | varchar(100) | YES |
| mapped_title | varchar(500) | YES |
| active | boolean | YES |

قیود واقعی: `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapping_version": "mapping_001",
    "mapping_name": "damage_type",
    "source_value": "تخریب",
    "mapped_code": "1",
    "mapped_title": "تخریب",
    "active": true
  },
  {
    "id": 2,
    "mapping_version": "mapping_001",
    "mapping_name": "damage_type",
    "source_value": "سوختگی",
    "mapped_code": "2",
    "mapped_title": "سوختگی",
    "active": true
  },
  {
    "id": 3,
    "mapping_version": "mapping_001",
    "mapping_name": "damage_type",
    "source_value": "دودزدگی و آلودگی",
    "mapped_code": "3",
    "mapped_title": "دودزدگی و آلودگی",
    "active": true
  }
]
```

### public.occupation_activity_mapping

تعداد رکورد: **210**. فیلد code: `activity_code`؛ فیلد نام: `activity_title`. مقصد پیشنهادی: `occupation`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| activity_code | varchar(100) | NO |
| activity_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| macro_group | varchar(255) | YES |
| macro_group_code | varchar(100) | YES |
| mapping_version | varchar(50) | NO |
| active | boolean | NO |
| created_at | timestamp with time zone | NO |

قیود واقعی: `PRIMARY KEY (id)`؛ `UNIQUE (activity_code, mapping_version)`. Foreign Key ندارد.

رابطه منطقی: `macro_group_code` به `occupation_group_mapping.mapped_code`. در بررسی فعلی کد گروه بدون مقصد یافت نشد. نمونه‌ای مثل «کارخانه سنگ بری» با گروه «مسکونی» نشان می‌دهد معنای گروه‌ها نیز نیازمند بازبینی است.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "activity_code": "152",
    "activity_title": "Value 152",
    "source_value": null,
    "macro_group": "اداری",
    "macro_group_code": "2",
    "mapping_version": "mapping_001",
    "active": true,
    "created_at": "2026-08-25T13:02:14.362269+00:00"
  },
  {
    "id": 2,
    "activity_code": "144",
    "activity_title": "Value 144",
    "source_value": null,
    "macro_group": "مسکونی",
    "macro_group_code": "1",
    "mapping_version": "mapping_001",
    "active": true,
    "created_at": "2026-08-25T13:02:14.362269+00:00"
  },
  {
    "id": 3,
    "activity_code": "10",
    "activity_title": "Value 10",
    "source_value": null,
    "macro_group": "اداری",
    "macro_group_code": "2",
    "mapping_version": "mapping_001",
    "active": true,
    "created_at": "2026-08-25T13:02:14.362269+00:00"
  }
]
```

نمونه‌های دیگر با عنوان غیر-placeholder:

```json
[
  {
    "activity_code": "118",
    "activity_title": "فروشگاه لوازم لوکس و اسپرت اتومبيل",
    "macro_group_code": "11",
    "macro_group": "فروشگاهی و تجاری"
  },
  {
    "activity_code": "145",
    "activity_title": "ميوه فروشي",
    "macro_group_code": "11",
    "macro_group": "فروشگاهی و تجاری"
  },
  {
    "activity_code": "186",
    "activity_title": "کارخانه سنگ بري",
    "macro_group_code": "1",
    "macro_group": "مسکونی"
  }
]
```

### public.occupation_group_mapping

تعداد رکورد: **13**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `occupation_group`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "2",
    "mapped_title": "اداری",
    "source_value": "اداری",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "1",
    "mapped_title": "مسکونی",
    "source_value": "مسکونی",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "9",
    "mapped_title": "کشاورزی و دامداری",
    "source_value": "کشاورزی و دامداری",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.occupation_mapping

تعداد رکورد: **0**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `منبع خالی؛ انتقال ندهید`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[]
```

### public.ownership_type_mapping

تعداد رکورد: **2**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `ownership_type`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "0",
    "mapped_title": "Value 0",
    "source_value": null,
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "1",
    "mapped_title": "فاقد مقدار",
    "source_value": "فاقد مقدار",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.property_type_mapping

تعداد رکورد: **2**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `property_type`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "0",
    "mapped_title": "Value 0",
    "source_value": null,
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "1",
    "mapped_title": "فاقد مقدار",
    "source_value": "فاقد مقدار",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.risk_density_mapping

تعداد رکورد: **4**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `risk_density`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "0",
    "mapped_title": "Value 0",
    "source_value": null,
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "3",
    "mapped_title": "منطقه بدون تراكم خطر",
    "source_value": "منطقه بدون تراكم خطر",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "1",
    "mapped_title": "منطقه 4 تراكم خطر",
    "source_value": "منطقه 4 تراكم خطر",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

### public.structure_type_mapping

تعداد رکورد: **6**. فیلد code: `mapped_code`؛ فیلد نام: `mapped_title`. مقصد پیشنهادی: `structure_type`. وجود در دیتابیس Prediction: **خیر**.

| ستون | نوع | Nullable |
| --- | --- | --- |
| id | bigint | NO |
| mapped_code | varchar(100) | NO |
| mapped_title | varchar(500) | NO |
| source_value | varchar(500) | YES |
| category | varchar(200) | YES |
| interpretation_description | text | YES |
| risk_level | varchar(30) | YES |
| mapping_version | varchar(100) | NO |
| active | boolean | NO |

قیود واقعی: `UNIQUE (mapped_code)`؛ `PRIMARY KEY (id)`. Foreign Key ندارد.

نمونه رکوردها (تمام ستون‌ها):

```json
[
  {
    "id": 1,
    "mapped_code": "0",
    "mapped_title": "Value 0",
    "source_value": null,
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 2,
    "mapped_code": "4",
    "mapped_title": "بتون",
    "source_value": "بتون",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  },
  {
    "id": 3,
    "mapped_code": "3",
    "mapped_title": "اسكلت فلزي",
    "source_value": "اسكلت فلزي",
    "category": null,
    "interpretation_description": null,
    "risk_level": null,
    "mapping_version": "mapping_001",
    "active": true
  }
]
```

## تعارض عنوان‌ها

| حوزه | کد | عنوان mapping_values | عنوان جدول domain |
| --- | --- | --- | --- |
| coverage | 2 | زلزله و آتشفشان | آتش سوزی، صاعقه و انفجار |
| coverage | 3 | سیل و طغیان آب | آتش سوزی، صاعقه و انفجار |
| coverage | 5 | ترکیدگی لوله آب و فاضلاب | زلزله و آتشفشان |
| coverage | 7 | سقوط هواپیما یا هلیکوپتر و قطعات آنها | زلزله و آتشفشان |
| coverage | 8 | سقوط اجسام خارجی | ضایعات آب برف و باران |
| coverage | 9 | پاکسازی و برداشت ضایعات | ضایعات آب برف و باران |
| damage_type | 1 | تخریب | مالی |

`mapping_values` فقط ۲۰ رکورد coverage و ۶ رکورد damage_type دارد و استان/شهر در آن ثبت نشده‌اند. نام یکسان mapping_version به‌تنهایی رفع‌کننده تعارض نیست.

## دیتابیس Prediction

| شیء | نوع | تعداد |
| --- | --- | --- |
| claim_payment_results | BASE TABLE | 0 |
| prediction_comparison | VIEW | 3 |
| prediction_requests | BASE TABLE | 3 |
| prediction_results | BASE TABLE | 3 |

### claim_payment_results

| ستون | نوع |
| --- | --- |
| id | bigint |
| request_id | uuid |
| claim_id | varchar(100) |
| payment_status | varchar(30) |
| paid_amount | numeric |
| prediction_amount | numeric |
| absolute_error | numeric |
| relative_error_percent | numeric |
| prediction_accuracy_percent | numeric |
| received_at | timestamp without time zone |

### prediction_comparison

| ستون | نوع |
| --- | --- |
| request_id | uuid |
| customer_claim_id | varchar(100) |
| created_at | timestamp without time zone |
| model_version | varchar(100) |
| predicted_paid_loss | numeric |
| payment_status | varchar(30) |
| paid_amount | numeric |
| absolute_error | numeric |
| relative_error_percent | numeric |
| prediction_accuracy_percent | numeric |
| received_at | timestamp without time zone |

### prediction_requests

| ستون | نوع |
| --- | --- |
| id | bigint |
| request_id | uuid |
| customer_claim_id | varchar(100) |
| request_payload | jsonb |
| model_version | varchar(100) |
| created_at | timestamp without time zone |

### prediction_results

| ستون | نوع |
| --- | --- |
| id | bigint |
| request_id | uuid |
| model_version | varchar(100) |
| predicted_paid_loss | numeric |
| model_mae | numeric |
| model_rmse | numeric |
| model_r2 | numeric |
| model_business_accuracy_percent | numeric |
| model_within_10pct_percent | numeric |
| model_within_20pct_percent | numeric |
| created_at | timestamp without time zone |

روابط FK در Prediction:

- `claim_payment_results`: `FOREIGN KEY (request_id) REFERENCES prediction_requests(request_id) ON DELETE RESTRICT`
- `prediction_results`: `FOREIGN KEY (request_id) REFERENCES prediction_requests(request_id) ON DELETE RESTRICT`

در request_payload کدها ذخیره شده‌اند؛ وجود آن‌ها به معنای وجود Master Data یا نام فارسی نیست. هیچ‌کدام از جداول ساده مقصد (`province` تا `property_type`) یا معادل `_mapping` آن‌ها در این دیتابیس یافت نشد.

## مقایسه با فایل مدل محلی

این بررسی مربوط به gboost_v2 است، نه اثبات سازگاری مدل مستقل Prediction. تعداد کدهای شناخته‌شده encoder:

| فیلد | تعداد کدهای encoder |
| --- | --- |
| coverage_code | 11 |
| event_type_code | 1 |
| province_code | 30 |
| city_code | 96 |
| loss_location_code | 146 |
| occupation_code | 94 |
| occupation_group_code | 13 |
| damaged_item_code | 95 |
| damage_type_code | 1 |
| financial_damage_type_code | 3 |
| property_type_code | 2 |
| structure_type_code | 6 |
| risk_density_code | 4 |
| ownership_type_code | 2 |

- همه کدهای استان/شهر فایل مدل محلی در داده منبع فعلی وجود دارند؛ مدل فقط ۳۰ استان و ۹۶ شهر را هنگام fit دیده است، در حالی که منبع ۳۲ استان و ۱۴۵ شهر دارد.
- کد فعالیت `0` در فایل مدل محلی وجود دارد ولی در clean_damage_data و occupation_activity_mapping فعلی یافت نشد؛ کد `42` در جدول فعالیت عنوان «تعميرگاه اتومبيل بدون صافكاري و نقاشي» و گروه `8` دارد.
- فیلد `damaged_item_code` در فایل مدل محلی هست، ولی ستون هم‌نام در clean_damage_data فعلی نیست. جایگزینی آن با insured_item_type_code بدون بررسی pipeline اشتباه است.
- وجود یک کد در lookup به‌تنهایی اثبات نمی‌کند عنوان آن همان معنایی را دارد که در dataset آموزش استفاده شده است.

## توقف پیش از تغییر

هیچ انتقال، migration یا تغییر UI/API در این مرحله انجام نشد. پیش از مرحله بعد باید مدل دقیق سرویس Prediction و dataset مرجع آن تعیین، تعارض عنوان‌ها رفع و تفکیک insured_item / damaged_item / insured_item_type مشخص شود. سپس نام‌های ساده پیشنهادی کاربر قابل استفاده‌اند؛ کدها باید به‌صورت رشته و بدون شماره‌گذاری مجدد حفظ شوند.
