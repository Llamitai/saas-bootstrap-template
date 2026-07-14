# saas-bootstrap-template

> **This repository is 100% generated — never edit it by hand.**
> Every release of [Llamitai/wise](https://github.com/Llamitai/wise)
> rebuilds this tree with `scripts/build_template.py` and overwrites whatever
> is here. Published tags are never moved.

Generate a project:

```bash
uvx copier copy --trust gh:Llamitai/saas-bootstrap-template my-app
```

Update an existing project to a newer template release:

```bash
cd my-app && uvx copier update --trust
```

`--trust` is required because the template declares `_tasks`
(`cp backend/.env.example backend/.env` and `git init`, first copy only).

After generating, regenerate the backend lockfile before any production
build: `cd my-app/backend && uv lock`.
