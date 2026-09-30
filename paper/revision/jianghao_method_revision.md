# Revision working text — experimental, not submission-ready

## Claim correction

A general arithmetic predicate can express exactly the same weighted halfspace and
second-order norm inequalities as our geometric implementation. We do not claim a
representational advantage over unrestricted if/else programs. Axis-aligned thresholds
are a restricted hypothesis class, not an equivalent implementation of the same policy.
The equivalent-predicate control shares constraints, features, evidence and candidate
ranking with the geometric backend. Its acceptance decisions should coincide.

## Why keep geometry instead of a boolean if--else gate?

The claim is about the execution interface, not about the expressive power of
arithmetic. An unrestricted predicate can reproduce every current halfspace and
second-order cone, so the predicate control is required to match the geometry
decision. Geometry is retained because one typed region exposes four quantities
from the same object: (i) joint feasibility across fields, (ii) a signed and
normalized margin for every violated facet, (iii) an interface for future constrained repair search (not yet a closest-action solver), and (iv) a provenance-bearing certificate that
can be composed when a new policy facet is added. A boolean gate returns only
true/false; an arithmetic implementation can expose the same quantities from shared constraint objects. Maintenance and repair advantages therefore remain hypotheses, not intrinsic properties of geometry.

This is a falsifiable systems claim. We will compare geometry and an equivalent
predicate with the same feature vector, constraints, candidates and repair
budget. The primary metrics are decision disagreement (should be zero), boundary
ranking agreement, constraint-localization accuracy, executable repair success,
unsafe repair rate, clarification count, and added latency. If a predicate
implementation is augmented with the same margin and repair oracle, any geometry
advantage should disappear; that result is expected and will be reported as a
representation/maintenance advantage rather than a security guarantee.

The motivating failure mode is a coupled budget: two individually acceptable
fields can exceed a joint risk budget. Geometry represents this as one cone and
reports the joint slack. A collection of independent if--else thresholds misses
the interaction; a hand-written predicate can encode it, but then the coupling,
diagnostic, and repair logic must be maintained separately.

## Proposed method

We investigate a training-free semantic mapper that translates trusted policy text and
tool schemas into a typed constraint representation. Structural and semantic-completeness validation checks the
representation; it does not establish full semantic fidelity. Security preconditions must
name their affected fields and use positive thresholds; failures abstain rather than being
repaired into an allow decision.
The experimental runtime intersects supported mapped constraints with the existing
trusted constraint envelope. Consequently, for fixed features and execution context,
the accepted set is a subset of that envelope. This inclusion is conditional on the
baseline's correctness and says nothing about safety of missing baseline policies.

The current adapter supports field-scoped grounding and authorization through the
feature encoder, and aggregate nonnegative risk budgets over existing features. Field-scoped
risk budgets and forbidden effects are rejected explicitly.
Role labels are supplied by a large-language-model semantic mapper and then checked before
entering the feature encoder. If this mapper transfers to held-out tools without parameter
updates, the evidence supports training-free cross-tool semantic adaptation. It does not
imply that a trained encoder will work; a trained encoder is a separate distilled,
low-latency implementation of the same IR interface and requires its own evaluation.

## Evaluation contract

1. Equivalent predicates: test decision agreement, including boundary points. Do not
   attribute ASR improvements to changing syntax from predicates to regions.
2. Mapper: held-out tools and policy paraphrases; measure omission, unsafe relaxation,
   field/role accuracy, abstention and API usage. Structural validity alone is insufficient.
   Compare manual mapping, LLM mapping, and a trained/distilled encoder under the same IR
   and execution layer; do not transfer conclusions between these adapters.
3. Repair: compare against predicate-based candidate enumeration using identical repair
   candidates and cost. Measure executed effect preservation, unsafe repair and utility;
   feature-space projection distance is not proof of an executable repair.
4. Report fixed-trajectory diagnostic results separately from fresh end-to-end rollouts.

No new benchmark accuracy or security claims have been established by this revision.

## Evidence gate after protocol audit (2026-09-29)

The first mapper pilot was invalid because the runner sent the hand-written `gold`
object to the model.  The corrected runner withholds gold and checks both IR
validation and `IRPolicyCompiler.compile()`.  On the corrected 32-case pilot,
precondition exact match is 21.9% for Qwen-Max and 28.1% for DeepSeek V4 Flash;
unsafe relaxation is 65.6% for both models.  These numbers are the usable mapper
baseline; the earlier positive pilot numbers must not be cited as generalization.

On the same 8 clean plus 8 injection banking tasks, the hand-written CLAFR
baseline succeeds on 5/8 clean tasks and has 0/8 attack successes.  A frozen LLM
IR artifact succeeds on 3/8 clean and 2/8 attack-utility tasks, while a
deterministic read-only/effectful tool-class adapter reaches 4/8 and 4/8.  Both
LLM variants have 0/8 attack successes under AgentDojo's `security=true`
definition, but their abstentions and utility loss prevent a claim that the
mapper improves end-to-end safety.

The matched 64-case in-process geometry pilot has zero geometry/predicate decision
disagreements, 32/64 allows for each, and zero executable repairs.  We therefore
retain the geometry story only as a common representation for coupled constraints
and diagnostics; we withdraw any claim that geometry is more expressive than
if--else or has already demonstrated better repair utility.


## Current smoke evidence (not a benchmark result)

A four-tool smoke pilot with Qwen-Max produced structurally valid, backend-compilable mappings for `send_email`, `transfer_funds`, `delete_record`, and `publish_post`. Against hand-written labels for this pilot, role accuracy and precondition exact match were both 1.0. These numbers are not held-out generalization results. The pilot also exposed a necessary metric for the full study: over-constraint rate, since a mapper may safely include an ordinary field in an authorization set while reducing utility.
