# HOST y JWT de la evaluación

El candidato proporciona la dirección del servicio y un JWT válido para cada transacción. El repositorio incluye el emisor: `scripts/issue_jwt.py`. Funciona con Python 3.10 o posterior, sin instalar .NET ni dependencias de Python adicionales.

## HOST es el servidor y, si corresponde, el puerto

En el comando del enunciado, `https://${HOST}/DevOps` se completa así:

| Instalación | HOST | URL de la petición |
| --- | --- | --- |
| Docker Compose local | `127.0.0.1:8443` | `https://127.0.0.1:8443/DevOps` |
| Kubernetes local, production | `127.0.0.1:9443` | `https://127.0.0.1:9443/DevOps` |
| Acceso remoto opcional | Dominio HTTPS vigente suministrado por el candidato | `https://DOMINIO/DevOps` |

En Postman, `base_url` incluye `https://`, pero no `/DevOps`. En PowerShell se usa `$apiHost` porque `$Host` es una variable reservada.

`127.0.0.1` corresponde al equipo que hace la petición: permite evaluar una copia instalada localmente. Para probar la instalación del candidato desde otro equipo se necesita una dirección accesible desde ese equipo. Una URL local no demuestra acceso público. El túnel es opcional para la evaluación local.

## Emitir y probar una transacción local

Desde la carpeta del repositorio, con Docker Desktop en modo Linux iniciado:

```powershell
py -3 scripts/demo.py
$apiHost = '127.0.0.1:8443'
$jwt = py -3 scripts/issue_jwt.py
$body = '{"message":"This is a test","to":"Juan Perez","from":"Rita Asturia","timeToLifeSec":45}'
$body | curl.exe --insecure --silent --show-error --request POST `
  --header 'X-Parse-REST-API-Key: 2f5ae96c-b558-4c7b-a590-a501ae1c3f6c' `
  --header "X-JWT-KWY: $jwt" `
  --header 'Content-Type: application/json' `
  --data-binary '@-' "https://$apiHost/DevOps"
```

Respuesta: `{"message":"Hello Juan Perez your message will be sent"}` y HTTP 200. Para mostrar el estado agrega `--write-out '\nHTTP %{http_code}\n'` a curl.

`--insecure` se usa exclusivamente aquí por el certificado autofirmado de loopback. Para una URL pública con certificado válido, se elimina esa opción. En Linux/macOS usa `python3 scripts/issue_jwt.py`, `curl` y la sintaxis de variables de tu shell.

Kubernetes production utiliza el mismo emisor y el puerto 9443. Para otros entornos, emite desde su configuración: `py -3 scripts/issue_jwt.py --environment staging` o `--environment development`. Los JWT de un entorno no son válidos en otro.

## Entregar el JWT al evaluador

El candidato ejecuta el emisor justo antes de la prueba y entrega la URL, la API Key del ejercicio y **el JWT resultante** por un canal privado. No entrega `JWT_SECRET`, `.env` ni los entornos privados de Postman de su instalación. El token dura cinco minutos y debe usarse una sola vez; por eso no se incluye un token fijo en GitHub.

En Postman, el receptor puede crear una petición POST independiente con el cuerpo anterior y los tres encabezados, pegando el token directamente en `X-JWT-KWY`, sin `Bearer` y sin un script que genere otro token. La colección de pruebas del repositorio está pensada para el propietario de una instalación: usa sus secretos locales para emitir tokens nuevos automáticamente.

Si el evaluador levanta su propia copia, el arranque crea claves nuevas en su equipo y el emisor suministrado en el repositorio genera JWT válidos para esa instalación. Un JWT emitido en el equipo del candidato no sirve en una instalación con otra clave.

## Un JWT por transacción

Cada ejecución del emisor produce un `jti` aleatorio nuevo, firmado con HS256, con emisor, audiencia y caducidad validados. Redis reserva el identificador de forma atómica, compartida por las réplicas.

1. Primera petición válida con un JWT nuevo: **200**.
2. Repetir la petición con ese mismo JWT: **409**.
3. Emitir otro JWT y enviar otra petición válida: **200**.
4. Diez peticiones simultáneas con el mismo JWT nuevo: una **200** y nueve **409**.

Una petición rechazada antes de aceptar la transacción, por ejemplo por un cuerpo inválido, no consume el identificador. El control de un solo uso protege las transacciones aceptadas. La vigencia del JWT es independiente de `timeToLifeSec`, que pertenece al mensaje.

Las comprobaciones automáticas de estos casos se ejecutan con `py -3 scripts/demo.py --test-only` y en el pipeline. El informe `evidence/host-jwt-local.json` registra la comprobación local sin guardar tokens ni secretos.
