# Visor HTML: web

Frontend del Visor HTML: web interna para que los usuarios suban sus archivos HTML (reportes de pandas, Plotly, Jupyter, etc.), los vean en el navegador y los compartan.

React 19 + Vite + TypeScript, publicado en Azure Static Web Apps. La API y la infraestructura viven en el repo `html-viewer-api`.

- Drag & drop de uno o varios `.html` / `.htm`, con progreso por archivo.
- Lista de "Mis archivos": abrir, renombrar, copiar enlace, compartir, eliminar.
- Enlaces legibles y personalizables: `/u/{usuario}/{nombre}`.
- Etiquetas (por ejemplo, una por proyecto): cada archivo se arrastra a la etiqueta que corresponda, o se mueve con el selector de la fila.
- Visibilidad por archivo: **Solo yo** u **Organización** (cualquier usuario del tenant con el enlace).
- Enlaces públicos con vencimiento (1, 7 o 30 días), revocables, para gente sin cuenta.

## Relación con la API

La web llama a `/api/...` en su mismo origen, con la cookie de sesión de Static Web Apps. SWA hace el login con Entra ID y reenvía cada llamada a la API (FastAPI, en la Function App enlazada como *linked backend*), así que no hay URL de API que configurar ni CORS hacia la API.

`public/staticwebapp.config.json` define qué exige login: `/api/public/*` es anónimo, el resto de `/api/*` requiere usuario. También fija el proveedor de identidad y la CSP. `dev/staticwebapp.config.json` es igual, pero permite Azurite.

Los archivos se suben y se leen directo contra Blob Storage con SAS cortas que entrega la API. El HTML se muestra en un `<iframe sandbox>` sin `allow-same-origin`, servido desde el dominio de Blob Storage: páginas que usan `localStorage` o cookies pueden no funcionar del todo; los reportes típicos (Plotly, Bokeh, Folium, pandas, Jupyter exportado) funcionan.

## Estructura

Organizada por dominio (*screaming architecture*), con los mismos nombres que la API:

```
src/
  files/                Archivos: lista, fila, subida (upload/), visor, renombrar, editar enlace, eliminar
  labels/               Etiquetas: secciones donde se sueltan archivos, alta, renombrar, eliminar
  shares/               Enlaces públicos: diálogo de compartir y página pública
  auth/                 Sesión de Static Web Apps
  shared/               Cliente HTTP, mensajes, formato y ui/ (ventana modal, iframe aislado)
  app/                  Rutas, layout y página de inicio
e2e/                    Pruebas de punta a punta (Playwright)
public/staticwebapp.config.json   Rutas, auth, CSP (producción)
dev/staticwebapp.config.json      Igual, pero permite Azurite (desarrollo)
scripts/deploy.sh       Build y deploy a la Static Web App
```

Cada dominio trae su `api.ts`, sus `types.ts` y sus componentes. Toda acción que pide un dato o una confirmación abre la misma ventana modal (`shared/ui/Dialog.tsx`); no se usan `prompt`, `confirm` ni `alert` del navegador.

## Desarrollo local

Requisitos: Node 20+, y la API corriendo en `http://localhost:7071` (en `html-viewer-api`: `./start.sh`). No hace falta Docker.

```bash
npm install
npm start
```

Abrí http://localhost:4280 (no el 5173). `npm start` levanta Vite detrás del emulador de Static Web Apps, que es quien hace el login y reenvía `/api` a la API. Muestra un formulario de login falso: completá un usuario cualquiera.

## Pruebas

De punta a punta con Playwright, contra la app real: la web compilada detrás del emulador de SWA, la API y Azurite. Con la API corriendo (`./start.sh` en `html-viewer-api`):

```bash
npx playwright install chromium   # solo la primera vez
npm run test:e2e
```

El comando compila la web y la sirve en el puerto 4281 solo mientras duran las pruebas, así que siempre prueba el código actual y no interfiere con un `npm start` abierto en el 4280. Cada prueba usa usuarios nuevos y al terminar borra lo que creó: no depende de los datos que haya, no los toca y no deja nada.

Qué cubren (`e2e/`):

| Archivo | Flujos |
| --- | --- |
| `isolation` | Cada usuario ve solo lo suyo: listas, enlaces, etiquetas, llamadas directas a la API, acceso sin sesión |
| `session` | Login por el formulario, volver al enlace pedido después del login, salir |
| `upload` | Tipos y tamaño rechazados, varios archivos a la vez con el mismo nombre, nombres con acentos |
| `files` | Renombrar, eliminar y cancelar, siempre en la ventana modal |
| `links` | Enlace legible, personalizarlo, nombre repetido, enlace público y su revocación |
| `legacy` | Archivos subidos antes de los enlaces legibles |
| `labels` | Crear, arrastrar entre etiquetas, mover con el selector, cambios seguidos, renombrar, eliminar |
| `viewer` | Barra del visor, aislamiento del HTML subido, enlaces viejos, direcciones inexistentes |
| `errors` | Qué ve el usuario cuando la API falla en cada acción |
| `responsive` | Pantalla de teléfono |

En todas las pruebas se verifica además que la página no tire errores sin atrapar ni use `prompt`/`confirm`/`alert` del navegador.

## Deploy en Azure

La Static Web App la crea el deploy de `html-viewer-api` (Bicep). Con eso hecho:

```bash
export RESOURCE_GROUP=rg-html-viewer
./scripts/deploy.sh
```

Buildea, restringe el login a tu tenant y publica. Si el resource group tiene más de una Static Web App, indicá cuál con `SWA_NAME`.

### Configuración

| Variable | Default | |
| --- | --- | --- |
| `VITE_MAX_UPLOAD_MB` | 20 | Límite de subida en el cliente. Tiene que coincidir con `maxUploadMb` en la infra. |

Para desactivar los enlaces públicos, quitá la ruta `/api/public/*` de `staticwebapp.config.json` (pasa a exigir login) y el bloque "Enlace público" de `ShareDialog.tsx`.
