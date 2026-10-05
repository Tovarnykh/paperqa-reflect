"""Offline evidence routing audit; no model, API, index or source mutation."""
import asyncio
import collections
import hashlib
import json
from pathlib import Path

from paperqa.settings import Settings
from paperqa.types import Context

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'research/paperqa-loop'
BASE = REPO / 'results/loop-stage-c/20261004T210539Z-3f1ab1/assessment-v1'


def read(p):
    return json.loads(p.read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


async def main():
    stats = read(REPO / 'results/reports/2026-10-05-loop-evidence-stage-c.json')
    records, sessions = [], {}
    for row in stats['rows']:
        if row['status'] != 'success':
            continue
        run = REPO / 'results/runs' / row['run_id']
        qdir = run / row['question_id']
        settings = Settings.model_validate(read(run / 'settings.json'))
        assert settings.prompts.pre is None
        pending, generations = None, []
        events = [json.loads(x) for x in (qdir / 'events.jsonl').read_text().splitlines()]
        for event in events:
            if event['kind'] == 'action':
                pending = [x['function']['name'] for x in event['value']['tool_calls']]
            if event['kind'] == 'step':
                if 'gen_answer' in pending:
                    p = qdir / event['value']['state_path']
                    assert sha(p.read_bytes()) == event['value']['state_sha256']
                    state = read(p)
                    contexts = [Context.model_validate(c) for c in state['contexts']]
                    rebuilt = await settings.context_serializer(contexts, state['question'], None)
                    assert rebuilt == state['context'], row['run_id']
                    ordered = sorted(contexts, key=lambda c: (-c.score, c.text.name))
                    shown = [c for c in ordered[:settings.answer.answer_max_sources]
                             if c.score >= settings.answer.evidence_relevance_score_cutoff]
                    chunks = [(str(c.text.doc.dockey), c.text.name, sha(c.text.text.encode())) for c in shown]
                    generations.append({'state_path': event['value']['state_path'], 'context_sha256': sha(rebuilt.encode()),
                        'pool': len(contexts), 'selected': len(shown), 'unique_selected_chunks': len(set(chunks)),
                        'selected_ids': [c.id for c in shown], 'excluded_ids': [c.id for c in ordered if c not in shown]})
                    sessions[row['question_id'], row['seed'], 'N'+str(row['n'])] = (row, state, shown)
                pending = None
        assert generations
        final = read(qdir / 'response.json')['session']
        assert final['context'] == state['context'] and final['raw_answer'] == state['raw_answer']
        records.append({'run_id': row['run_id'], 'question_id': row['question_id'], 'seed': row['seed'],
                        'n': row['n'], 'generations': generations})
    judge_dir = BASE / 'stage-c-allocation-v1/manual-continuation-v1/combined-assessment'
    mapping = {x['case_id']: x for x in read(judge_dir / 'mapping.json')}
    pairs = {p['pair_id']: p for p in read(BASE / 'audit.json')['pair_audit']}
    traces, raw_categories = [], collections.Counter()
    for file in sorted(judge_dir.glob('*.result.json')):
        verdict = read(file); m = mapping[verdict['case_id']]; p = pairs[m['pair_id']]
        for issue in verdict['verdict']['issues']:
            arm = m['slots'][issue['answer']]
            row, state, selected = sessions[p['question_id'], p['seed'], arm]
            raw_categories[issue['category']] += 1
            original = [c for c in state['contexts'] if c['id'] == issue['source_id']]
            traces.append({'run_id': row['run_id'], 'question_id': row['question_id'], 'seed': row['seed'],
                           'arm': arm, 'judge_file': file.name, 'pair_id': p['pair_id'], **issue,
                           'issue_source_in_this_run': bool(original),
                           'issue_source_selected': any(c.id == issue['source_id'] for c in selected),
                           'source_quote_in_run_original': any(issue['source_quote'] in c['text']['text'] for c in original),
                           'source_summaries': [{'id': c['id'], 'score': c['score'], 'summary': c['context'],
                                                'original': c['text']['text']} for c in original],
                           'selected_summaries': [{'id': c.id, 'summary': c.context} for c in selected]})
    out = {'kind': 'offline-evidence-routing-audit-v1', 'successful_runs': len(records),
           'answer_contexts_replayed': sum(len(r['generations']) for r in records),
           'runs_with_duplicate_chunks_in_final_top5': sum(r['generations'][-1]['unique_selected_chunks'] < r['generations'][-1]['selected'] for r in records),
           'runs_with_excluded_contexts': sum(bool(r['generations'][-1]['excluded_ids']) for r in records),
           'raw_judge_issue_records': len(traces), 'raw_issue_categories': dict(raw_categories),
           'caution': 'Mirrored orders and N8 in two contrasts duplicate judgments. Counts are not independent error rates. Summary meaning requires manual source review.',
           'rows': records, 'script_sha256': sha(Path(__file__).read_bytes()), 'model_calls': 0}
    (ROOT / '.tmp/evidence-routing-audit.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    (ROOT / '.tmp/evidence-routing-private-traces.json').write_text(json.dumps(traces, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k != 'rows'}))


if __name__ == '__main__':
    asyncio.run(main())
