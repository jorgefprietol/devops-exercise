# Probar la API con Postman

La colección incluye 15 peticiones: mensaje válido, credenciales incorrectas, JWT reutilizado, validación del cuerpo, métodos HTTP y diagnóstico de TRACE. Genera automáticamente un JWT HS256 con identificador nuevo antes de cada petición. No hay que copiar tokens manualmente.

## Preparación local

Con Docker Desktop iniciado, ejecuta desde la carpeta del repositorio:

```sh
py -3 scripts/demo.py
py -3 scripts/export_postman_env.py
```

En Linux o macOS, sustituye `py -3` por `python3`. La exportación solo lee la configuración existente; no cambia credenciales ni inicia servicios.

## Importar y enviar

1. Abre Postman actualizado y pulsa **Import**.
2. Importa `postman/DevOps_Jorge_Prieto.postman_collection.json`.
3. Importa `.local/postman/Local_Compose.postman_environment.json` y selecciónalo como entorno activo.
4. Abre **01 - Petición válida → POST - Enviar mensaje (200)**.
5. Para el certificado autofirmado local, desactiva **SSL certificate verification** en la configuración de Postman únicamente durante la prueba en `127.0.0.1`. Actívala de nuevo para probar la URL pública. La colección no desactiva esta protección.
6. Pulsa **Send**. En **Test Results** verás las comprobaciones y en **Body** la respuesta:

```json
{"message":"Hello Juan Perez your message will be sent"}
```

Puedes ejecutar la colección completa con **Run collection**, una iteración, usando el entorno seleccionado. El caso de JWT reutilizado realiza una llamada preparatoria, por eso las 15 peticiones de la colección producen 16 solicitudes HTTP.

## URL pública

Si este equipo tiene publicada la demostración, el exportador también crea `Publico_production.postman_environment.json` y los entornos adicionales disponibles. Importa el entorno público y selecciónalo: la misma colección funciona sin modificar las peticiones. Mantén activa la verificación SSL. El equipo, los servicios y el túnel deben seguir encendidos. Si cambia la URL del túnel, vuelve a exportar e importar el entorno actualizado.

Cloudflare no es necesario para probar desde el equipo local.

## Credenciales

Los entornos de `.local/postman` contienen el secreto de firma y no se versionan. Úsalos en tu espacio privado de Postman: no los publiques, compartas ni adjuntes a la entrega. El tipo `secret` oculta la visualización, pero el archivo JSON sigue conteniendo el valor. El evaluador puede generar sus propias credenciales al arrancar su copia del proyecto y ejecutar el exportador. La plantilla pública contiene `jwt_secret` vacío y no permite enviar una petición válida hasta configurarlo.

## Interpretar los resultados

| Caso | Resultado esperado |
| --- | --- |
| POST válido | 200 y JSON exacto |
| API Key incorrecta | 401 o 403 |
| JWT inválido | 401 |
| JWT ya utilizado | Primera llamada 200, repetición 409 |
| Datos o JSON inválidos | 400 |
| Content-Type no admitido | 415 |
| GET, PUT, PATCH, DELETE, OPTIONS | 405 y texto `ERROR` |
| HEAD | 405 sin cuerpo, conforme al protocolo HTTP |
| TRACE | 405 del proxy; puede responder JSON o HTML |

El caso TRACE comprueba el rechazo, pero **no acredita el cuerpo literal `ERROR`**. Esa limitación continúa documentada en el proyecto. Las solicitudes con errores intencionales aparecen como pruebas correctas cuando se recibe el error esperado.

Si aparece un error de conexión, arranca la aplicación. Si aparece un error de certificado en localhost, revisa el paso 5. Si aparece 401 en el caso válido, revisa el entorno seleccionado y vuelve a exportarlo. No reemplaces `X-JWT-KWY` por otro nombre ni agregues `Bearer`: el contrato pide el token directamente.
