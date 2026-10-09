BEGIN;
INSERT INTO public.ownership_type_mapping
 (mapped_code, mapped_title, source_value, mapping_version, active, interpretation_description)
SELECT code, title, title, 'ownership_002', true,
 'User-defined ownership option; not mapped to current trained model.'
FROM (VALUES ('2','مالک'),('3','مستأجر')) AS v(code,title)
WHERE NOT EXISTS (SELECT 1 FROM public.ownership_type_mapping m WHERE m.mapped_code=v.code);
COMMIT;
