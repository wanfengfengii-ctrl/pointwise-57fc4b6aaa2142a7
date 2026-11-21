from dataclasses import dataclass
from fractions import Fraction

from analysis.first_pass import eventual_pass_mass, first_hit_mass
from analysis.process import TransientProcess


@dataclass(frozen=True, slots=True)
class SingleBenchMetrics:
    first_tick_pass: Fraction
    eventual_pass: Fraction
    never_pass: Fraction


def measure_bench(process: TransientProcess) -> SingleBenchMetrics:
    eventual = eventual_pass_mass(process.kernel)
    return SingleBenchMetrics(first_hit_mass(process.kernel, 1), eventual, 1 - eventual)
