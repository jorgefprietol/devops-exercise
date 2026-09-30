# Instalar y probar el ejercicio

La demostración local necesita Docker con contenedores Linux, Docker Compose y Python 3.10 o posterior. Inicia Docker Desktop antes de ejecutar los comandos. El primer arranque necesita Internet para descargar dependencias e imágenes.

Cloudflare, una cuenta de nube y el SDK .NET no son necesarios para esta demostración.

## Descargar y arrancar

En Windows, tanto en PowerShell como en Git Bash:

```sh
git clone https://github.com/jorgefprietol/devops-exercise.git
cd devops-exercise
py -3 scripts/demo.py
```

En Linux o macOS, utiliza `python3 scripts/demo.py`. Si descargaste el ZIP, descomprímelo y abre una terminal dentro de la carpeta que contiene `README.txt` y `compose.yaml`.

El script genera las credenciales privadas, construye la aplicación, inicia Kong, dos instancias de la API y Redis, y ejecuta las pruebas. La respuesta esperada es:

```json
{"message":"Hello Juan Perez your message will be sent"}
```

El servicio está en `https://127.0.0.1:8443/DevOps`. Abrir esa dirección en un navegador envía GET: la prueba válida utiliza POST y la ejecuta el script con un JWT nuevo.

## Repetir la prueba o detener la demostración

Desde la carpeta del proyecto:

```sh
py -3 scripts/demo.py --test-only
py -3 scripts/demo.py --stop
```

`--test-only` comprueba contenedores ya iniciados; no los arranca. Para la primera ejecución, o si están detenidos, utiliza `py -3 scripts/demo.py`.

## Si aparece que scripts/demo.py no existe

La ruta `scripts/demo.py` es relativa a la carpeta actual de la terminal. En Git Bash, el prompt `MINGW64 /` indica que estás en la raíz de Git Bash; no es la carpeta del repositorio.

Puedes entrar primero en tu copia del proyecto. Ejemplo para un repositorio guardado en `D:\Proyectos\devops-exercise`:

```sh
# Git Bash
cd /d/Proyectos/devops-exercise
py -3 scripts/demo.py --test-only
```

O indicar la ruta completa, desde cualquier carpeta, tanto en PowerShell como en Git Bash:

```sh
py -3 "D:/Proyectos/devops-exercise/scripts/demo.py" --test-only
```

Sustituye la carpeta del ejemplo por la ubicación real. Una vez localizado el archivo, el script trabaja automáticamente desde la raíz de su propio proyecto.

## Qué función cumple Cloudflare

| Forma de probar | Necesita Cloudflare | Alcance |
| --- | --- | --- |
| Docker Compose en el equipo del evaluador | No | Instalación local con el comando anterior. |
| Kubernetes por HTTPS local | No | Cluster y entorno previamente preparados; comandos en PUBLICACION.txt. |
| Acceso desde Internet al PC de esta demostración | Se utiliza como túnel temporal | Publica HTTPS mientras el PC, Docker y el túnel estén activos. |
| Aplicación en otro servidor o proveedor de nube | No es obligatorio | Necesita entrada accesible, certificado TLS válido y configuración de despliegue. |

Cloudflare no figura como requisito del ejercicio. La instalación local permite reproducir la solución, pero no sustituye la URL HTTPS accesible desde Internet cuando el evaluador necesita probar el HOST entregado desde su equipo.

El pipeline publicado actualmente comprueba una URL pública después de desplegar. Para esa comprobación necesita el túnel activo o un acceso HTTPS alternativo configurado. La demostración Compose es independiente de ese flujo de publicación.

## TRACE y HEAD

- GET, PUT, PATCH, DELETE y OPTIONS devuelven HTTP 405 con el texto `ERROR`.
- HEAD devuelve HTTP 405 sin cuerpo. Es el comportamiento requerido por HTTP, no un fallo de instalación.
- En la configuración actual, TRACE devuelve HTTP 405 con JSON al acceder directamente a Kong y HTTP 405 con HTML al pasar por Cloudflare. Se rechaza antes de la API; retirar Cloudflare por sí solo no cambia la respuesta de Kong.

Si la evaluación exige específicamente `405 ERROR` también para TRACE, hay que adaptar el tratamiento del error en el gateway y usar una entrada pública que permita controlar esa respuesta. El objetivo sería rechazar el método con el texto solicitado, sin habilitar la función de reflejar encabezados de TRACE. Esa adaptación no forma parte de la implementación actual. Las instrucciones de instalación no eliminan esta diferencia de contrato.

Referencias: [semántica de HEAD en RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-head) y [función y límites de Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Para Kubernetes, entornos y versiones, consulta [PUBLICACION.txt](PUBLICACION.txt). Las decisiones y límites están en [ARQUITECTURA.txt](ARQUITECTURA.txt).
