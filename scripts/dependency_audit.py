"""Detiene la compilación ante vulnerabilidades NuGet o una auditoría incompleta."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def inspect(report):
    if report.get('version') != 1 or not report.get('projects'):
        raise ValueError('El informe de dependencias no contiene proyectos válidos')
    if report.get('problems'):
        raise ValueError('La consulta de vulnerabilidades informó problemas')
    findings = []
    for project in report['projects']:
        if project.get('problems'):
            raise ValueError('No se pudo auditar un proyecto')
        for framework in project.get('frameworks', []):
            for group in ('topLevelPackages', 'transitivePackages'):
                for package in framework.get(group, []):
                    for issue in package.get('vulnerabilities', []):
                        findings.append((package['id'], package['resolvedVersion'], issue['severity'], issue['advisoryurl']))
    return sorted(set(findings))


def main():
    command = ['dotnet', 'list', 'DevOpsExercise.sln', 'package', '--vulnerable',
               '--include-transitive', '--format', 'json', '--output-version', '1']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode or result.stderr.strip():
        raise RuntimeError('No se completó la auditoría NuGet. Revisa conectividad y restauración de paquetes.')
    report = json.loads(result.stdout.lstrip('\ufeff'))
    findings = inspect(report)
    output = ROOT / 'evidence' / 'green'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'dependencias.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, version, severity, url in findings:
        print(f'Vulnerabilidad: {name} {version} | {severity} | {url}')
    if findings:
        raise RuntimeError('Actualiza las dependencias vulnerables antes de publicar.')
    print('CORRECTO: sin vulnerabilidades NuGet conocidas en dependencias directas y transitivas.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        sys.exit(str(error))
