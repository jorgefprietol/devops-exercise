"""Configuración declarativa de Kong. Las credenciales se leen del entorno."""
import os


def config(local=False):
    targets = ['api1:8080', 'api2:8080'] if local else ['devops-api:8080']
    auth = [
        # Kong requiere Bearer. Se adapta el encabezado X-JWT-KWY internamente
        # para conservar el contrato solicitado al cliente.
        {'name': 'pre-function', 'config': {'access': [
            "kong.service.request.clear_header('Authorization'); "
            "local t = kong.request.get_header('X-JWT-KWY'); "
            "if t then kong.service.request.set_header('Authorization', 'Bearer ' .. t) end"]}},
        {'name': 'key-auth', 'config': {'key_names': ['X-Parse-REST-API-Key'],
         'key_in_header': True, 'key_in_query': False, 'key_in_body': False, 'hide_credentials': False}},
        {'name': 'jwt', 'config': {'header_names': ['Authorization'], 'uri_param_names': [],
         'cookie_names': [], 'key_claim_name': 'iss', 'claims_to_verify': ['exp', 'nbf']}}
    ]
    result = {
        '_format_version': '3.0',
        # Es global para alcanzar también el 405 generado por Nginx antes del
        # enrutamiento (TRACE). Solo normaliza errores; nunca refleja la petición.
        'plugins': [{'name': 'post-function', 'config': {
            'header_filter': ["if kong.response.get_status() == 405 then "
                "kong.response.set_header('Content-Type', 'text/plain; charset=utf-8'); "
                "kong.response.set_header('Content-Length', '5'); end"],
            'body_filter': ["if kong.response.get_status() == 405 then "
                "kong.response.set_raw_body('ERROR'); end"]}}],
        'consumers': [{'username': 'evaluator',
          'keyauth_credentials': [{'key': os.environ['API_KEY']}],
          'jwt_secrets': [{'key': 'devops-candidate', 'algorithm': 'HS256', 'secret': os.environ['JWT_SECRET']}]}],
        'upstreams': [{'name': 'devops-pool', 'algorithm': 'round-robin',
          'targets': [{'target': t, 'weight': 100} for t in targets]}],
        'services': [{'name': 'devops-service', 'host': 'devops-pool', 'port': 8080,
          'protocol': 'http', 'retries': 0, 'connect_timeout': 5000,
          'read_timeout': 10000, 'write_timeout': 10000,
          'routes': [
            {'name': 'devops-post', 'paths': ['~/DevOps$'], 'methods': ['POST'],
             'strip_path': False, 'regex_priority': 10, 'plugins': auth},
            {'name': 'devops-method-error', 'paths': ['~/DevOps$'],
             'strip_path': False, 'regex_priority': 0}
          ]}]
    }
    if os.environ.get('ISSUER_KEY'):
        result['services'].append({'name': 'evaluation-issuer', 'host': 'token-issuer', 'port': 8080,
            'protocol': 'http', 'retries': 0, 'connect_timeout': 5000, 'read_timeout': 5000,
            'write_timeout': 5000, 'routes': [{'name': 'evaluation-token',
                'paths': ['~/auth/token$'], 'strip_path': False}]})
    return result
