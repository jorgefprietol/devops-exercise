EJERCICIO DEVOPS
Jorge Fidel Prieto Linares

Inicio rápido para PowerShell, Git Bash, Linux y macOS: INICIO_RAPIDO.md.
Incluye cómo resolver "scripts/demo.py no existe" y cuándo se necesita el túnel.
Colección de Postman y pasos de importación: postman/README.md.

API REST implementada con .NET, Kong, Redis, Docker, Kubernetes y GitHub Actions.
El servicio valida credenciales, controla la reutilización de JWT y responde
al contrato solicitado mediante POST /DevOps.

Repositorio: https://github.com/jorgefprietol/devops-exercise
Integración y despliegue: https://github.com/jorgefprietol/devops-exercise/actions
Detalle de entrega: ENTREGA.txt. Operación: PUBLICACION.txt.
Decisiones y límites: ARQUITECTURA.txt. Matriz del ejercicio: REQUISITOS.csv.

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
TRACE: HTTP 405 con cuerpo literal ERROR, normalizado por Kong sin reflejar
la petición. La entrada pública Pinggy conserva esta respuesta; Cloudflare no.
Credenciales inválidas: 401; Kong puede responder 403 para una API Key incorrecta.
Cuerpo inválido: 400. Tipo no admitido: 415. Cuerpo excesivo: 413.
JWT reutilizado: 409. Redis no disponible: 503. Ruta inexistente: 404.

DECISIONES
- Se implementa la respuesta indicada; no se incluye una cola de envío real.
- timeToLifeSec pertenece al mensaje y admite de 1 a 86400 segundos.
- La vigencia del JWT es independiente: máximo cinco minutos.
- El JWT se emite por consola o Postman, sin añadir otra ruta pública.
- /health/live y /health/ready son rutas internas que Kong no publica.
- Los secretos se leen del entorno. .env y .local no se versionan.

PRUEBA RÁPIDA PARA EL EVALUADOR
Requisitos: Git, Docker Desktop iniciado con contenedores Linux y Python >=3.10.
No se necesitan cuenta cloud, Kubernetes ni SDK .NET para esta demostración.
Si se descarga el ZIP del repositorio, Git tampoco es necesario.

Windows / PowerShell:
git clone https://github.com/jorgefprietol/devops-exercise.git
cd devops-exercise
py -3 scripts/demo.py

Linux / macOS: sustituir py -3 por python3 en los comandos de Python.
El script crea secretos propios, construye la imagen, inicia Kong, dos APIs y
Redis, ejecuta las pruebas HTTPS e imprime la respuesta solicitada.
La primera ejecución tarda lo que requiera descargar y construir las imágenes.

Repetir las comprobaciones sin reiniciar:
py -3 scripts/demo.py --test-only

Este comando se ejecuta dentro del repositorio y requiere contenedores activos.
Si Git Bash muestra MINGW64 /, entra primero en la carpeta donde clonaste el
proyecto. Alternativa desde cualquier carpeta: usa la ruta absoluta del script,
por ejemplo py -3 "D:/Proyectos/devops-exercise/scripts/demo.py" --test-only.
Sustituye la carpeta por la ubicación real. Para iniciar usa el comando sin
--test-only. El error de archivo inexistente ocurre antes de ejecutar el script.

Detener conservando los datos:
py -3 scripts/demo.py --stop

Conflicto de puerto o red: seleccionar un puerto y una subred privada libres.
Ejemplo: py -3 scripts/demo.py --port 18443 --subnet 10.203.73.0/24
Usar las mismas opciones al repetir la prueba o detener ese entorno.
El arranque recrea los contenedores del proyecto de demostración para usar la
imagen recién construida y conserva el volumen de Redis. No afecta Kubernetes.

En Docker Desktop aparecen Kong, Redis, api1 y api2. La URL local utiliza HTTPS:
https://127.0.0.1:8443/DevOps. Abrirla en un navegador envía GET y devuelve ERROR;
la prueba correcta de POST la ejecuta demo.py con un JWT nuevo.
--local solo admite el certificado de laboratorio en localhost/127.0.0.1.
En la URL pública se valida TLS normalmente, sin excepciones.

GENERACIÓN DE JWT
Para usar el emisor .NET se necesita SDK 8 y cargar primero las variables:
Get-Content .env | ForEach-Object {
  $parts = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
}
dotnet build tools/TokenIssuer -c Release
$jwt = dotnet tools/TokenIssuer/bin/Release/net8.0/TokenIssuer.dll

El emisor necesita JWT_SECRET en su entorno. El secreto de firma no se publica.
Cada petición de negocio requiere un JWT nuevo. Para comprobar el despliegue
público desde el equipo configurado:

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-PublicApi.ps1

Desde otra carpeta hay que proporcionar la ruta absoluta del script.
Abrir /DevOps en el navegador envía GET y no comprueba el caso correcto de POST.

COMPILACIÓN Y PRUEBAS
Para desarrollo y pruebas unitarias instalar .NET SDK 8 y su runtime.
dotnet restore --locked-mode
py -3 scripts/dependency_audit.py
dotnet build -c Release --no-restore -warnaserror
dotnet format --verify-no-changes --no-restore
dotnet test -c Release --no-restore --collect:"XPlat Code Coverage" --results-directory evidence/green
py -3 scripts/coverage_gate.py 80
py -3 -m unittest discover -s tests -p "test_*.py"

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
Si la rama seleccionada es master, el destino siempre es production.
Los tres entornos usan namespaces, Redis y secretos de firma independientes.
Inicio conjunto: powershell -File scripts/Start-AllEnvironments.ps1
Prueba conjunta sin túnel: py -3 scripts/verify_environments.py
Preparación y versiones: PUBLICACION.txt. Evidencias: evidence/cierre-entornos.json.

INFRAESTRUCTURA Y LÍMITES
kind ejecuta un nodo de control y dos trabajadores en Docker. Son nodos lógicos
en un PC, no servidores físicamente independientes. Calico aplica políticas de
red y Metrics Server entrega las métricas al HPA. La API escala de 2 a 6 réplicas;
Kong mantiene 2 réplicas. La distribución respeta taints y revisiones de despliegue.
Redis tiene una réplica persistente y no ofrece alta disponibilidad.

El túnel HTTPS tiene una dirección temporal. Solo para el acceso público, el PC, Docker y el túnel deben
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

ARRANQUE COMPLETO CON UN COMANDO
Solo Docker Desktop (Linux) y Python >=3.10 como requisitos previos:
py -3 scripts/demo.py --public
Construye la API, inicia Kong, dos APIs y Redis, publica HTTPS temporal,
prueba POST y métodos inválidos incluido TRACE y exporta entornos Postman.
Sin --public funciona completamente en local y no crea un túnel.

Laboratorio Kubernetes: dos trabajadores, Calico, métricas, HPA y persistencia:
py -3 scripts/lab.py --public
Agregar --all-environments para preparar también staging y development.
Descarga kind/kubectl si faltan y verifica sus SHA-256; instala dependencias
en un entorno virtual privado. La API usa el digest de infra/release-image.txt,
una imagen pública verificada; --image permite elegir otro digest.
La primera instalación necesita Internet, espacio para imágenes y suficiente
memoria en Docker (este laboratorio se ha probado con 16 GB asignados).
Los tres nodos lógicos comparten el equipo; no son tres máquinas físicas.

Pinggy gratuito dura hasta 60 minutos por sesión. Para renovar Kubernetes:
py -3 scripts/public_tunnel.py production --renew
Actualiza la URL y Postman; requiere compartir la URL nueva. No es alojamiento
24/7 ni una dirección permanente. El túnel termina TLS y transporta el tráfico
al origen mediante SSH. El puerto HTTP interno de Kong no se publica al host.

KUBERNETES Y PORTABILIDAD
py -3 scripts/lab.py --all-environments
py -3 scripts/verify_environments.py
El pipeline verifica el cluster sin una URL pública. NUBE.md explica el
despliegue en clusters existentes con perfiles EKS/AKS y sus requisitos.
