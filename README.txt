SOLUCIÓN DEL EJERCICIO DEVOPS
Jorge Prieto - Material de preparación y laboratorio

Implementación .NET 8 con Kong DB-less, Redis, Docker Compose, Kubernetes y GitHub Actions.
El único endpoint de negocio es POST /DevOps. Las rutas /health/live y /health/ready
son internas: Kong no las publica. No hay una cola ni un envío real de mensajes;
se implementa exactamente la respuesta pedida en el ejercicio.

ARCHIVOS IMPORTANTES
src/DevOps.Api/            API, validación JWT, contrato y control de repetición
tools/TokenIssuer/         Generador CLI de JWT; no agrega un endpoint público
tests/DevOps.Api.Tests/    Pruebas de contrato y seguridad
scripts/smoke.py           Pruebas HTTPS a través del gateway y Redis real
scripts/kong_config.py     Gestor de API y balanceo declarativos
scripts/deploy.py          Infraestructura Kubernetes como código
infra/kind.yaml            Laboratorio con control-plane y dos workers
.github/workflows/ci-cd.yml Pipeline automático y manual
evidence/                 Resultados reales locales, sin credenciales

REQUISITOS LOCALES
.NET SDK 8 o 9 con runtime 8, Python 3 y Docker Desktop con contenedores Linux.
Este equipo tenía .NET 8 instalado. Antes de una puesta en producción duradera,
recomiendo migrar y volver a validar en .NET 10 LTS; .NET 8 termina soporte el
10 de noviembre de 2026. Las imágenes de infraestructura deben actualizarse y
fijarse a un digest revisado según la política de la organización.

INICIO EN POWERSHELL DESDE ESTA CARPETA
python scripts/init_local.py
docker compose -p jorge-devops-exercise up -d --build --wait --wait-timeout 180

Importar el entorno privado sin imprimir secretos:
Get-Content .env | ForEach-Object {
  $parts = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
}

Probar el sistema completo:
python scripts/smoke.py https://localhost:8443 --local

El parámetro --local tolera el certificado autofirmado generado por Kong SOLO
en localhost. Una entrega remota exige DNS y certificado válido; no usar -k.

GENERAR JWT Y REPRODUCIR EL CURL DEL EJERCICIO
dotnet build tools/TokenIssuer -c Release
$jwt = dotnet tools/TokenIssuer/bin/Release/net8.0/TokenIssuer.dll
$baseUrl = 'https://localhost:8443'
$body = '{ "message":"This is a test", "to":"Juan Perez", "from":"Rita Asturia", "timeToLifeSec":45 }'
curl.exe -k -i -X POST "$baseUrl/DevOps" `
  -H "X-Parse-REST-API-Key: $env:API_KEY" `
  -H "X-JWT-KWY: $jwt" `
  -H 'Content-Type: application/json' --data-raw $body

Para un HOST remoto: quitar -k y establecer $baseUrl con https:// y dominio.
No usar $HOST en PowerShell: es una variable reservada. Generar un JWT nuevo
antes de cada transacción; repetir uno aceptado devuelve 409.
Respuesta 200: {"message":"Hello Juan Perez your message will be sent"}

VALIDACIÓN DEL CÓDIGO
dotnet restore --locked-mode
dotnet build -c Release --no-restore -warnaserror
dotnet format --verify-no-changes --no-restore
dotnet test -c Release --no-restore --collect:'XPlat Code Coverage' --results-directory evidence/green
python scripts/coverage_gate.py 80

Los tests de API usan un almacén de repetición en memoria como doble de prueba.
La prueba smoke verifica Redis real, Kong y ambos contenedores. No confundir ambos
niveles ni afirmar que la cobertura del adaptador Redis es completa.

CONTRATO Y SUPUESTOS
Se conserva el header X-JWT-KWY tal como aparece, aunque parezca una errata.
Kong espera Bearer: una pre-function normaliza internamente el JWT a Authorization
y conserva X-JWT-KWY para la API. Un Authorization enviado por el cliente se
descarta en esa normalización; no reemplaza el header exigido en el ejercicio.
JWT: HS256, iss=devops-candidate, aud=devops-api, jti UUID único, iat, nbf, exp.
El CLI lo emite con 5 minutos de validez. La API limita su vida a 300 segundos.
timeToLifeSec se valida entre 1 y 86400. Es un campo del mensaje, no la vida del
JWT. El enunciado no define procesamiento asíncrono ni tiempos de entrega.
API Key de evaluación: scripts/init_local.py la obtiene del valor del enunciado;
no es el secreto con el que se firma el JWT. El secreto se genera aleatoriamente.
GET/PUT/PATCH/DELETE/OPTIONS: 405 con texto ERROR y Allow: POST.
HEAD: 405 sin cuerpo, porque HTTP prohíbe contenido en la respuesta a HEAD.
Autenticación inválida: 401 (Kong puede dar 403 si la API Key es incorrecta).
Body inválido: 400; Content-Type incorrecto: 415; tamaño excesivo: 413.
JWT reutilizado: 409; Redis no disponible: 503; ruta inexistente: 404.
Las respuestas de autenticación del gateway son las propias de Kong; el requisito
de texto ERROR aplica a los métodos no permitidos en /DevOps.

KUBERNETES Y ENTREGA REAL
El pipeline despliega en un cluster previamente preparado. No crea cuentas cloud.
Se requieren Kubernetes >=1.30, dos workers, Metrics Server, StorageClass por
defecto, CNI que aplique NetworkPolicy e implementación de Service LoadBalancer.
En kind, un LoadBalancer requiere un complemento; kind solo no publica una IP.
En AWS/EKS y Azure/AKS el controlador cloud debe estar instalado/configurado.
La API usa 2 réplicas, HPA 2..6 a 65% CPU y distribución entre dos nodos.
HPA crea pods; el autoscaler del proveedor agrega nodos, y se configura aparte.
Kong usa dos réplicas; el Service público balancea hacia ellas, y un Service
interno reparte conexiones hacia los pods API. No se exige afinidad de sesión.
Redis usa una réplica con PVC y AOF appendfsync always: es una limitación de
disponibilidad explícita. Una pérdida de datos puede permitir repetir JWT aún
vigentes; para producción, diseñar Redis HA y la recuperación según ese riesgo.

CONFIGURACIÓN EN GITHUB
Crear repositorio público, subir el contenido de esta carpeta sin .env ni .local.
Rama por defecto: master. Crear environments development, staging y production.
Registrar por environment estos secrets:
  API_KEY, JWT_SECRET, REDIS_PASSWORD (hex aleatorio), KUBECONFIG_B64,
  TLS_CRT_B64, TLS_KEY_B64
Variable por environment: PUBLIC_URL (por ejemplo https://devops.ejemplo.com).
El kubeconfig debe permitir aplicar esta infraestructura en su namespace; la
creación inicial de namespaces requiere permiso cluster-scope. Usar cuentas de
despliegue restringidas; en una adaptación cloud usar OIDC en vez de kubeconfig
persistente. No cargar credenciales administrativas del usuario por comodidad.
El contenedor se publica en GHCR. Hacer público el paquete para que los nodos
puedan descargarlo, o añadir imagePullSecrets y credenciales de solo lectura.
DNS debe apuntar al LoadBalancer y el certificado debe cubrir ese DNS.
Proteger master, exigir build/test y configurar reglas de environments. Para
cumplir el despliegue automático del ejercicio no agregar aprobación manual
obligatoria a production. En un banco real esto se ajustaría a su gobierno.

EVENTOS DEL PIPELINE
PR a master/develop -> Build y Test, sin publicar ni desplegar.
Push a develop -> Build, Test, Package y Deploy en development.
Push a master -> Build, Test, Package y Deploy automático en production.
Push de tag v* -> validación y despliegue en staging.
workflow_dispatch -> elegir environment y opcionalmente tag vX.Y.Z.
Producción solo admite commits alcanzables desde master; un master sin versión
manual siempre apunta a producción. Las etiquetas publicadas deben ser inmutables.
Se despliega por digest de imagen, no por latest. Conservar el digest anterior
para rollback. Los tags seleccionan código versionado; esta implementación lo
reconstruye. Para promover exactamente el mismo binario entre entornos, guardar
y promover el digest del release en vez de reconstruirlo.

DESPLIEGUE BAJO DEMANDA DESDE LINUX
Exportar de forma segura los secrets indicados y además:
  DEPLOY_ENV=staging
  IMAGE=ghcr.io/usuario/repositorio@sha256:<digest real de 64 caracteres>
  PUBLIC_URL=https://dominio-con-certificado-valido
bash scripts/rollout.sh

El paso comprueba rollout y luego ejecuta smoke HTTPS. Un cambio de secretos
fuerza una nueva revisión mediante un hash de configuración. La rotación de
JWT con una sola clave requiere ventana coordinada o ampliar a dos claves con
kid; esa rotación sin interrupción no está implementada en este ejemplo.

ROLLBACK DE APLICACIÓN
kubectl -n devops-production rollout history deployment/devops-api
kubectl -n devops-production rollout undo deployment/devops-api
kubectl -n devops-production rollout status deployment/devops-api
Repetir smoke con JWT nuevo. rollout undo NO restaura automáticamente Secrets,
Kong, Redis ni el resto de la infraestructura. Para recuperación completa usar
el commit de configuración compatible y los secretos de esa versión.

ANTES DE ENTREGAR AL EVALUADOR
1. Ejecutar CI/CD en el repositorio real y revisar sus evidencias.
2. Verificar dos workers y que las réplicas estén distribuidas entre ellos.
3. Mostrar HPA operativo con métricas y un ensayo de carga.
4. Probar cURL contra el dominio HTTPS real sin -k.
5. Facilitar repositorio, HOST, pasos para generar JWT y evidencias.
   No entregar un token vencido o ya consumido como única forma de probar.
6. Explicar que el JWT se emite fuera de la API con el CLI y que su secreto
   permanece en manos del emisor; acordar cómo recibirá tokens el evaluador.

PARAR SOLO ESTE LABORATORIO
docker compose -p jorge-devops-exercise stop
Este comando preserva los datos del laboratorio. No usar comandos globales de
limpieza Docker, porque pueden afectar otros proyectos de esta computadora.
