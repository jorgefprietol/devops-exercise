EJERCICIO DEVOPS
Jorge Fidel Prieto Linares

API REST implementada con .NET, Kong, Redis, Docker, Kubernetes y GitHub Actions.
El servicio valida credenciales, controla la reutilización de JWT y responde
al contrato solicitado mediante POST /DevOps.

Repositorio: https://github.com/jorgefprietol/devops-exercise
Integración y despliegue: https://github.com/jorgefprietol/devops-exercise/actions
Detalle de entrega: ENTREGA.txt. Operación del entorno: PUBLICACION.txt.

ARQUITECTURA
Cliente HTTPS -> Kong -> Servicio Kubernetes -> Réplicas de la API -> Redis

Kong controla la entrada y comprueba API Key y JWT. La API valida el cuerpo,
la firma, el emisor, la audiencia, la vigencia y el identificador de transacción.
Redis registra ese identificador mediante una operación atómica y con vencimiento.
Una segunda petición con el mismo JWT aceptado devuelve HTTP 409.

CONTRATO
POST /DevOps
Encabezados: X-Parse-REST-API-Key y X-JWT-KWY
Content-Type: application/json

Solicitud:
{"message":"This is a test","to":"Juan Perez","from":"Rita Asturia","timeToLifeSec":45}

Respuesta HTTP 200:
{"message":"Hello Juan Perez your message will be sent"}

X-JWT-KWY y los textos del contrato se conservan como aparecen en el enunciado.
El cliente envía el JWT sin Bearer; Kong realiza la adaptación internamente.
GET, PUT, PATCH, DELETE y OPTIONS: HTTP 405 y texto ERROR.
HEAD: HTTP 405 sin cuerpo, conforme al protocolo HTTP.
Credenciales inválidas: 401; Kong puede responder 403 para una API Key incorrecta.
Cuerpo inválido: 400. Tipo no admitido: 415. Cuerpo excesivo: 413.
JWT reutilizado: 409. Redis no disponible: 503. Ruta inexistente: 404.

DECISIONES
- Se implementa la respuesta indicada; no se incluye una cola de envío real.
- timeToLifeSec pertenece al mensaje y admite de 1 a 86400 segundos.
- La vigencia del JWT es independiente: máximo cinco minutos.
- El JWT se emite por consola, sin añadir otra ruta pública.
- /health/live y /health/ready son rutas internas que Kong no publica.
- Los secretos se leen del entorno. .env y .local no se versionan.

EJECUCIÓN LOCAL CON DOCKER COMPOSE
Requisitos: .NET SDK 8 y su entorno de ejecución, Python >=3.10 y Docker
con contenedores Linux. Ejecutar los comandos desde la raíz del repositorio.

py -3 scripts/init_local.py
docker compose -p jorge-devops-exercise up -d --build --wait --wait-timeout 180

En Linux puede utilizarse python3 en lugar de py -3.
Para cargar las variables privadas en PowerShell:

Get-Content .env | ForEach-Object {
  $parts = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
}

Prueba integral local:
py -3 scripts/smoke.py https://localhost:8443 --local

--local permite el certificado de laboratorio únicamente en localhost.
En la URL pública se valida TLS normalmente, sin excepciones.

GENERACIÓN DE JWT
dotnet build tools/TokenIssuer -c Release
$jwt = dotnet tools/TokenIssuer/bin/Release/net8.0/TokenIssuer.dll

El emisor necesita JWT_SECRET en su entorno. El secreto de firma no se publica.
Cada petición de negocio requiere un JWT nuevo. Para comprobar el despliegue
público desde el equipo configurado:

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-PublicApi.ps1

Desde otra carpeta hay que proporcionar la ruta absoluta del script.
Abrir /DevOps en el navegador envía GET y no comprueba el caso correcto de POST.

COMPILACIÓN Y PRUEBAS
dotnet restore --locked-mode
dotnet build -c Release --no-restore -warnaserror
dotnet format --verify-no-changes --no-restore
dotnet test -c Release --no-restore --collect:"XPlat Code Coverage" --results-directory evidence/green
py -3 scripts/coverage_gate.py 80

El umbral de cobertura de líneas es 80%. Las pruebas verifican el contrato,
credenciales, vigencia, repeticiones concurrentes y validación del cuerpo.
La prueba integral utiliza Kong, dos instancias de API y Redis real.
Los resultados remotos están en el artefacto pruebas-y-cobertura de Actions.

INTEGRACIÓN Y DESPLIEGUE
Compilación -> Pruebas -> Imagen Docker -> Despliegue Kubernetes

Las etapas se ejecutan en Ubuntu 24.04. Las acciones se fijan por SHA y utilizan
Node.js 24. La imagen se identifica por su digest. Un agente local verifica la
solicitud, aplica la versión y comunica el resultado de la prueba HTTPS.
El acceso al cluster y las credenciales de la aplicación permanecen locales.

Solicitud de cambios a master/develop: compilación y pruebas.
Push a master: despliegue a production tras superar las comprobaciones.
Push a develop: despliegue a development. Etiqueta v*: despliegue a staging.
Ejecución manual: selección de entorno y, opcionalmente, etiqueta vX.Y.Z.
Los entornos adicionales requieren su configuración y túnel correspondientes.

INFRAESTRUCTURA Y LÍMITES
kind ejecuta un nodo de control y dos trabajadores en Docker. Son nodos lógicos
en un PC, no servidores físicamente independientes. Calico aplica políticas de
red y Metrics Server entrega las métricas al HPA. La API escala de 2 a 6 réplicas;
Kong mantiene 2 réplicas. La distribución respeta taints y revisiones de despliegue.
Redis tiene una réplica persistente y no ofrece alta disponibilidad.

El túnel HTTPS tiene una dirección temporal. El PC, Docker y el túnel deben
permanecer activos. La operación continua requiere infraestructura remota,
dominio estable y una estrategia de disponibilidad para Redis.
.NET 8 termina su soporte el 10 de noviembre de 2026; una evolución productiva
debe contemplar la migración a una versión LTS vigente.

RECUPERACIÓN
kubectl -n devops-production rollout history deployment/devops-api
kubectl -n devops-production rollout undo deployment/devops-api
kubectl -n devops-production rollout status deployment/devops-api

La reversión de la API no restaura secretos, Redis ni configuración de Kong.
Se debe comprobar la compatibilidad y repetir la prueba pública.

ORGANIZACIÓN
src/DevOps.Api: servicio y autenticación.
tools/TokenIssuer: emisor de JWT.
tests/DevOps.Api.Tests: pruebas de contrato y seguridad.
scripts: inicialización, despliegue, validación y operación.
infra: configuración de Kubernetes local.
evidence: resultados de las comprobaciones.
.github/workflows: integración y despliegue automatizados.
