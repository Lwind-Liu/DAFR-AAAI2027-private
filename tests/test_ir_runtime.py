import random
import pytest
from clafr import FeatureVector, RuntimeEvidence, ToolAction, ConfidenceLiftedActionSelector
from clafr.compiler import PolicyCompiler
from clafr.features import FEATURE_NAMES
from clafr.ir_compiler import IRPolicyCompiler
from clafr.policy_ir import ConstraintIR, ConstraintIRValidationError, validate_constraint_ir
from clafr.predicate import predicate_feasible


def test_exact_predicates_match_full_region():
    region = PolicyCompiler().compile(['private payment update untrusted'])
    rng = random.Random(29)
    for _ in range(10000):
        vector = FeatureVector.from_mapping({k: rng.random() for k in FEATURE_NAMES})
        assert region.feasible(vector) == predicate_feasible(region, vector)


def test_empty_schema_is_not_unspecified_schema():
    ir = ConstraintIR.from_dict({'tool_name': 'read', 'roles': {'fake': 'data'}})
    with pytest.raises(ConstraintIRValidationError):
        validate_constraint_ir(ir, schema_fields=[])


def test_ir_retains_envelope_and_rejects_tool_mismatch():
    ir = ConstraintIR.from_dict({'tool_name': 'send', 'preconditions': [
        {'type': 'confirmation', 'fields': ['body'], 'minimum': 1.0}]})
    compiler = IRPolicyCompiler(ir, schema_fields=['body'])
    evidence = RuntimeEvidence(trusted_task='Send hello', tool_schema={'send': ('body',)})
    base = PolicyCompiler().compile([], evidence)
    enhanced = compiler.compile([], evidence)
    assert enhanced.constraints[:len(base.constraints)] == base.constraints
    for backend in ['geometry', 'predicate']:
        selector = ConfidenceLiftedActionSelector(compiler=compiler, decision_backend=backend)
        result = selector.select([ToolAction('a', 'send', {'body': 'hello'})], evidence)
        assert not result.certificates[0].feasible
        assert 'ir:0:confirmation' in result.certificates[0].violated_constraints
        with pytest.raises(ValueError):
            selector.select([ToolAction('b', 'other')], evidence)


def test_unsupported_semantics_cannot_silently_disappear():
    for extra in [{'forbidden_effects': ['delete']}, {'preconditions': [
        {'type': 'authorization', 'fields': ['body']}]}]:
        with pytest.raises(ConstraintIRValidationError):
            IRPolicyCompiler(ConstraintIR.from_dict({'tool_name': 'send', **extra}), schema_fields=['body'])
