BEGIN;
INSERT INTO public.ownership_type
 (code,title,source_table,source_version,active,requires_review)
VALUES ('2','مالک','ownership_type_mapping','ownership_002',true,true),
       ('3','مستأجر','ownership_type_mapping','ownership_002',true,true)
ON CONFLICT (code) DO NOTHING;
COMMIT;
