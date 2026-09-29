# Revision working text — experimental, not submission-ready

## Claim correction

A general arithmetic predicate can express exactly the same weighted halfspace and
second-order norm inequalities as our geometric implementation. We do not claim a
representational advantage over unrestricted if/else programs. Axis-aligned thresholds
are a restricted hypothesis class, not an equivalent implementation of the same policy.
The equivalent-predicate control shares constraints, features, evidence and candidate
ranking with the geometric backend. Its acceptance decisions should coincide.

## Proposed method

We investigate a training-free semantic mapper that translates trusted policy text and
tool schemas into a typed constraint representation. Structural validation checks the
representation; it does not establish semantic fidelity, completeness or authorization.
The experimental runtime intersects supported mapped constraints with the existing
trusted constraint envelope. Consequently, for fixed features and execution context,
the accepted set is a subset of that envelope. This inclusion is conditional on the
baseline's correctness and says nothing about safety of missing baseline policies.

The current adapter supports global preconditions and nonnegative risk budgets over
existing features. Field-scoped semantics and forbidden effects are rejected explicitly.
Role labels are not yet integrated into the feature encoder; therefore this prototype
must not be described as zero-shot tool generalization.

## Evaluation contract

1. Equivalent predicates: test decision agreement, including boundary points. Do not
   attribute ASR improvements to changing syntax from predicates to regions.
2. Mapper: held-out tools and policy paraphrases; measure omission, unsafe relaxation,
   field/role accuracy, abstention and API usage. Structural validity alone is insufficient.
3. Repair: compare against predicate-based candidate enumeration using identical repair
   candidates and cost. Measure executed effect preservation, unsafe repair and utility;
   feature-space projection distance is not proof of an executable repair.
4. Report fixed-trajectory diagnostic results separately from fresh end-to-end rollouts.

No new benchmark accuracy or security claims have been established by this revision.
