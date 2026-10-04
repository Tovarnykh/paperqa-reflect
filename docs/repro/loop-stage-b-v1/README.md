# Stage B exact analysis supplements

These are the exact standalone helper scripts executed from the parent workspace
`.tmp` directory. Copy them byte-for-byte there before running; they resolve the
workspace from their own location. They are not imported by the PaperQA agent.
Use the original sibling layout `research/paperqa-loop` and `research/paperqa-reflect`.
Raw generation archives and the frozen citation201b3fb evaluator are prerequisites;
a fresh Git clone alone does not contain those data. Hashes are in helper-sha256.json.

- `analyze-loop-stage-b.py`: bundled Python/standard library; offline32-run audit,
  actual settings and observations, descriptive statistics and cluster bootstrap.
- `prepare-loop-stage-b-judge.py`: citation .venv Python; pass the imported Stage B
  directory. Default is offline audit; `--output NEW_PATH` creates mirrored packets
  and requests. No key or ledger access. Its `--self-test` additionally needs the
  original Stage A archives and `.tmp/loop-stage-b-evaluator-freeze.json`.
- `run-loop-stage-b-judge.py`: citation .venv Python; pass a frozen prepared plan.
  Default makes authenticated token-count requests and reads budget headroom but
  sends no generation. `--run` sends the32 paid requests once after the complete
  reservation fits. Do not repeat the completed measured plan; it has exclusive
  run/ledger guards. Key and ledger must remain on their original laptop host.

The wrapper adds only remaining-budget preflight and reuses exact token-count
bodies; the frozen evaluator, prompt, model and answer/source inputs are unchanged.
The measured plan and its audit identify the exact inputs. Rebuilding a plan has
a new identifier, and repeating a nondeterministic external judge is a new run.
The default wrapper checks the original pricing date validity through the judge;
do not treat the historical documentation-check date as a future price guarantee.
