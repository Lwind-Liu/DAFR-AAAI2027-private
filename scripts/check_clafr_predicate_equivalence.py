"""Decision equivalence only: random vectors are NOT benchmark trajectories."""
import json
import random
from clafr.compiler import PolicyCompiler
from clafr.features import FEATURE_NAMES
from clafr.schemas import FeatureVector
from clafr.predicate import predicate_feasible


def main():
    region = PolicyCompiler().compile(['private payment update untrusted'])
    rng = random.Random(29)
    disagreements = 0
    allowed = 0
    for _ in range(10000):
        vector = FeatureVector.from_mapping({k: rng.random() for k in FEATURE_NAMES})
        geometric = region.feasible(vector)
        allowed += geometric
        disagreements += geometric != predicate_feasible(region, vector)
    print(json.dumps({'seed': 29, 'vectors': 10000, 'allowed': allowed,
                      'disagreements': disagreements, 'runtime': 'clafr',
                      'scope': 'synthetic membership equivalence, not ASR or utility'}, indent=2))
    if disagreements:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
