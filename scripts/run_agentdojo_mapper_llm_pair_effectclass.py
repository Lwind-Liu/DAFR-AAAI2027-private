from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUTO=ROOT/'external/official_baselines/AutoDojo'
out=ROOT/'results/runs/agentdojo_mapper_pair_smoke/llm_mapper_clafr_effectclass'
out.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
# Caller provides API variables; this script only forwards them.
env['PYTHONPATH']=f"{AUTO/'agentdojo/src'}:{ROOT/'src'}"
env['CLAFR_MAPPER_ARTIFACT']=str(ROOT/'results/summaries/agentdojo_mapper_banking_v1/artifact_effectclass_v1.jsonl')
base=[sys.executable,'-m','agentdojo.scripts.benchmark','--model','qwen-max','--model-id','qwen-max','--benchmark-version','v1.2.2','--suite','banking','--defense','clafr','--logdir',str(out),'--force-rerun']
tasks=[f'user_task_{i}' for i in range(8)]
commands=[('clean',base+sum((['--user-task',t] for t in tasks),[])),('attack',base+['--attack','important_instructions','--injection-task','injection_task_0']+sum((['--user-task',t] for t in tasks),[]))]
for label,cmd in commands:
 log=out/f'{label}.stdout.log'
 with log.open('w') as f:
  f.write(' '.join(cmd)+'\n'); f.flush()
  rc=subprocess.run(cmd,cwd=AUTO,env=env,stdout=f,stderr=subprocess.STDOUT).returncode
 if rc: raise SystemExit(f'{label} failed rc={rc}; see {log}')
 print(label, 'ok', log)
