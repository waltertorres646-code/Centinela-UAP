# Centinela UAP para Windows

Esta es una adaptación defensiva y de **solo lectura**. Observa publicaciones
públicas de `r/UFOs`, crea una base SQLite y un CSV local, y no publica,
comenta, modera ni descarga videos o imágenes.

## Primer encendido

1. Solicita/crea acceso autorizado a la Data API de Reddit.
2. Obtén `client_id` y `client_secret` para una aplicación de lectura.
3. Ejecuta `INSTALAR_Y_PROBAR.bat`.
4. La primera vez se abrirá `.env`. Completa sus tres valores, guarda y cierra.
5. Ejecuta otra vez `INSTALAR_Y_PROBAR.bat`.
6. Si la prueba termina bien, abre `VIGILAR_UAP.bat`.

## Traductor local inglés → español

Después de la primera prueba, ejecuta una sola vez `INSTALAR_TRADUCTOR.bat`.
Descargará el modelo inglés-español de Argos Translate. A partir de entonces la
traducción se realiza localmente y el CSV mostrará `titulo_es` y `texto_es`.
El original se conserva siempre mientras la publicación siga pública. Si el
traductor no está instalado o falla, el Centinela continúa sin detenerse.

No pongas usuario ni contraseña de Reddit. No subas `.env` a GitHub y no
compartas sus valores en chats o capturas.

## Resultados

Se crean dentro de `datos`:

- `centinela_uap.sqlite3`: archivo técnico con publicaciones y observaciones.
- `publicaciones_uap.csv`: tabla compatible con Excel.

La traducción automática es una ayuda de lectura: puede contener errores y no
reemplaza el texto original para análisis o citación.

Las palabras de alerta solo sirven para priorizar revisión humana. No prueban
espionaje, origen, autenticidad ni intención.

## Eliminaciones

Cuando la API señala una publicación como eliminada o retirada, el programa
vacía el título, autor, texto y URL local. Conserva ID, fechas, estado y huella
SHA-256 para documentar que el registro observado cambió sin conservar el
contenido retirado.

## Diferencias con el programa original

- No usa rutas de Ubuntu.
- No necesita contraseña.
- No copia contenido a otro subreddit.
- No descarga archivos potencialmente grandes o inseguros.
- No usa Discord, cron, SSH, FFmpeg ni GitHub Actions.
- Tiene punto de entrada seguro y no actúa al importarlo.

## Normas

Usa este programa únicamente con acceso aprobado y respetando los términos de
Reddit, la privacidad, los derechos de autor y la legislación aplicable.
