from dataclasses import dataclass
from fractions import Fraction

from analysis.process import PassageKernel


FIRST_TICK = 1


@dataclass(frozen=True, slots=True)
class AnalysisIdentity:
    analysis_id: str
    bench_id: str
    revision_id: str


@dataclass(frozen=True, slots=True)
class FrozenAnalysis:
    identity: AnalysisIdentity
    first_tick: int
    eventual_pass: Fraction
    never_pass: Fraction
    passage: PassageKernel
