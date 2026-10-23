"""Google responses/authentication are mocked; no credentials or Google writes."""
from dataclasses import replace
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
import httpx
import pytest
from src import automation
from src.automation import main, make_report
from src.sheets import OWNER_KEY, OWNER_VALUE, SheetTargets, SheetsClient, SheetsError, build_plan
from src.sheets_auth import AccessToken, CredentialError, credential_status, load_credentials

ID = 'test_spreadsheet_123'

@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    for key in ('GOOGLE_SERVICE_ACCOUNT_JSON', 'GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_SHEETS_SPREADSHEET_ID'):
        monkeypatch.delenv(key, raising=False)

@pytest.fixture
def plan():
    return build_plan(make_report('offline', search='DEMO-00001'))


class FakeSheets:
    def __init__(self):
        self.sheets = [{'properties': {'sheetId': 1, 'title': 'Existing Human Data'}}]
        self.cells = {1: [['do not touch']]}
        self.posts = []

    def __call__(self, request):
        assert request.headers['Authorization'] == 'Bearer mock-token'
        if request.method == 'GET':
            return httpx.Response(200, json={'sheets': self.sheets})
        body = json.loads(request.content)
        self.posts.append(body)
        for op in body['requests']:
            if 'addSheet' in op:
                props = op['addSheet']['properties']
                assert not any(s['properties']['title'] == props['title'] for s in self.sheets)
                self.sheets.append({'properties': props})
            elif 'createDeveloperMetadata' in op:
                meta = op['createDeveloperMetadata']['developerMetadata']
                sheet = next(s for s in self.sheets if s['properties']['sheetId'] == meta['location']['sheetId'])
                sheet.setdefault('developerMetadata', []).append(meta)
            elif 'updateCells' in op:
                update = op['updateCells']
                assert update['fields'] == 'userEnteredValue'
                assert set(update['range']) == {'sheetId'}
                self.cells[update['range']['sheetId']] = [[c['userEnteredValue']['stringValue'] for c in row['values']] for row in update['rows']]
        return httpx.Response(200, json={'spreadsheetId': ID, 'replies': [{} for _ in body['requests']]})


def test_atomic_idempotent_and_stale_rows(plan):
    remote = FakeSheets()
    with httpx.Client(transport=httpx.MockTransport(remote)) as http:
        client = SheetsClient(lambda: 'mock-token', http)
        assert client.sync(ID, plan)['status'] == 'synchronized'
        snapshot = remote.cells.copy()
        client.sync(ID, plan, replace_managed=True)
        assert snapshot == remote.cells
        assert len(remote.sheets) == 4
        orders = next(s for s in remote.sheets if s['properties']['title'] == 'CommerceFlow_Orders')
        assert len(remote.cells[orders['properties']['sheetId']]) == 2
        empty = build_plan(make_report('offline', search='DOES-NOT-EXIST'))
        client.sync(ID, empty, replace_managed=True)
        assert len(remote.cells[orders['properties']['sheetId']]) == 1
        assert remote.cells[1] == [['do not touch']]
    assert len(remote.posts) == 3
    assert len(remote.posts[0]['requests']) == 9


def test_refuse_unmanaged_and_require_replace(plan):
    remote = FakeSheets()
    with httpx.Client(transport=httpx.MockTransport(remote)) as http:
        client = SheetsClient(lambda: 'mock-token', http)
        client.sync(ID, plan)
        with pytest.raises(SheetsError, match='Explicitly'):
            client.sync(ID, plan)
        remote.sheets[-1]['developerMetadata'] = []
        with pytest.raises(SheetsError, match='ownership'):
            client.sync(ID, plan, replace_managed=True)
        assert len(remote.posts) == 1


def test_formula_is_explicit_text(plan):
    payload = make_report('offline')
    payload['top_products'][0]['title'] = '=IMPORTXML("bad")'
    malicious = build_plan(payload)
    remote = FakeSheets()
    with httpx.Client(transport=httpx.MockTransport(remote)) as http:
        SheetsClient(lambda: 'mock-token', http).sync(ID, malicious)
    batch = json.dumps(remote.posts)
    assert 'formulaValue' not in batch
    assert '=IMPORTXML' in batch and 'stringValue' in batch

@pytest.mark.parametrize('status', [401, 403, 404, 400])
def test_read_errors_are_sanitized(plan, status):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text='secret private key'))) as http:
        with pytest.raises(SheetsError) as exc:
            SheetsClient(lambda: 'mock-token', http, sleep=lambda _: None).sync(ID, plan)
    assert 'secret' not in str(exc.value) and 'private' not in str(exc.value)

@pytest.mark.parametrize('failure', ['429', '503', 'timeout'])
def test_bounded_read_retry(plan, failure):
    calls, delays = [], []
    def handler(request):
        calls.append(request)
        if failure == 'timeout': raise httpx.ReadTimeout('SECRET')
        return httpx.Response(int(failure), headers={'Retry-After': '0'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SheetsError): SheetsClient(lambda: 'mock-token', http, delays.append).sync(ID, plan)
    assert len(calls) == 3 and len(delays) == 2
    assert 0.5 <= delays[0] <= 0.6


def test_rate_limit_recovers(plan):
    remote = FakeSheets()
    count = [0]
    def handler(request):
        count[0] += 1
        if count[0] == 1: return httpx.Response(429, headers={'Retry-After': '1'})
        return remote(request)
    delays = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert SheetsClient(lambda: 'mock-token', http, delays.append).sync(ID, plan)['atomic']
    assert 1 <= delays[0] <= 1.1

@pytest.mark.parametrize('failure', ['timeout', '503', 'invalid-confirmation', 'rejected-batch'])
def test_write_failures_never_claim_success_or_retry_ambiguous(plan, failure):
    writes = []
    def handler(request):
        if request.method == 'GET': return httpx.Response(200, json={'sheets': []})
        writes.append(request)
        if failure == 'timeout': raise httpx.ReadTimeout('secret')
        if failure == '503': return httpx.Response(503, text='secret')
        if failure == 'rejected-batch': return httpx.Response(400, json={'error': 'invalid subrequest'})
        return httpx.Response(200, json={'spreadsheetId': ID, 'replies': []})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SheetsError): SheetsClient(lambda: 'mock-token', http).sync(ID, plan)
    assert len(writes) == 1


def test_stable_plan_and_preview(plan):
    payload = make_report('offline', search='DEMO-00001')
    payload['metadata']['generated_at'] = 'different timestamp'
    assert build_plan(payload) == plan
    assert plan.preview()['writes_performed'] is False
    assert plan.preview()['remote_checked'] is False

@pytest.mark.parametrize('targets', [SheetTargets('same', 'SAME', 'third'), SheetTargets('', 'a', 'b'), SheetTargets('bad/name', 'a', 'b')])
def test_invalid_targets(targets):
    with pytest.raises(ValueError): targets.validate()


def test_bad_id_before_network(plan):
    http = Mock()
    with pytest.raises(ValueError): SheetsClient(lambda: 'token', http).sync('https://bad', plan)
    http.request.assert_not_called()


def test_no_credentials_and_conflicting_sources():
    assert credential_status({}) == 'Not configured'
    assert 'not authenticated' in credential_status({'GOOGLE_SERVICE_ACCOUNT_JSON': 'invalid'})
    for env in ({}, {'GOOGLE_SERVICE_ACCOUNT_JSON':'x', 'GOOGLE_APPLICATION_CREDENTIALS':'y'}):
        with pytest.raises(CredentialError): load_credentials(env)


def test_protected_file_and_sanitized_errors(tmp_path, monkeypatch):
    path = tmp_path / 'credential.json'
    path.write_text('private-contents-not-for-error-messages')
    path.chmod(0o644)
    with pytest.raises(CredentialError, match='chmod'): load_credentials({'GOOGLE_APPLICATION_CREDENTIALS':str(path)})
    path.chmod(0o600)
    with pytest.raises(CredentialError) as exc:
        load_credentials({'GOOGLE_APPLICATION_CREDENTIALS':str(path)})
    assert 'private-contents' not in str(exc.value) and str(path) not in str(exc.value)


def test_load_valid_structure_mocked(monkeypatch):
    factory = Mock(return_value='mock-credentials')
    monkeypatch.setattr('src.sheets_auth.Credentials.from_service_account_info', factory)
    env = {'GOOGLE_SERVICE_ACCOUNT_JSON': json.dumps({'type':'service_account', 'token_uri':'https://oauth2.googleapis.com/token'})}
    assert load_credentials(env) == 'mock-credentials'
    assert factory.call_args.kwargs['scopes'] == ['https://www.googleapis.com/auth/spreadsheets']
    bad = {'GOOGLE_SERVICE_ACCOUNT_JSON': json.dumps({'type':'service_account','token_uri':'https://attacker.invalid'})}
    with pytest.raises(CredentialError, match='endpoint'): load_credentials(bad)


def test_auth_failure_redacted():
    from google.auth.exceptions import RefreshError
    creds = Mock(valid=False)
    creds.refresh.side_effect = RefreshError('sensitive token')
    with pytest.raises(CredentialError) as exc: AccessToken(creds)()
    assert 'sensitive' not in str(exc.value)


def test_cli_dry_run_without_streamlit(capsys, monkeypatch):
    monkeypatch.setattr(automation, 'load_credentials', Mock(side_effect=AssertionError('must not load')))
    assert main(['--sync', '--dry-run', '--status', 'paid', '--search', 'DEMO-00001']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['mode'] == 'dry-run' and not result['writes_performed']
    code = "import sys; from src.automation import main; assert 'streamlit' not in sys.modules; raise SystemExit(main(['--dry-run']))"
    completed = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)['summary']['selected_order_count'] == 240


def test_cli_missing_credentials_fails(capsys):
    assert main(['--sync', '--spreadsheet-id', ID]) == 3
    captured = capsys.readouterr()
    assert not captured.out and json.loads(captured.err)['status'] == 'failed'


def test_cli_exports_are_new_and_consistent(tmp_path, capsys):
    arguments = ['--export-dir', str(tmp_path), '--search', 'DEMO-00001']
    assert main(arguments) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['writes_performed'] and not result['remote_writes_performed']
    folder = Path(result['export_directory'])
    assert len(json.loads((folder / 'report.json').read_text())['orders']) == 1
    assert len(list(folder.iterdir())) == 3
    assert main(arguments) == 0
    other = Path(json.loads(capsys.readouterr().out)['export_directory'])
    assert other != folder and folder.exists()


def test_cli_rejects_invalid_dates_and_dry_writes(tmp_path):
    for args in (['--start','2026-09-30','--end','2026-07-01'], ['--dry-run','--export-dir',str(tmp_path)], ['--sync']):
        with pytest.raises(SystemExit) as exc: main(args)
        assert exc.value.code == 2


def test_new_integration_page_without_credentials():
    from streamlit.testing.v1 import AppTest
    from src.config import ROOT
    app = AppTest.from_file(ROOT / 'app.py').run(timeout=30)
    app.sidebar.radio[0].set_value('Google Sheets Integration').run()
    assert not app.exception
    assert any('Not configured' in m.value for m in app.markdown)
    assert len(app.json) == 1


def test_recover_after_server_committed_but_response_lost(plan):
    remote = FakeSheets()
    lose_response = [True]
    def handler(request):
        response = remote(request)
        if request.method == 'POST' and lose_response[0]:
            lose_response[0] = False
            raise httpx.ReadTimeout('connection lost after commit')
        return response
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = SheetsClient(lambda: 'mock-token', http)
        with pytest.raises(SheetsError, match='outcome unknown'):
            client.sync(ID, plan)
        snapshot = remote.cells.copy()
        assert client.sync(ID, plan, replace_managed=True)['status'] == 'synchronized'
        assert remote.cells == snapshot and len(remote.sheets) == 4


def test_post_rate_limit_retries_without_duplicates(plan):
    remote = FakeSheets()
    attempts, delays = [], []
    def handler(request):
        if request.method == 'POST':
            attempts.append(request)
            if len(attempts) == 1: return httpx.Response(429)
        return remote(request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        SheetsClient(lambda: 'mock-token', http, delays.append).sync(ID, plan)
    assert len(attempts) == 2 and len(remote.posts) == 1 and len(delays) == 1

@pytest.mark.parametrize('payload', [{}, {'sheets': [None]}, {'sheets':[{'properties':{'sheetId':1,'title':'Demo'},'developerMetadata':None}]}])
def test_malformed_metadata_never_writes(plan, payload):
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SheetsError): SheetsClient(lambda: 'mock-token', http).sync(ID, plan)
    assert calls == ['GET']


def test_cli_sync_wiring_mocked(monkeypatch, capsys):
    remote = FakeSheets()
    client = httpx.Client(transport=httpx.MockTransport(remote))
    monkeypatch.setattr(automation, 'load_credentials', lambda: object())
    monkeypatch.setattr(automation, 'AccessToken', lambda _: lambda: 'mock-token')
    monkeypatch.setattr(automation.httpx, 'Client', lambda **kwargs: client)
    assert main(['--sync', '--spreadsheet-id', ID, '--search', 'DEMO-00001']) == 0
    assert json.loads(capsys.readouterr().out)['orders'] == 1


def test_token_refresh_uses_bounded_request(monkeypatch):
    underlying = Mock()
    monkeypatch.setattr('src.sheets_auth.Request', lambda: underlying)
    credentials = Mock(valid=False, token='mock-token')
    credentials.refresh.side_effect = lambda request: request(url='https://oauth2.googleapis.com/token', method='POST', timeout=999)
    assert AccessToken(credentials)() == 'mock-token'
    assert underlying.call_args.kwargs['timeout'] == 10


def test_readback_exact_content_and_counts(plan):
    def handler(request):
        assert request.method == 'GET'
        assert len(request.url.params.get_list('ranges')) == 3
        return httpx.Response(200, json={'valueRanges': [
            {'values': [[str(v) for v in row] for row in rows]} for rows in plan.tables.values()]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = SheetsClient(lambda: 'token', http).verify(ID, plan)
    assert result['verified'] and result['order_count'] == result['unique_order_ids'] == 1
    assert result['duplicate_orders'] == 0
    assert all(w['exact_match'] for w in result['worksheets'])
    assert ID not in json.dumps(result)

@pytest.mark.parametrize('failure', ['missing', 'changed', 'extra-row'])
def test_readback_rejects_incomplete_or_wrong_cells(plan, failure):
    ranges = [{'values': [[str(v) for v in row] for row in rows]} for rows in plan.tables.values()]
    if failure == 'missing': ranges.pop()
    elif failure == 'changed': ranges[1]['values'][1][0] = 'wrong-order'
    else: ranges[1]['values'].append(ranges[1]['values'][1].copy())
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'valueRanges':ranges}))) as http:
        with pytest.raises(SheetsError): SheetsClient(lambda: 'token', http).verify(ID, plan)


def test_readback_financial_reconciliation_rejects_inconsistent_summary():
    payload = make_report('offline')
    payload['summary']['net_sales'] = '0.00'
    inconsistent = build_plan(payload)
    ranges = [{'values': [[str(v) for v in row] for row in rows]} for rows in inconsistent.tables.values()]
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'valueRanges':ranges}))) as http:
        with pytest.raises(SheetsError, match='financial reconciliation'):
            SheetsClient(lambda: 'token', http).verify(ID, inconsistent)
