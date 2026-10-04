# Stage C: inspected continuation after Coder autostop

This is a manual recovery amendment after inspecting a real infrastructure stop,
not an automatic retry or a replacement of an unfavorable model result. The
original Stage C protocol, plan, progress files, model configs and results remain
unchanged. It continues the user's authorized N1/N3/N8 comparison.

## Incident and preserved outcomes

Original group: `20261004T210539Z-3f1ab1`, clean source
`ad5b60ced2ae4b695c7f7119ddc7e49e5d0b5379`. It launched4October21:05:39UTC.
Coder recorded reason `autostop`, transition `stop`, at22:07:38UTC (5October00:07
Europe/Oslo), completed22:07:55UTC. Detached execution did not survive stopping
the workspace. It was restarted for inspection at22:09UTC; the new recorded
deadline is7October22:09UTC (8October00:09Europe/Oslo). Schedule settings were
not changed and no artificial activity/keepalive loop is installed.

Nine attempts were recorded before interruption: jobs1-9, three complete
question/seed blocks. Eight returned correct answers. Job1 (N1) returned a
structured `fail` caused by Ollama timing out while starting llama-server;
it produced no controller action. Preserve it as an execution failure, not a
wrong answer or a reasoning-quality error. It is not retried.

Job10 (N1, COSA-1, seed42) was interrupted during evidence gathering. Its partial
run `20261004T220455Z-c76620` has events/requests but no final response or grade.
It remains an infrastructure-interrupted attempt and is not rerun. Jobs11-48
were never started. The saved `running` label is stale: original PID1904071 no
longer exists, no experiment process is active, and the stale lock remains.

## Explicit continuation

The new launcher executes only the original schedule's38 never-started jobs,
in their original order. It verifies the hashed inspection manifest, original
plan/current/progress and START/FINISHED records, the completed prefix and the
absence of a final response/grade for interrupted job10. A possibly completed
or additionally started job requires further inspection and must not be replayed.

All original measured source/config/input/package/model hashes must remain
unchanged. The only new tracked files are recovery launcher/tests/protocol and
README documentation. The continuation freezes its new clean Git head and
original source hashes. It reuses the unchanged Stage C execution functions,
unloading models and building a fresh index before each attempt. The same
16384/4096 context/output limits, timeouts, prompts and answer cap5 remain.

Dry planning does not remove locks or launch anything. Explicit `--run` creates
a separate one-use claim and continuation plan/progress/logs. Before replacing
the stale shared lock, verify that its exact recorded PID is absent and no other
experiment is running, then archive the original lock bytes. Preserve the
original execution claim, plan, progress and raw runs byte-for-byte. The new
continuation uses the same shared execution lock. Stop on another structural
failure; no automatic resume, retries, substituted seeds or schedule expansion.

Archive the original progress and all ten existing full/partial runs before
launching this continuation. Record archive/file hashes and the restart boundary
in the parent wiki. Start the same installed Ollama0.35.0 service on11436 if it
is absent; retain previous service logs. No model request is used to warm up or
replace a failed attempt before the scheduled execution.

## Reporting and interpretation

If all38 remaining jobs finish, report47 recorded completed attempts plus one
infrastructure-interrupted attempt out of48 scheduled, including the preserved
job1 failure. Never call that48 successful completions. Keep the initial segment
and continuation segment identifiable; reboot/service restart can affect timing.

Compare N8/N1 and N8/N3 on matched available question/seed pairs. Missing cells
are explicitly unavailable, not incorrect answers, zero time or invented judge
preferences. Show per-arm denominators, startup failure and interruption counts
separately. Do not fill gaps with Stage B or pool repeated questions as independent
observations. The original all-complete bootstrap recipe cannot be applied
silently to a dataset with missing cells; disclose any appropriate restricted
descriptive analysis and its smaller sample before claiming a result.

The external judge remains unchanged and subject to its original maximum64
judgments plus actual availability, token reservation and ledger limits. This
recovery performs no paid evaluation. No citation mechanism, holdout, answer
selection change or extra N setting is added.
