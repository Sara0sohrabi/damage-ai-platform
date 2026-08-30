# Mappingهای واقعی سیستم
# این فایل منبع اولیه Mapping است و سپس با load_mappings.py داخل PostgreSQL ذخیره می‌شود.

MAPPINGS = [
    # نوع آسیب
    {"mapping_version":"mapping_001","mapping_name":"damage_type","source_value":"تخریب","mapped_code":"1","mapped_title":"تخریب"},
    {"mapping_version":"mapping_001","mapping_name":"damage_type","source_value":"سوختگی","mapped_code":"2","mapped_title":"سوختگی"},
    {"mapping_version":"mapping_001","mapping_name":"damage_type","source_value":"دودزدگی و آلودگی","mapped_code":"3","mapped_title":"دودزدگی و آلودگی"},
    {"mapping_version":"mapping_001","mapping_name":"damage_type","source_value":"ترک","mapped_code":"4","mapped_title":"ترک"},
    {"mapping_version":"mapping_001","mapping_name":"damage_type","source_value":"ترکیدگی لوله","mapped_code":"5","mapped_title":"ترکیدگی لوله"},
    {"mapping_version":"mapping_001","mapping_name":"damage_type","source_value":"آب گرفتگی و آب زدگی","mapped_code":"6","mapped_title":"آب گرفتگی و آب زدگی"},

    # پوشش
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"آتش سوزی، صاعقه و انفجار","mapped_code":"1","mapped_title":"آتش سوزی، صاعقه و انفجار"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"زلزله و آتشفشان","mapped_code":"2","mapped_title":"زلزله و آتشفشان"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"سیل و طغیان آب","mapped_code":"3","mapped_title":"سیل و طغیان آب"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"طوفان، گردباد و تندباد","mapped_code":"4","mapped_title":"طوفان، گردباد و تندباد"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"ترکیدگی لوله آب و فاضلاب","mapped_code":"5","mapped_title":"ترکیدگی لوله آب و فاضلاب"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"ضایعات آب برف و باران","mapped_code":"6","mapped_title":"ضایعات آب برف و باران"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"سقوط هواپیما یا هلیکوپتر و قطعات آنها","mapped_code":"7","mapped_title":"سقوط هواپیما یا هلیکوپتر و قطعات آنها"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"سقوط اجسام خارجی","mapped_code":"8","mapped_title":"سقوط اجسام خارجی"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"پاکسازی و برداشت ضایعات","mapped_code":"9","mapped_title":"پاکسازی و برداشت ضایعات"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"شکست شیشه","mapped_code":"10","mapped_title":"شکست شیشه"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"سرقت با شکست حرز","mapped_code":"11","mapped_title":"سرقت با شکست حرز"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"ریزش سقف ناشی از سنگینی برف","mapped_code":"12","mapped_title":"ریزش سقف ناشی از سنگینی برف"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"ریزش، رانش و فروكش کردن زمین","mapped_code":"13","mapped_title":"ریزش، رانش و فروكش کردن زمین"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"ریزش کوه و سقوط بهمن","mapped_code":"14","mapped_title":"ریزش کوه و سقوط بهمن"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"نشت دستگاه آب افشان","mapped_code":"15","mapped_title":"نشت دستگاه آب افشان"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"اعتصاب، شورش و اغتشاش","mapped_code":"16","mapped_title":"اعتصاب، شورش و اغتشاش"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"نیاز به اجاره محل اسکان موقت","mapped_code":"17","mapped_title":"نیاز به اجاره محل اسکان موقت"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"نوسانات برق","mapped_code":"18","mapped_title":"نوسانات برق"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"نیاز به هزینه برگزاری مراسم ترحیم افراد مجاز به اقامت در محل مورد بیمه در صورت فوت به علت آتش سوزی","mapped_code":"19","mapped_title":"نیاز به هزینه برگزاری مراسم ترحیم افراد مجاز به اقامت در محل مورد بیمه در صورت فوت به علت آتش سوزی"},
    {"mapping_version":"mapping_001","mapping_name":"coverage","source_value":"از بین رفتن اسناد و مدارک","mapped_code":"20","mapped_title":"از بین رفتن اسناد و مدارک"}
]
