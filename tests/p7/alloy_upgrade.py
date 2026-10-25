"""Disposable Alloy positions upgrade/cold rollback with the unchanged log pipeline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
PYTHON = 'python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377'
OLD = 'grafana/alloy:v1.14.1@sha256:8f5666aebb871ba43ee2d65159c5d1c26c903720efafaf2d9ed4e237afc3bc88'
NEW = 'grafana/alloy:v1.14.2@sha256:eadfe35ea52b26cbec4d4d780fbcc31edb31108c1c9e537ca59557a5a102c712'
LOKI = 'grafana/loki:2.9.17@sha256:c4a25af6f2709fa625d88ee5df494a332a85f30e9575854031667823ecc5be04'


def cleanup_owned(kind, name, project, commands):
    """Include create-success/start-failure resources; refuse foreign labels."""
    if kind not in ('container', 'volume', 'network') or not re.fullmatch(
            r'cloud-api-alloy-upgrade-[a-f0-9]{12}', project) or not name.startswith(project + '-'):
        raise ValueError('Only this disposable drill is authorized')
    argv = ['docker', kind, 'inspect', name]
    inspected = subprocess.run(argv, capture_output=True, text=True)
    commands.append({'argv': argv, 'exit_code': inspected.returncode})
    if inspected.returncode:
        # API/permission errors are not evidence that cleanup succeeded.
        return 0 if re.search(r'no such (?:container|volume|network|object)', inspected.stderr, re.I) else 1
    info = json.loads(inspected.stdout)[0]
    labels = info['Config'].get('Labels', {}) if kind == 'container' else info.get('Labels', {})
    if (labels or {}).get('florasecure.alloy-upgrade') != project:
        return 1
    argv = ['docker', kind, 'rm'] + (['--force'] if kind == 'container' else []) + [name]
    removed = subprocess.run(argv, capture_output=True)
    commands.append({'argv': argv, 'exit_code': removed.returncode})
    return removed.returncode


def execute(output):
    project = 'cloud-api-alloy-upgrade-' + uuid.uuid4().hex[:12]
    network, collector, store = [project + suffix for suffix in ['-net', '-alloy', '-loki']]
    positions, cold, data = [project + suffix for suffix in ['-positions', '-cold', '-data']]
    label = ['--label', 'florasecure.alloy-upgrade=' + project]
    evidence = {'project': project, 'status': 'FAIL', 'commands': [], 'stages': [],
                'production_data_used': False, 'old_image': OLD, 'new_image': NEW}
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def run(argv):
        p = subprocess.run(argv, capture_output=True, text=True)
        evidence['commands'].append({'argv': argv, 'exit_code': p.returncode})
        if p.returncode:
            raise RuntimeError('Disposable command failed: ' + str(p.returncode))
        return p.stdout

    def http(container, port, path):
        code = "import urllib.request; c=urllib.request.build_opener(urllib.request.ProxyHandler({})); print(c.open('http://127.0.0.1:" + str(port) + path + "',timeout=5).read().decode())"
        return run(['docker', 'run', '--rm', '--network', 'container:' + container,
                    '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                    '--entrypoint', 'python', PYTHON, '-c', code])

    def ready(container, port, path):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                http(container, port, path)
                return
            except RuntimeError:
                time.sleep(1)
        raise AssertionError('Disposable service readiness timed out')

    def lines_read():
        metrics = http(collector, 12345, '/metrics')
        values = re.findall(r'^loki_source_file_read_lines_total\{[^\n]*\}\s+([0-9.eE+]+)$', metrics, re.M)
        assert values, 'Actual file-read counter is required; no inferred positions PASS'
        return sum(float(v) for v in values)

    def query(marker):
        params = urllib.parse.urlencode({'query': '{project="' + project + '",service="backend"} | json | marker="' + marker + '"',
                                         'start': str(time.time_ns() - 3600 * 10**9), 'end': str(time.time_ns() + 10**9)})
        result = json.loads(http(store, 3100, '/loki/api/v1/query_range?' + params))
        return sum(len(s['values']) for s in result['data']['result'])

    def ingested(marker):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if query(marker) == 1:
                return
            time.sleep(1)
        raise AssertionError('Real file-to-Loki event not ingested exactly once')

    def stop_collector():
        run(['docker', 'stop', '--time', '40', collector])
        run(['docker', 'rm', collector])

    try:
        for image in [OLD, NEW, LOKI, PYTHON]:
            i = json.loads(run(['docker', 'image', 'inspect', image]))[0]
            assert i['Os'] == 'linux' and i['Architecture'] == 'amd64'
        run(['docker', 'network', 'create', '--internal', *label, network])
        for volume in [positions, cold, data]:
            run(['docker', 'volume', 'create', *label, volume])
        with tempfile.TemporaryDirectory(prefix=project + '-') as directory:
            logs = Path(directory) / 'logs'
            (logs / 'fixture').mkdir(parents=True)
            logs.chmod(0o755)
            (logs / 'fixture').chmod(0o755)
            logfile = logs / 'fixture/fixture-json.log'
            logfile.touch(mode=0o644)

            def append(marker):
                record = {'log': json.dumps({'service': 'backend', 'event_type': 'image_upgrade', 'marker': marker}) + '\n',
                          'time': datetime.now(timezone.utc).isoformat(),
                          'attrs': {'com.docker.compose.project': project, 'com.docker.compose.service': 'backend'}}
                with logfile.open('a') as stream:
                    stream.write(json.dumps(record) + '\n')

            run(['docker', 'run', '-d', '--name', store, *label, '--network', network,
                 '--network-alias', 'loki', '--mount', 'type=volume,source=' + data + ',target=/loki',
                 '--mount', 'type=bind,source=' + str(ROOT / 'monitoring/loki/p6-loki.yml') + ',target=/etc/loki/p6.yml,readonly',
                 '-e', 'HTTP_PROXY=', '-e', 'HTTPS_PROXY=', '-e', 'NO_PROXY=*', LOKI, '-config.file=/etc/loki/p6.yml'])
            ready(store, 3100, '/ready')

            def start(image, volume):
                run(['docker', 'run', '-d', '--name', collector, *label, '--network', network,
                     '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp',
                     '--mount', 'type=volume,source=' + volume + ',target=/var/lib/alloy,volume-nocopy',
                     '--mount', 'type=bind,source=' + str(logs) + ',target=/var/log/project,readonly',
                     '--mount', 'type=bind,source=' + str(ROOT / 'monitoring/alloy/config.alloy') + ',target=/etc/alloy/config.alloy,readonly',
                     '-e', 'LOG_PROJECT=' + project, image, 'run', '--server.http.listen-addr=0.0.0.0:12345',
                     '--storage.path=/var/lib/alloy', '/etc/alloy/config.alloy'])
                ready(collector, 12345, '/-/ready')
                info = json.loads(run(['docker', 'inspect', collector]))[0]
                assert not info['HostConfig'].get('PortBindings')
                assert info['HostConfig']['ReadonlyRootfs'] and info['HostConfig']['CapDrop'] == ['ALL']
                evidence['stages'].append({'image_id': info['Image'], 'positions_volume': volume})

            append('before')
            start(OLD, positions)
            ingested('before')
            assert lines_read() == 1
            stop_collector()
            copy = "import os,shutil,pathlib; s=pathlib.Path('/source'); d=pathlib.Path('/copy'); shutil.copytree(s,d,dirs_exist_ok=True); [(os.chown(d/p.relative_to(s),p.stat().st_uid,p.stat().st_gid)) for p in [s,*s.rglob('*')]]"
            run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python',
                 '--mount', 'type=volume,source=' + positions + ',target=/source,readonly',
                 '--mount', 'type=volume,source=' + cold + ',target=/copy', PYTHON, '-c', copy])
            start(NEW, positions)
            append('after')
            ingested('after')
            assert query('before') == 1 and lines_read() == 1, 'New collector reread already-positioned input'
            stop_collector()
            start(NEW, positions)
            append('restarted')
            ingested('restarted')
            assert lines_read() == 1, 'Restart reread already-positioned input'
            stop_collector()
            start(OLD, cold)
            append('rollback')
            ingested('rollback')
            # The read counter prevents Loki dedup from concealing replay.
            assert lines_read() == 3
            assert all(query(m) == 1 for m in ['before', 'after', 'restarted', 'rollback'])
            evidence.update(status='PASS', cold_positions_rollback=True,
                            real_ingestion=True, old_input_not_replayed=True,
                            new_version_restart_preserves_positions=True,
                            counter_checks=[1, 1, 1, 3], reverse_binary_on_upgraded_positions=False)
    except Exception as error:
        evidence.update(error_type=type(error).__name__, error=str(error))
    finally:
        cleanup = []
        for kind, names in [('container', [collector, store]), ('volume', [data, cold, positions]),
                            ('network', [network])]:
            for name in names:
                cleanup.append(cleanup_owned(kind, name, project, evidence['commands']))
        evidence['cleanup_exit_codes'] = cleanup
        if any(cleanup):
            evidence['status'] = 'FAIL'
        (output / (project + '.json')).write_text(json.dumps(evidence, indent=2))
    print(json.dumps({'project': project, 'status': evidence['status']}))
    return evidence['status'] == 'PASS'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'tests/p7/artifacts/alloy-upgrades')
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.output) else 1)
