#!/usr/bin/env python3
"""Markdown tables for results/proposal_v2/REPORT.md from <run>/pv2_summary.json (run analyze_pv2.py first).

Usage: tables.py <run_dir> [<run_dir> ...]
Prints (1) a run table and (2) a proposal-outcome table (one row per injection run; columns = outcome counters).
"""
import sys, json, os

OUTCOMES = ['received', 'drop_not_found', 'drop_redirect_cap', 'drop_no_live_ancestor', 'drop_self', 'drop_queue_cap',
            'drop_dup_in_queue', 'drop_dup_with_dbow2', 'not_evaluated', 'bad_at_eval', 'abort_near', 'bow_fail',
            'sim3_fail', 'geom_pass_not_best', 'geom_pass_best', 'unconfirmed_loop', 'unconfirmed_merge',
            'unconfirmed_replaced_loop', 'unconfirmed_replaced_merge', 'accepted_loop', 'accepted_merge',
            'pending_loop', 'pending_merge', 'queued']
LEVEL1 = ['drop_not_found', 'drop_redirect_cap', 'drop_no_live_ancestor', 'drop_self', 'drop_queue_cap',
          'drop_dup_in_queue', 'drop_dup_with_dbow2', 'not_evaluated', 'bad_at_eval', 'abort_near', 'bow_fail',
          'sim3_fail', 'geom_pass_not_best', 'geom_pass_best', 'queued']
ANNOT = ['redirected', 'redirect_hops', 'to_loop_list', 'to_merge_list']


def load(run):
    return json.load(open(os.path.join(run, 'pv2_summary.json')))


runs = [load(r) for r in sys.argv[1:]]
print('| run | arm | exit | traj saved | maps created | merges | loops | accepted (list/src) | live maps: KFs per session | ATE Sim3 per live map (m) | Mono drop % |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for d in runs:
    name = d['run']
    arm = d['meta']['mode']
    base = name[: -len(arm) - 1] if name.endswith('_' + arm) else name
    c = d['counts_log']
    acc = ', '.join(f"{a['list']}/{a['src']}" for a in d['accepted']) or '—'
    lm = d['live_maps']
    kps = '; '.join('/'.join(map(str, m.get('kfs_per_session', [m['kfs']]))) for m in lm) or '—'
    ate = '; '.join('—' if m.get('ate_sim3_m') is None else f"{m['ate_sim3_m']:.3f}" for m in lm) or '—'
    traj = 'yes' if d.get('traj_kfs_final_map') else 'no'
    print(f"| {base} | {arm} | {d['meta']['mono_exit']} | {traj} | {c['new_map']} | {c['merge']} | {c['loop_detected']} | {acc} | {kps} | {ate} | {d.get('mono_drop_pct', '—')} |")
print()
inj = [d for d in runs if d['meta']['mode'] == 'resnet18']
if inj:
    cols = [k for k in OUTCOMES if any(d['prop'].get(k) for d in inj)]
    ann = [k for k in ANNOT if any(d['prop'].get(k) for d in inj)]
    print('| run | ' + ' | '.join(cols) + ' | sum of level-1 outcomes (= received?) | ' + ' | '.join(ann) + ' | counters from |')
    print('|---|' + '---|' * (len(cols) + 1 + len(ann)) + '---|')
    for d in inj:
        p = d['prop']
        # level 1: every received proposal ends in exactly one of these (geom_pass_* included; queued = still waiting).
        # level 2 (accepted_* / unconfirmed_* / pending_*) is what then happened to a geom_pass_best, not summed.
        term = sum(p.get(k, 0) for k in LEVEL1)
        print(f"| {d['run']} | " + ' | '.join(str(p.get(k, 0)) for k in cols) + f" | {term} | " +
              ' | '.join(str(p.get(k, 0)) for k in ann) + f" | {d['prop_src']} |")
