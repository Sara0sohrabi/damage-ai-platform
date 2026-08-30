# Mapping Data

این پوشه فقط برای **Mapping داده‌های بیمه خسارت** است؛ هیچ Mapping مربوط به folder/path ندارد.

هر کدی که در `clean_damage_data` به عنوان KPI استفاده می‌شود، فقط از lookup table متناظر خود معنی می‌گیرد.

مثال:

`coverage_code = 1` → `coverage_mapping` → `mapped_title = آتش سوزی...`

کدهای یکسان در Domainهای مختلف مستقل‌اند؛ مثلاً `coverage_code=1` با `damage_type_code=1` یک معنی ندارد.

## جدول‌ها

- `coverage_mapping`
- `event_type_mapping`
- `loss_location_mapping`
- `occupation_mapping`
- `occupation_group_mapping`
- `damaged_item_mapping`
- `damage_type_mapping`
- `financial_damage_type_mapping`
- `property_type_mapping`
- `structure_type_mapping`
- `risk_density_mapping`
- `ownership_type_mapping`

ستون‌های مهم هر Mapping:

- `mapped_code`: کد Excel/مدل
- `mapped_title`: معنی فارسی کد
- `source_value`: مقدار اصلی Excel
- `category`: دسته تفسیری
- `interpretation_description`: توضیح برای API/گزارش
- `risk_level`: برای Mappingهایی که ریسک دارند
- `mapping_version`: نسخه Mapping
- `active`: فعال/غیرفعال

قبل از INSERT داده‌های اصلی، lookup table مربوط باید با Excel پر شود؛ FK جلوی ورود کدی را می‌گیرد که Mapping آن هنوز وارد نشده است.
