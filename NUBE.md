# Desplegar en otro equipo, AWS o Azure

La aplicación y los manifiestos Kubernetes son portables. La infraestructura de la aplicación está en `scripts/deploy.py`; los perfiles de proveedor están en `infra/cloud/`. [AWS.md](AWS.md) describe la alternativa temporal con CloudFormation y dos EC2 ejecutando K3s, incluida la eliminación programada. Esta alternativa crea su propia red y clúster, y genera cargos.

Las secciones EKS/AKS de este documento requieren clústeres administrados existentes; esos perfiles tienen pruebas de configuración y no equivalen a una ejecución comprobada en EKS o AKS. El repositorio no crea una cuenta cloud.

## Otro equipo sin una cuenta cloud

Con Docker Linux y Python 3.10 o posterior, desde el repositorio:

```sh
python3 scripts/demo.py
```

Esto inicia Kong, dos instancias de la API y Redis. Para verificar también dos nodos trabajadores, políticas de red y HPA:

```sh
python3 scripts/lab.py --all-environments
```

En Windows sustituye `python3` por `py -3`. El primer arranque necesita Internet. No requiere un túnel público. Los nodos de kind comparten el mismo equipo físico.

## Clúster existente

Requisitos del clúster: Kubernetes 1.30 o posterior, al menos dos trabajadores Linux compatibles con la imagen publicada (amd64), métricas de CPU, almacenamiento dinámico y un complemento de red que aplique NetworkPolicy. Se necesita kubectl autenticado y con permisos para crear los recursos de la aplicación y verificar nodos, métricas y clases de almacenamiento. No ejecutes `bootstrap_addons.py` sobre EKS/AKS: sus ajustes corresponden únicamente a kind.

Prepara un archivo **privado**, por ejemplo `.local/cloud.env`, con `API_KEY`, `JWT_SECRET` y `REDIS_PASSWORD`. La API Key es la del ejercicio; genera un secreto JWT de al menos 32 bytes y una contraseña Redis hexadecimal de 32 a 128 caracteres. Conserva esos valores al volver a desplegar; un cambio de secreto invalida los JWT anteriores. Utiliza credenciales diferentes por entorno. No publiques este archivo ni las claves TLS.

Prepara el certificado PEM y su clave privada para el dominio público. El script comprueba que ambos correspondan. Para el laboratorio local se utiliza el certificado de localhost; no se presenta como certificado válido de un dominio cloud.

```sh
kubectl config get-contexts
python3 scripts/deploy_cluster.py --context CONTEXTO --environment production --profile infra/cloud/aws-eks.json --secrets-file .local/cloud.env --tls-cert .local/cloud.crt --tls-key .local/cloud.key
```

En Azure cambia el perfil por `infra/cloud/azure-aks.json`. El contexto se indica explícitamente y no cambia el contexto global. `--image REGISTRO/IMAGEN@sha256:DIGEST` permite seleccionar la versión; si se omite utiliza `infra/release-image.txt`. Se puede conservar GHCR como registro, no es obligatorio migrar las imágenes a ECR/ACR.

El comando comprueba requisitos, aplica la infraestructura, espera los despliegues y verifica dos réplicas distribuidas en dos nodos, HPA con métricas y el contrato HTTPS mediante `kubectl port-forward` limitado a loopback. El proceso temporal se cierra al terminar. Esta prueba comprueba la aplicación; no certifica todavía la entrada pública del proveedor.

Una vez asignada la dirección del balanceador y configurado el DNS del dominio, repite con `--public-url https://api.ejemplo.com` para comprobar HTTPS público, certificado, API Key, JWT, concurrencia, TRACE y HEAD. Esta comprobación no desactiva TLS.

## AWS EKS

El perfil se dirige a EKS con AWS Load Balancer Controller y EBS CSI Driver previamente instalados y autorizados. Usa NLB de nivel TCP; Kong termina TLS, por lo que el balanceador no sustituye la respuesta HTTP de TRACE. Prepara subredes y reglas de red según la documentación de AWS. Para almacenamiento, si no existe `gp3`:

```sh
kubectl --context CONTEXTO apply -f infra/cloud/aws-storage.yaml
```

La clase conserva el volumen tras eliminar su reclamación; revisa manualmente los recursos y sus costes al desmontar el entorno. EKS Auto Mode utiliza otros identificadores para balanceo y almacenamiento: este perfil no se presenta como un perfil de Auto Mode.

## Azure AKS

El perfil utiliza Azure Load Balancer y la clase `managed-csi` del controlador Azure Disk. Comprueba que exista y que el clúster tenga configuradas las políticas de red y métricas. Kong termina TLS dentro del clúster. Las reglas de red deben permitir la entrada HTTPS y las comprobaciones del balanceador.

## Pipeline y alcance

El pipeline incluido se ejecuta en GitHub Actions: master → production, develop → development y etiquetas → staging. Con `DEPLOY_TARGET=aws`, utiliza OIDC y Systems Manager para desplegar en el servidor de la pila descrita en AWS.md. Con otro valor utiliza el agente del laboratorio local; en ese caso el equipo y el agente deben estar encendidos. La prueba del clúster no requiere Pinggy ni Cloudflare.

El comando de despliegue externo puede utilizarse desde un ejecutor con acceso autenticado a un clúster cloud. La identidad cloud, los permisos, el acceso de red y la conexión del pipeline a EKS/AKS deben configurarse en la cuenta de destino; no están provisionados ni verificados en este laboratorio. Para esa conexión se recomienda identidad federada OIDC con permisos mínimos, evitando claves permanentes.

La API, balanceo, Redis, escalado y entornos se mantienen. Redis tiene una sola réplica persistente: no ofrece alta disponibilidad de datos. El escalado configurado aumenta pods de la API; no crea automáticamente más nodos del proveedor.

Referencias oficiales:

- [Balanceadores NLB en EKS](https://docs.aws.amazon.com/eks/latest/userguide/network-load-balancing.html).
- [EBS CSI en EKS](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html).
- [Azure Load Balancer en AKS](https://learn.microsoft.com/en-us/azure/aks/load-balancer-standard).
- [Almacenamiento en AKS](https://learn.microsoft.com/en-us/azure/aks/concepts-storage).
- [OIDC en GitHub Actions](https://docs.github.com/en/actions/concepts/security/openid-connect).
