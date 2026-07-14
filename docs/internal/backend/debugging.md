# Backend debugging

El backend incluye un override Docker para arrancar uvicorn y el worker SAQ con
`debugpy`.

## Levantar en modo debug

Desde la raíz del repo:

```bash
just backend debugpy
```

Puertos:

| Puerto | Proceso |
|---|---|
| `5678` | API uvicorn (`config.main:app`) |
| `5679` | worker SAQ (`config.tasks.worker_settings`) |

## VS Code

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "API :5678",
      "type": "debugpy",
      "request": "attach",
      "connect": { "host": "localhost", "port": 5678 },
      "pathMappings": [
        { "localRoot": "${workspaceFolder}/backend", "remoteRoot": "/app" }
      ]
    }
  ]
}
```

La API no espera al debugger para arrancar. Conecta el IDE antes de disparar la
request que quieras inspeccionar.

## Emails locales (Mailpit)

El stack de `just backend dev` incluye Mailpit como servidor SMTP de desarrollo
(`SMTP_HOST=mailpit`, `SMTP_PORT=1025` en `backend/.env`). Todo correo enviado
por el backend queda capturado y se inspecciona en la UI web:
`http://localhost:8027`.
