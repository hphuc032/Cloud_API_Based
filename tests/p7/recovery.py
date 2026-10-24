"""Quiesced paired backups -> fresh lab PostgreSQL instances -> recovered APIs.

Only random cloud-api-p7-* projects; no credentials/dumps written to disk or
evidence. Source volumes remain intact. This is a lab drill, never production.
"""
import hashlib
import json
import time
from datetime import datetime, timezone


def execute(run, compose, project, artifacts):
    if not project.startswith('cloud-api-p7-') or len(project) != len('cloud-api-p7-') + 12:
        raise ValueError('Only an isolated P7 project is authorized')
    overlay = artifacts / 'recovery-compose.json'
    source = json.loads(run(compose + ['config', '--format', 'json'], capture_output=True, text=True).stdout)
    image = source['services']['postgres']['image']
    services = {}
    for suffix in ('app', 'identity'):
        services['recovery-' + suffix] = {
            'image': image, 'pull_policy': 'never', 'profiles': ['p7-recovery'],
            'environment': {'POSTGRES_PASSWORD_FILE': '/run/secrets/postgres_password'},
            'secrets': ['postgres_password'], 'networks': ['p7_recovery'],
            'volumes': ['p7_recovery_' + suffix + ':/var/lib/postgresql/data'],
            'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U postgres'], 'interval': '2s', 'timeout': '2s', 'retries': 40},
            'logging': {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '2'}},
        }
    overlay.write_text(json.dumps({'services': services,
        'networks': {'p7_recovery': {'internal': True}},
        'volumes': {'p7_recovery_app': {}, 'p7_recovery_identity': {}}}, indent=2))
    compose += ['-f', str(overlay)]
    evidence = {'started_utc': datetime.now(timezone.utc).isoformat(), 'project': project,
                'status': 'FAIL', 'quiesced_services': ['backend', 'keycloak'],
                'secret_recovery': 'In-memory role verifier stream, disposable lab only; no private exports persisted',
                'backups': [], 'production_executed': False}
    attached = []
    switched = False

    def output(service, args, **kwargs):
        return run(compose + ['exec', '-T', service, *args], capture_output=True, **kwargs).stdout

    def sql(service, database, statement):
        return output(service, ['psql', '-X', '-U', 'postgres', '-d', database, '-At', '-v', 'ON_ERROR_STOP=1', '-c', statement], text=True).strip()

    def snapshot(service, database):
        tables = sql(service, database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
        result = {}
        for table in tables:
            if not table.replace('_', '').isalnum():
                raise ValueError('Unexpected lab table identifier')
            result[table] = sql(service, database,
                'SELECT count(*)::text || chr(58) || md5(coalesce(string_agg(row_to_json(t)::text, chr(10) ORDER BY row_to_json(t)::text),\'\')) FROM public."' + table + '" t')
        result['constraints'] = sql(service, database, "SELECT md5(string_agg(conname || pg_get_constraintdef(oid), chr(10) ORDER BY conname, pg_get_constraintdef(oid))) FROM pg_constraint WHERE connamespace='public'::regnamespace")
        result['table_owners'] = sql(service, database, "SELECT md5(string_agg(tablename||tableowner, chr(10) ORDER BY tablename)) FROM pg_tables WHERE schemaname='public'")
        return result

    def ready():
        run(compose + ['up', '--no-deps', '-d', '--wait', '--wait-timeout', '180', 'keycloak', 'backend'])
        # Identity edge can retain the old upstream peer until its normal DNS refresh.
        run(compose + ['restart', 'identity-edge'])
        run(compose + ['up', '--no-deps', '-d', '--wait', '--wait-timeout', '90', 'identity-edge'])

    try:
        run(compose + ['up', '--no-deps', '-d', '--wait', '--wait-timeout', '120', 'recovery-app', 'recovery-identity'])
        run(compose + ['stop', 'backend', 'keycloak'])
        evidence['quiesced_utc'] = datetime.now(timezone.utc).isoformat()
        for origin, target, database in [('postgres', 'recovery-app', 'p0_baseline'), ('identity-db', 'recovery-identity', 'keycloak')]:
            before = snapshot(origin, database)
            roles = output(origin, ['pg_dumpall', '-U', 'postgres', '--roles-only'])
            # Fresh PostgreSQL already owns its bootstrap postgres role. Preserve
            # its ALTER ROLE statements and all other attributes/verifiers.
            roles = roles.replace(b'CREATE ROLE postgres;\n', b'')
            output(target, ['psql', '-X', '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1'], input=roles)
            dump = output(origin, ['pg_dump', '-U', 'postgres', '-d', database, '-Fc', '--create'])
            output(target, ['pg_restore', '-U', 'postgres', '-d', 'postgres', '--create', '--exit-on-error'], input=dump)
            after = snapshot(target, database)
            assert before == after, 'Recovered rows/schema differ: ' + database
            if database == 'p0_baseline':
                assert sql(target, database, 'SELECT count(*) FROM orders o JOIN users u ON u.id=o.user_id JOIN external_identities e ON e.user_id=u.id') == '2'
                assert sql(target, database, "SELECT has_table_privilege('app_runtime','external_identities','SELECT'),has_table_privilege('app_runtime','external_identities','INSERT'),has_table_privilege('app_runtime','audit_logs','INSERT'),has_table_privilege('app_runtime','audit_logs','SELECT'),has_schema_privilege('app_runtime','public','CREATE')") == 't|f|t|f|f'
            evidence['backups'].append({'database': database, 'archive_bytes': len(dump),
                'tables': before, 'restored_rows_constraints_owners_equal': True,
                'role_verifiers_exported_to_evidence': False})
            del dump, roles
        # Isolated original writers now exercise the recovered instances using
        # the same private DNS aliases, CA trust, secrets and application policy.
        run(compose + ['stop', 'postgres', 'identity-db'])
        switched = True
        for target, network, alias in [('recovery-app', 'app_data', 'postgres'), ('recovery-identity', 'identity_data', 'identity-db')]:
            cid = run(compose + ['ps', '-q', target], capture_output=True, text=True).stdout.strip()
            run(['docker', 'network', 'connect', '--alias', alias, project + '_' + network, cid])
            attached.append((project + '_' + network, cid))
        ready()
        run(compose + ['run', '--rm', '--no-deps', '-T', 'tests', 'python', '/tests/p7/verify_recovered.py'])
        evidence['recovered_api_chain'] = 'PASS'
        # Force recreation also demonstrates data survives container replacement.
        run(compose + ['up', '--no-deps', '-d', '--force-recreate', '--wait', '--wait-timeout', '180', 'backend'])
        run(compose + ['run', '--rm', '--no-deps', '-T', 'tests', 'python', '/tests/p7/verify_recovered.py'])
        evidence['backend_container_recreation'] = 'PASS'
        evidence['status'] = 'PASS'
    except Exception as exc:
        evidence['error_type'] = type(exc).__name__
        # Never include subprocess output potentially containing database data.
        print('P7 recovery failed: ' + type(exc).__name__, flush=True)
    finally:
        try:
            if switched:
                run(compose + ['stop', 'backend', 'keycloak'])
            for network, cid in reversed(attached):
                run(['docker', 'network', 'disconnect', network, cid])
            if switched:
                run(compose + ['up', '--no-deps', '-d', '--wait', '--wait-timeout', '120', 'postgres', 'identity-db'])
            ready()
            run(compose + ['run', '--rm', '--no-deps', '-T', 'tests', 'python', '/tests/p7/verify_recovered.py'])
            evidence['return_to_original_databases'] = 'PASS'
        except Exception as exc:
            evidence['status'] = 'FAIL'
            evidence['return_error_type'] = type(exc).__name__
        # Release only this drill's fresh instance filesystems on vfs hosts.
        clean = run(compose + ['rm', '--stop', '--force', 'recovery-app', 'recovery-identity'], check=False)
        evidence['fresh_instance_cleanup_exit'] = clean.returncode
        if clean.returncode:
            evidence['status'] = 'FAIL'
        evidence['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (artifacts / 'p7-recovery.json').write_text(json.dumps(evidence, indent=2))
    return evidence['status'] == 'PASS'
