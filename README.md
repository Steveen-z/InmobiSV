# InmobiSV · Encuentra tu lugar

Plataforma académica de comercialización de terrenos en El Salvador. Aplicación web con backend real, base de datos relacional persistente y tres perfiles de usuario. El alcance está pensado para una demostración escolar, no para operar transacciones inmobiliarias reales.

## 1. Requisitos

- Python 3.10 o posterior (recomendado 3.11+). En Windows marca «Add Python to PATH» al instalarlo.
- Navegador actualizado.
- Git, únicamente si vas a clonar o subir el repositorio.
- No necesitas npm, pip, XAMPP, MySQL ni configurar un servicio de base de datos. SQLite viene con Python.

## 2. Ejecutar el proyecto

Descarga y descomprime el ZIP; abre una terminal en la carpeta `InmobiSV` (donde está `app.py`). Si lo obtuviste desde Git, entra en la carpeta clonada.

**Windows (PowerShell):**

```powershell
py -3 app.py --demo
```

**Linux / macOS:**

```bash
python3 app.py --demo
```

Abre **http://127.0.0.1:8000** en tu navegador. Mantén abierta la terminal mientras utilizas la aplicación. Detén el servidor con `Ctrl+C`.

El parámetro `--demo` crea las tablas, tres cuentas y seis terrenos ficticios. Al volver a ejecutar el servidor, SQLite conserva las modificaciones y las cuentas existentes. No hace falta ejecutar SQL manualmente. Para usar otro puerto: `python3 app.py --demo --port 8080` (en Windows, `py -3` en lugar de `python3`). En este caso abre http://127.0.0.1:8080.

> **Importante:** no abras `static/index.html` con doble clic: necesita el servidor HTTP y la API. Las credenciales de demostración son públicas y no deben utilizarse en Internet.

## 3. Usuarios de prueba

| Rol | Correo | Contraseña |
| --- | --- | --- |
| Comprador | comprador@inmobi.test | Inmobi2026! |
| Vendedor | vendedor@inmobi.test | Inmobi2026! |
| Administrador | administrador@inmobi.test | Inmobi2026! |

En la ventana de ingreso existen botones que rellenan las credenciales para facilitar la exposición. El registro público solo permite comprador o vendedor. El administrador se crea únicamente mediante el inicializador de demostración; no se puede elegir al registrarse. No introduzcas datos personales reales para la exposición.

## 4. Cómo demostrar las funciones

1. Como visitante: explora y filtra terrenos por ubicación, precio, área, texto y tipo; selecciona dos o más (máximo cuatro) para comparar.
2. Como comprador: guarda un terreno del catálogo como favorito, abre su detalle y consulta los avisos. Puedes solicitar el cambio de rol desde «Mi cuenta».
3. Cierra sesión e ingresa como vendedor: edita el precio del terreno guardado y redúcelo. Publica un nuevo terreno en tres pasos (datos, ubicación y fotos); prueba pausar y reactivar una publicación. Puedes registrar un teléfono propio desde «Mi cuenta» para habilitar WhatsApp en tus anuncios no ficticios. Los anuncios de ejemplo no contactan a números reales.
4. Regresa a la cuenta compradora y revisa «Avisos»: debe aparecer la reducción del precio. Los avisos son internos y se consultan al entrar o recargar, no se envían por correo o push.
5. Como administrador: revisa usuarios y publicaciones, deshabilita/habilita compradores o vendedores, modera estados y aprueba o rechaza solicitudes de cambio de rol. El administrador no puede deshabilitarse a sí mismo ni a otro administrador.

El mapa de detalle utiliza OpenStreetMap y necesita Internet; las demás funciones operan en local. El enlace al mapa permite explorar puntos de interés; no hay cálculo automático de cercanía ni verificación de terrenos.

## 5. Estructura del código

```text
InmobiSV/
├── app.py                  # Servidor HTTP, API, autenticación y lógica de negocio
├── schema.sql              # Tablas, claves foráneas, restricciones e índices
├── static/
│   ├── index.html          # Estructura de la interfaz
│   ├── style.css           # Diseño responsive
│   ├── app.js              # Navegación, formularios, fetch y eventos
│   └── *.svg               # Ilustraciones locales de terrenos ficticios
├── tests/test_app.py       # Prueba de integración HTTP/SQLite
├── INFRAESTRUCTURA.md      # Arquitectura, stack y relaciones de datos
├── README.md
└── .gitignore             # Excluye bases locales y archivos generados
```

La base `data/inmobisv.sqlite3` se genera al iniciar. Puedes abrirla con DB Browser for SQLite o con la extensión SQLite de tu editor. Para reiniciar la demostración, detén el servidor, haz una copia si necesitas conservar datos, elimina únicamente `data/inmobisv.sqlite3` (y archivos auxiliares si existen) y arranca de nuevo con `--demo`.

## 6. Pruebas automatizadas

Desde la raíz del proyecto:

```bash
python3 -m unittest discover -s tests -v
```

En Windows usa `py -3 -m unittest discover -s tests -v`. La prueba levanta un servidor temporal en un puerto libre y crea una base SQLite independiente; no toca tus datos. Verifica registro, autenticación, permisos, propiedad de anuncios, favoritos, avisos por baja de precio, moderación, cambio de rol y cierre de sesión.

## 7. Subir a GitHub

El ZIP contiene el código fuente sin `.git` ni bases de datos locales. También se entrega un archivo `InmobiSV.bundle` con el commit inicial; puedes restaurarlo mediante `git clone InmobiSV.bundle InmobiSV-repo` y entrar en `InmobiSV-repo`.

Para subir desde el ZIP, crea un repositorio vacío llamado `InmobiSV` (preferiblemente privado si es una entrega escolar) en https://github.com/new — no marques README, licencia ni gitignore para evitar conflictos iniciales. Luego, en la carpeta del código:

```bash
git init -b main
git add .
git commit -m "InmobiSV: plataforma académica con SQLite y tres roles"
git remote add origin https://github.com/TU_USUARIO/InmobiSV.git
git push -u origin main
```

Si clonaste el bundle, conserva el historial y ejecuta solo `git remote set-url origin https://github.com/TU_USUARIO/InmobiSV.git` y `git push -u origin main`.

Si Git solicita identidad para un commit: configura tu nombre y correo con `git config user.name "Tu nombre"` y `git config user.email "Tu correo"`. Para el push autentícate con Git Credential Manager, SSH o GitHub CLI; no publiques tokens ni contraseñas personales. Alternativamente, desde la carpeta con Git inicializado, con GitHub CLI instalado y autenticado: `gh repo create InmobiSV --private --source=. --remote=origin --push`.

## 8. Alcance y seguridad

Contraseñas almacenadas con PBKDF2-HMAC-SHA256, sal aleatoria por cuenta y 600 000 iteraciones, sesiones opacas con cookies HttpOnly y SameSite=Lax, consultas SQL parametrizadas, permisos comprobados en el servidor, validación de formularios y restricción de imágenes. El campo de teléfono de las publicaciones no ficticias es visible para el contacto directo. Las cuentas de demostración no son secretos.

Es un servidor de desarrollo local de la biblioteca estándar de Python, no un servidor de producción. No incluye HTTPS local, recuperación de contraseña, correo de verificación, rate limiting, revisión documental de identidad, procesamiento avanzado de imágenes, ni respaldo automático. Antes de publicar en Internet se necesita revisar estos controles, configurar HTTPS y cookies Secure, cambiar credenciales y retirar los accesos de demostración. Para una aplicación real, se recomienda migrar a un framework servidor de producción y almacenamiento de imágenes externo.
