DELETE FROM public.directus_collections
WHERE collection NOT LIKE 'directus_%';

INSERT INTO public.directus_collections (
    collection,
    icon,
    note,
    display_template,
    hidden,
    singleton,
    translations,
    archive_field,
    archive_app_filter,
    archive_value,
    unarchive_value,
    sort_field,
    accountability,
    color,
    item_duplication_fields,
    sort,
    "group",
    collapse,
    preview_url,
    versioning
) VALUES
    ('email_addresses', NULL, NULL, NULL, false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 1, NULL, 'open', NULL, false),
    ('phone_numbers', NULL, NULL, NULL, false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 2, NULL, 'open', NULL, false),
    ('users', NULL, NULL, '{{username}}', false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 3, NULL, 'open', NULL, false),
    ('tenants', NULL, NULL, '{{name}}', false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 4, NULL, 'open', NULL, false),
    ('tenant_roles', NULL, NULL, '{{name}}', false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 5, NULL, 'open', NULL, false),
    ('tenant_users', NULL, NULL, '{{first_name}} {{last_name}}', false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 6, NULL, 'open', NULL, false),
    ('tenant_user_invitations', NULL, NULL, '{{email}}', false, false, NULL, NULL, true, NULL, NULL, NULL, 'all', NULL, NULL, 7, NULL, 'open', NULL, false)
ON CONFLICT (collection) DO UPDATE SET
    icon = EXCLUDED.icon,
    note = EXCLUDED.note,
    display_template = EXCLUDED.display_template,
    hidden = EXCLUDED.hidden,
    singleton = EXCLUDED.singleton,
    sort = EXCLUDED.sort,
    color = EXCLUDED.color,
    collapse = EXCLUDED.collapse,
    versioning = EXCLUDED.versioning;
