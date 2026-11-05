"""Install only scoped JSON credentials on an ephemeral GitHub-hosted runner.

No admin configuration, .env, connection-string overrides or credential output.
"""
import argparse
import json
import os
from pathlib import Path
import re
import ssl

TARGETS = {
    'writer': ('safetrip_writer', 'advisory-writer.json', 'SAFETRIP_WRITER_CONFIG'),
    'reader': ('safetrip_reader', 'advisory-reader.json', 'SAFETRIP_READER_CONFIG'),
    'publisher': ('safetrip_score_publisher', 'official-score-publisher.json', 'SAFETRIP_PUBLISHER_CONFIG'),
}
ROOT = Path(__file__).resolve().parents[1]


def scoped_config(raw, role):
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {'host', 'port', 'dbname', 'user', 'password'}:
        raise ValueError('Expected exactly the five scoped connection fields')
    if any(not isinstance(value[k], str) or not value[k] for k in ['host', 'dbname', 'user', 'password']):
        raise ValueError('Missing connection fields')
    if (not re.fullmatch(r'[a-z0-9.-]+\.pooler\.supabase\.com', value['host'])
            or str(value['port']) != '5432'
            or not re.fullmatch(TARGETS[role][0] + r'\.[a-z0-9]+', value['user'])):
        raise ValueError('Unexpected hosted role or session-pooler target')
    return value


def install(roles):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Credential installation is restricted to disposable Actions runners')
    configs = {role: scoped_config(os.environ[TARGETS[role][2]], role) for role in roles}
    targets = {(c['host'], str(c['port']), c['dbname'], c['user'].split('.', 1)[1]) for c in configs.values()}
    if len(targets) != 1:
        raise ValueError('Scoped accounts must target the same project')
    ca = os.environ['SAFETRIP_DATABASE_CA']
    ssl.create_default_context(cadata=ca)
    directory = ROOT / '.local/supabase'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    files = {directory / 'prod-ca.crt': ca,
             **{directory / TARGETS[r][1]: json.dumps(c) + '\n' for r, c in configs.items()}}
    # Refuse overwrites so this command cannot silently replace local credentials.
    if directory.is_symlink() or any(p.exists() or p.is_symlink() for p in files):
        raise ValueError('Expected a fresh runner credential directory')
    created = []
    try:
        for path, content in files.items():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, 'w') as stream:
                stream.write(content)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    print('Scoped runner credentials installed privately. No credentials printed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=TARGETS, action='append', required=True)
    args = parser.parse_args()
    try:
        install(args.role)
    except Exception:
        parser.exit(1, 'Runner credential configuration failed; details suppressed. Check the environment secrets.\n')
