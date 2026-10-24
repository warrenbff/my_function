"""Install a project-local Neo4j and Java; no administrator rights required."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.cache' / 'neo4j'
VERSION = '5.26.30'


def download(url, path, checksum):
    if not path.exists():
        print('Downloading ' + path.name, flush=True)
        urllib.request.urlretrieve(url, path)
    if hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != checksum:
        path.unlink()
        raise RuntimeError('Download checksum mismatch; retry setup')


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    home = RUNTIME / ('neo4j-community-' + VERSION)
    if not home.exists():
        url = f'https://dist.neo4j.org/neo4j-community-{VERSION}-windows.zip'
        checksum = urllib.request.urlopen(url + '.sha256').read().decode().split()[0]
        archive = RUNTIME / 'neo4j.zip'
        download(url, archive, checksum)
        with zipfile.ZipFile(archive) as z:
            z.extractall(RUNTIME)
    java_dirs = list(RUNTIME.glob('zulu*/bin/java.exe'))
    if not java_dirs:
        url = 'https://api.azul.com/metadata/v1/zulu/packages/?java_version=21&os=windows&arch=x86&hw_bitness=64&archive_type=zip&java_package_type=jre&javafx_bundled=false&release_status=ga&availability_types=CA&latest=true'
        package = json.load(urllib.request.urlopen(url))[0]
        asset = json.load(urllib.request.urlopen('https://api.azul.com/metadata/v1/zulu/packages/' + package['package_uuid']))
        archive = RUNTIME / 'java.zip'
        download(asset['download_url'], archive, asset['sha256_hash'])
        with zipfile.ZipFile(archive) as z:
            z.extractall(RUNTIME)
        java_dirs = list(RUNTIME.glob('zulu*/bin/java.exe'))
    if not java_dirs:
        raise RuntimeError('Java installation not found')
    config_path = ROOT / 'neo4j' / 'local.json'
    if not config_path.exists():
        config = {'uri': 'bolt://127.0.0.1:7687', 'user': 'neo4j',
                  'password': secrets.token_urlsafe(24), 'database': 'neo4j'}
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    # Neo4j's Windows launcher mishandles Unicode home paths. Use an ASCII
    # junction; data still physically lives in this project's .cache directory.
    alias = Path(os.environ['LOCALAPPDATA']) / 'InvestmentOntologyNeo4j'
    if not alias.exists():
        escaped_alias = str(alias).replace("'", "''")
        escaped_runtime = str(RUNTIME).replace("'", "''")
        subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                        f"New-Item -ItemType Junction -Path '{escaped_alias}' -Target '{escaped_runtime}' | Out-Null"], check=True)
    if alias.resolve() != RUNTIME.resolve():
        raise RuntimeError('Runtime alias belongs to another project: ' + str(alias))
    env = os.environ.copy()
    java_home = alias / java_dirs[0].parents[1].name
    home = alias / home.name
    env['JAVA_HOME'] = str(java_home)
    env['NEO4J_HOME'] = str(home)
    conf = home / 'conf' / 'neo4j.conf'
    marker = '# Investment ontology local settings'
    content = conf.read_text(encoding='utf-8')
    if marker not in content:
        with conf.open('a', encoding='utf-8') as f:
            f.write('\n' + marker + '\nserver.default_listen_address=127.0.0.1\n'
                    'server.memory.heap.initial_size=256m\nserver.memory.heap.max_size=512m\n'
                    'server.memory.pagecache.size=256m\ndbms.usage_report.enabled=false\n')
    admin = home / 'bin' / 'neo4j-admin.ps1'
    if not (home / 'data' / 'databases' / 'system').exists():
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(admin), 'dbms', 'set-initial-password', config['password']],
                       env=env, check=True, stdout=subprocess.DEVNULL)
    (RUNTIME / 'runtime.json').write_text(json.dumps({'home': str(home), 'java_home': env['JAVA_HOME']}), encoding='utf-8')
    venv = ROOT / '.cache' / 'neo4j-venv'
    if not (venv / 'Scripts' / 'python.exe').exists():
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    subprocess.run([str(venv / 'Scripts' / 'python.exe'), '-m', 'pip', 'install', '-r',
                    str(ROOT / 'neo4j' / 'requirements.txt')], check=True)
    print('Setup complete. Run neo4j/start.ps1, then neo4j/sync.ps1.', flush=True)


if __name__ == '__main__':
    main()
