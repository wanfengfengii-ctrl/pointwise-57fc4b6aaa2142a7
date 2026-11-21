from analysis.evidence import FIRST_TICK, AnalysisIdentity, FrozenAnalysis
from analysis.metrics import SingleBenchMetrics, measure_bench
from analysis.process import PassageKernel, build_process
from protocol.revision import RevisionStore


def _anonymous_passage(kernel: PassageKernel) -> PassageKernel:
    order = [kernel.initial]
    positions = {kernel.initial: 0}
    for state in order:
        for target, _ in kernel.continuation[state]:
            if target not in positions:
                positions[target] = len(order)
                order.append(target)
    return PassageKernel(
        0,
        tuple(tuple(sorted((positions[target], weight) for target, weight in kernel.continuation[state]))
              for state in order),
        tuple(kernel.direct_pass[state] for state in order),
    )


def freeze(store: RevisionStore, revision_id: str) -> tuple[SingleBenchMetrics, FrozenAnalysis]:
    revision = store.get(revision_id)
    if revision is None:
        raise KeyError(revision_id)
    process = build_process(revision)
    metrics = measure_bench(process)
    identity = AnalysisIdentity(f'A-{revision_id}', revision.protocol.bench_id, revision_id)
    analysis = FrozenAnalysis(
        identity, FIRST_TICK, metrics.eventual_pass, metrics.never_pass,
        _anonymous_passage(process.kernel),
    )
    return metrics, analysis
