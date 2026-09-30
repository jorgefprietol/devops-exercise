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

## Publicar y probar con un solo comando

```sh
py -3 scripts/demo.py --public
```

Este comando construye la aplicación, inicia los contenedores, abre un túnel Pinggy, comprueba HTTPS (incluido `TRACE → 405 ERROR`) y genera los archivos privados de Postman. Copia la URL que imprime la consola. Cloudflare no es necesario.

La sesión gratuita dura hasta 60 minutos. Repite el mismo comando para crear otra sesión y URL. Mantén Docker, el PC e Internet activos. No es una URL permanente ni alojamiento 24/7.

## Kubernetes completo

Con Docker Desktop en modo Linux y Python 3.10 o posterior:

```sh
py -3 scripts/lab.py --public
```

El script descarga `kind` y `kubectl` si faltan, comprueba sus SHA-256, crea un nodo de control y dos trabajadores, prepara Calico y Metrics Server, conserva los secretos y despliega Kong, dos réplicas de la API, Redis persistente y HPA. Utiliza la imagen pública verificada por digest en `infra/release-image.txt`; permite sustituirla mediante `--image`. No requiere SDK .NET ni cuenta de nube. La primera ejecución necesita Internet y descarga varias imágenes; el laboratorio se ha probado con 16 GB asignados a Docker.

Para preparar además los otros dos entornos:

```sh
py -3 scripts/lab.py --public --all-environments
```

La producción local está en `https://127.0.0.1:9443/DevOps`. Los otros namespaces se pueden probar por sus URLs públicas. Los tres nodos comparten el equipo; esto demuestra distribución lógica, sin equivaler a alta disponibilidad física.

Renueva únicamente la publicación de un entorno:

```sh
py -3 scripts/public_tunnel.py production --renew
```

El pipeline remoto y su agente requieren la cuenta del propietario del repositorio. Descargar el código no concede acceso a su GitHub ni conecta automáticamente otro equipo al despliegue del propietario. La ejecución local y la publicación temporal funcionan sin esos accesos.

## TRACE y HEAD

- GET, PUT, PATCH, DELETE, OPTIONS y TRACE devuelven HTTP 405 con el texto exacto `ERROR`.
- Kong normaliza también el 405 generado por Nginx antes del enrutamiento. No se habilita la reflexión de encabezados de TRACE.
- HEAD devuelve HTTP 405 sin cuerpo, como exige HTTP. Pedir un cuerpo literal para HEAD sería incompatible con el protocolo.
- La entrada pública Pinggy se verifica con la misma prueba. Una URL antigua de Cloudflare continúa interceptando TRACE: usa la URL actual que imprime el script.

El cliente usa HTTPS con certificado público válido; el tramo de túnel está cifrado por SSH. El HTTP de Kong queda dentro de la red Docker o Kubernetes y no tiene un puerto abierto en el host.

Consulta [Postman](postman/README.md), [operación del pipeline](PUBLICACION.txt) y [decisiones de arquitectura](ARQUITECTURA.txt).

Referencias: [HEAD en RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-head), [túneles Pinggy](https://pinggy.io/docs/) y [límites de la modalidad gratuita](https://pinggy.io/).
