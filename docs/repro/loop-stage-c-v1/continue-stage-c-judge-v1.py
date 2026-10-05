"""User-authorized seven-request continuation after the inspected HTTP429 stop.

Original files remain immutable. The unresolved old reservation stays charged
conservatively, under a reviewed hold state; no assumption of zero billing.
"""
import argparse
import collections
import importlib.util
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / ".tmp/run-loop-stage-c-judge.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
judge, pairwise, adapter = runner.judge, runner.pairwise, runner.adapter
BASE = adapter.LOOP_ROOT / "results/loop-stage-c/20261004T210539Z-3f1ab1/assessment-v1/stage-c-allocation-v1"
ORIGINAL = BASE / "plans/20261005T103734Z-00aaee"
CONT = BASE / "manual-continuation-v1"
DEST = CONT / "plan"
HOLD_ID = "b55f529ef5d54a0783fd5a2d5e0f8354"


def hashes(directory):
    return {str(p.relative_to(directory)).replace('\\', '/'): judge.digest(p.read_bytes())
            for p in sorted(directory.rglob('*')) if p.is_file()}


def validate_original():
    freeze = adapter.read(adapter.LOOP_ROOT / "docs/loop-stage-b-evaluator-freeze.json")
    frozen = adapter.verify_evaluator(freeze)
    plan, config, requests = pairwise.load_plan(ORIGINAL)
    assert config == {**frozen, "budget_group": "loop-stage-c-pairwise-v1"}
    state = adapter.read(ORIGINAL / "run.json")
    assert state['status'] == 'failed' and state['error']['code'] == 'http_429'
    checked, missing = [], []
    for row in plan['rows']:
        cid = row['anonymous_id']
        path = ORIGINAL / f'{cid}.result.json'
        if path.exists():
            result = adapter.read(path)
            if result['status'] == 'checked':
                verdict = pairwise.parse_response(adapter.read(ORIGINAL / f'{cid}.response.json'), requests[cid], config)
                verdict['case_id'] = row['case_id']
                assert verdict == result['verdict']
                checked.append(cid)
                continue
            assert cid == 'item-054' and result['error']['code'] == 'http_429'
            assert result['ledger_call_id'] == HOLD_ID and result['verdict'] is None
        assert not (ORIGINAL / f'{cid}.response.json').exists()
        missing.append(row)
    assert checked == [f'item-{i:03d}' for i in range(1, 54)]
    assert [r['anonymous_id'] for r in missing] == [f'item-{i:03d}' for i in range(54, 61)]
    return plan, config, requests, missing


def prepare():
    plan, config, requests, missing = validate_original()
    CONT.mkdir(exist_ok=False)
    DEST.mkdir()
    for name in ['config.json', 'prompt.txt', 'mapping.json']:
        shutil.copyfile(ORIGINAL / name, DEST / name)
    assert plan['expected_sha256'] is None
    new = {**plan, 'id': plan['id'] + '-manual-continuation-v1', 'cases': 7, 'rows': missing}
    judge.write_json(DEST / 'plan.json', new)
    for row in missing:
        name = row['anonymous_id'] + '.request.json'
        shutil.copyfile(ORIGINAL / name, DEST / name)
    _, new_config, new_requests = pairwise.load_plan(DEST)
    assert new_config == config and new_requests == {r['anonymous_id']: requests[r['anonymous_id']] for r in missing}
    record = {'kind': 'stage-c-manual-seven-request-continuation-v1',
              'created_utc': datetime.now(UTC).isoformat(),
              'authorization': 'User reports credit top-up and explicitly requests completion of these seven assessments.',
              'preserved_successful_assessments': 53, 'remaining_requests': list(new_requests),
              'retry_policy': 'One explicitly authorized retry of HTTP429 item-054; six previously unstarted calls. No automatic retry.',
              'original_file_hashes': hashes(ORIGINAL), 'continuation_input_hashes': hashes(DEST),
              'config_request_and_mapping_unchanged': True,
              'old_reservation': {'id': HOLD_ID, 'held_micro_usd': 71925,
                                  'policy': 'Retain charged maximum; transition reserved to held_http429 after manual inspection. This is not confirmed billing.'},
              'helper_sha256': judge.digest(Path(__file__).read_bytes())}
    judge.write_json(CONT / 'amendment.json', record)
    print(json.dumps({'prepared': str(DEST), 'requests': 7, 'preserved': 53}))


def run():
    validate_original()
    amendment = adapter.read(CONT / 'amendment.json')
    assert hashes(ORIGINAL) == amendment['original_file_hashes']
    assert hashes(DEST) == amendment['continuation_input_hashes'], 'Continuation already attempted or altered'
    assert judge.digest(Path(__file__).read_bytes()) == amendment['helper_sha256']
    plan, config, requests = pairwise.load_plan(DEST)
    # Reserve transition is recorded in a separate journal, with the whole ledger
    # backed up first. Keep the unknown old cost inside both budget totals.
    backup = CONT / 'ledger-before-continuation.sqlite3'
    assert not backup.exists()
    with sqlite3.connect(judge.DEFAULT_LEDGER) as db:
        with sqlite3.connect(backup) as copy:
            db.backup(copy)
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute("SELECT id,plan_id,group_id,request_hash,reserved,charged,state FROM calls WHERE state IN ('reserved','overrun')").fetchall()
        expected = (HOLD_ID, '20261005T103734Z-00aaee', config['budget_group'],
                    '021007acf678ad15228ee87b5503b0de422c8cecd35ea553be74252b553724c0', 71925, 71925, 'reserved')
        assert rows == [expected]
        db.execute("UPDATE calls SET state='held_http429' WHERE id=? AND state='reserved'", (HOLD_ID,))
        db.commit()
    judge.write_json(CONT / 'ledger-review.json', {'old_row': expected, 'new_state': 'held_http429',
                      'charged_unchanged': True, 'backup_sha256': judge.digest(backup.read_bytes())})
    key = judge.api_key(adapter.CITATION_ROOT / '.env')
    counts, cache = {}, {}
    with httpx.Client(timeout=config['timeout_seconds'], trust_env=False, follow_redirects=False) as client:
        for cid, request in requests.items():
            body = judge.token_count_body(request)
            count = judge.response_json(client, 'POST', '/responses/input_tokens', key, body).get('input_tokens')
            assert type(count) is int and 0 < count <= config['max_input_tokens']
            counts[cid] = count
            cache[json.dumps(body, sort_keys=True, ensure_ascii=False)] = count
        remaining = runner.headroom(judge.DEFAULT_LEDGER, config)
        reservation = runner.prior.guard_budget(counts, config, remaining)
        preflight = {'checked_utc': datetime.now(UTC).isoformat(), 'counts': counts, 'remaining': remaining,
                     'maximum_usd': judge.usd(reservation), 'old_http429_hold_retained_usd': '0.071925'}
        judge.write_json(CONT / 'preflight.json', preflight)
        print('PREFLIGHT', json.dumps(preflight), flush=True)
        state = judge.run_plan(DEST, adapter.CITATION_ROOT / '.env', judge.DEFAULT_LEDGER,
                               client=runner.prior.CountCacheClient(client, cache), recipe=pairwise)
        print('RUN', json.dumps(state), flush=True)
    assert hashes(ORIGINAL) == amendment['original_file_hashes']


def assess():
    amendment = adapter.read(CONT / 'amendment.json')
    assert hashes(ORIGINAL) == amendment['original_file_hashes']
    assert adapter.read(DEST / 'run.json')['status'] == 'completed'
    plan, config, requests = pairwise.load_plan(ORIGINAL)
    merged = CONT / 'combined-assessment'
    merged.mkdir(exist_ok=False)
    for name in ['config.json', 'prompt.txt', 'mapping.json']:
        shutil.copyfile(ORIGINAL / name, merged / name)
    judge.write_json(merged / 'plan.json', {**plan, 'id': plan['id'] + '-combined-assessment-only'})
    origins = {}
    for row in plan['rows']:
        cid = row['anonymous_id']
        source = DEST if cid in amendment['remaining_requests'] else ORIGINAL
        result = adapter.read(source / f'{cid}.result.json')
        assert result['status'] == 'checked'
        verdict = pairwise.parse_response(adapter.read(source / f'{cid}.response.json'), requests[cid], config)
        verdict['case_id'] = row['case_id']
        assert verdict == result['verdict']
        shutil.copyfile(ORIGINAL / f'{cid}.request.json', merged / f'{cid}.request.json')
        shutil.copyfile(source / f'{cid}.result.json', merged / f'{cid}.result.json')
        origins[cid] = {'source_plan': str(source.relative_to(BASE)), 'result_sha256': judge.digest((source / f'{cid}.result.json').read_bytes())}
    report = pairwise.assess(merged)
    assert report['checked'] == 60 and len(report['pairs']) == 30
    by_contrast = {}
    for comparator in ['N1', 'N3']:
        by_contrast[f'N8/{comparator}'] = dict(collections.Counter(p['outcome'] for p in report['pairs'] if p['pair_id'].endswith(f'-N8-{comparator}')))
    report['by_contrast'] = by_contrast
    judge.write_json(merged / 'assessment.json', report)
    judge.write_json(merged / 'provenance.json', {'assessment_only_never_execute': True, 'origins': origins,
                     'original_unchanged': True, 'amendment_sha256': judge.digest((CONT / 'amendment.json').read_bytes())})
    judge.write_json(merged / 'run.json', {'status': 'assessment_only_do_not_execute', 'requests_sent': 0})
    print('ASSESSMENT', json.dumps({k: v for k, v in report.items() if k != 'pairs'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'assess'])
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'assess': assess}[args.command]()
