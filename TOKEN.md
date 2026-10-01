# Obtener un JWT para la evaluación

El servicio auxiliar `POST /auth/token` entrega un JWT firmado para el mismo
entorno. No requiere cuenta de AWS, CloudShell, Python ni el secreto de firma.
La API del ejercicio conserva su único endpoint de negocio: `POST /DevOps`.

El candidato proporciona la URL base y una **clave de evaluación privada**.
Esta clave se envía en `X-Evaluation-Key`; no es la API Key publicada en el
enunciado. No publicar la clave en GitHub ni en capturas.

## cURL

En Bash (Linux, macOS, Git Bash o CloudShell):

```bash
BASE_URL="https://3.145.153.25"
read -rsp 'Clave de evaluación: ' EVALUATION_KEY; echo
curl --fail-with-body --request POST "$BASE_URL/auth/token" \
  --header "X-Evaluation-Key: $EVALUATION_KEY"
```

La respuesta contiene `token`, `expires_in: 300` y `header: "X-JWT-KWY"`.
Copiar el valor de `token` como JWT, sin comillas y sin el prefijo Bearer.

Para obtener el JWT y ejecutar la prueba directamente (requiere Python 3):

```bash
JWT=$(curl --fail-with-body --silent --show-error --request POST "$BASE_URL/auth/token" \
  --header "X-Evaluation-Key: $EVALUATION_KEY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
curl --fail-with-body --request POST "$BASE_URL/DevOps" \
  --header "X-Parse-REST-API-Key: 2f5ae96c-b558-4c7b-a590-a501ae1c3f6c" \
  --header "X-JWT-KWY: $JWT" \
  --header "Content-Type: application/json" \
  --data '{"message":"This is a test","to":"Juan Perez","from":"Rita Asturia","timeToLifeSec":45}'
unset EVALUATION_KEY JWT
```

En Windows PowerShell puede obtenerse y utilizarse sin Python:

```powershell
$baseUrl = 'https://3.145.153.25'
$key = Read-Host 'Clave de evaluación' -AsSecureString
$credential = [System.Net.NetworkCredential]::new('', $key).Password
$jwt = (Invoke-RestMethod -Method Post -Uri "$baseUrl/auth/token" -Headers @{'X-Evaluation-Key'=$credential}).token
Invoke-RestMethod -Method Post -Uri "$baseUrl/DevOps" -ContentType 'application/json' -Headers @{
    'X-Parse-REST-API-Key'='2f5ae96c-b558-4c7b-a590-a501ae1c3f6c'
    'X-JWT-KWY'=$jwt
} -Body '{"message":"This is a test","to":"Juan Perez","from":"Rita Asturia","timeToLifeSec":45}'
Remove-Variable credential,jwt,key
```

Respuesta de `/DevOps`: `{"message":"Hello Juan Perez your message will be sent"}`.
Cada emisión genera un `jti` distinto. El JWT vence a los cinco minutos; al
reutilizarlo después de una transacción aceptada, `/DevOps` responde `409`.
Los JWT de la instalación local no funcionan en AWS y viceversa.

## Postman

Importar `postman/DevOps_Emisor.postman_collection.json`. Crear o importar un
entorno privado con `base_url` (sin `/DevOps`) y `issuer_key`.
Ejecutar en orden **1. Obtener JWT**, **2. Enviar mensaje**, **3. Reutilizar JWT**.
La primera petición guarda automáticamente el token; no se necesita `jwt_secret`.
La colección comprueba los estados 200, 200 y 409.

## Instalación local y administración

Desde la raíz del repositorio: `python3 scripts/demo.py` (Windows: `py -3 scripts/demo.py`).
El arranque crea una `ISSUER_KEY` aleatoria en `.env`, conservada entre reinicios,
y un entorno privado `Emisor_Local_Compose.postman_environment.json` en
`.local/postman/`. Importarlo con la colección anterior. El certificado local
es autofirmado; la excepción de verificación TLS debe limitarse al host local.
AWS utiliza un certificado público que debe verificarse normalmente.

En AWS la clave se conserva en `/opt/devops/private/production.env`, accesible
solo mediante la administración autorizada. No compartir este archivo: contiene
también los secretos de firma y Redis. Entregar únicamente `ISSUER_KEY` por canal
privado. Para revocarla, reemplazarla por un valor aleatorio de 32 bytes o más y
volver a desplegar. Los JWT ya emitidos caducan en un máximo de cinco minutos.

El emisor utiliza la misma imagen versionada, en un contenedor independiente con
el rol `token-issuer`. No tiene acceso a Redis ni credenciales de AWS. Kubernetes
solo permite entrada desde Kong; el puerto del emisor no se publica directamente.
La respuesta no se almacena en caché y el secreto de firma nunca se entrega.
Hay una réplica auxiliar y un límite global de 30 solicitudes por minuto en ese
proceso, incluidos intentos inválidos; se reinicia al reiniciar el contenedor.
Un exceso responde `429`: esperar un minuto. Esta protección es suficiente para
la demostración, pero no sustituye un proveedor de identidad para producción.

En Kubernetes, `infra/issuer-image.txt` fija el digest de la versión verificada
del emisor, independiente de la versión de API seleccionada para desplegar.
Esto permite probar versiones anteriores de la API sin perder la emisión de
JWT. Al cambiar el código del emisor, publicar y verificar primero la nueva
imagen y actualizar ese archivo. Docker Compose construye ambos servicios
desde el código descargado.

La emisión no amplía la duración ni el presupuesto del laboratorio AWS. Su
disponibilidad termina cuando se apagan los recursos de evaluación.
