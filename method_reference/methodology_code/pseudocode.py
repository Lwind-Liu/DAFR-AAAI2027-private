"""Paper-level pseudocode stored as an importable reference constant."""


REFERENCE_PSEUDOCODE = """
input: numeric point z, active geometric constraints C

evaluations = [evaluate(c, z) for c in C]
raw_margins = [item.raw_margin for item in evaluations]
M = min(raw_margins)

if M >= 0:
    return EXECUTE, certificate(M, evaluations)

violations = [item for item in evaluations if item.raw_margin < 0]
ordered = sort(violations, key=normalized_margin)
return resolution(ordered[0]), certificate(M, evaluations, ordered)
""".strip()
