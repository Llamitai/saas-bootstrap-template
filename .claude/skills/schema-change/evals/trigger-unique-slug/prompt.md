---
description: Invokes the schema-change skill.
tags: [trigger, trigger]
max_turns: 3
allowed_tools: [Skill]
---

Add a unique constraint on (tenant_id, slug) for roles and create the Alembic migration without losing existing data.
