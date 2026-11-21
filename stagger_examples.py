import argparse
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis import freeze
from intake import IntakeCatalog, accept, pack
from protocol import RevisionStore, Transition, revise
from records import connect_archive, get, initialize_archive
from review import sign


ZERO = Fraction(0)
ONE = Fraction(1)
HALF = Fraction(1, 2)
QUARTER = Fraction(1, 4)
CASES = {
    "tie": ("tie", "direct", ONE, HALF),
    "closed": ("closed", "direct", HALF, HALF),
    "dead": ("dead", "direct", ZERO, None),
    "retry": ("delayed_retry", "retry", ONE, Fraction(1, 12)),
    "long": ("long", "direct", ONE, ZERO),
}


def _delayed(wait, retry):
    chain = [f"等待{i + 1}" for i in range(wait)] + ["尝试"]
    edges = [(a, b, ONE) for a, b in zip(chain, chain[1:])]
    if retry:
        edges.extend([("尝试", "通过", HALF), ("尝试", "尝试", HALF)])
    else:
        edges.append(("尝试", "通过", ONE))
    return chain[0], edges


def _protocol(mode):
    if mode == "tie":
        return "首试", [("首试", "通过", HALF), ("首试", "间隔", HALF),
                       ("间隔", "末试", ONE), ("末试", "通过", ONE)]
    if mode == "closed":
        return "首试", [("首试", "通过", QUARTER), ("首试", "间隔", QUARTER),
                       ("首试", "停检", HALF), ("间隔", "末试", ONE),
                       ("末试", "通过", ONE), ("停检", "停检", ONE)]
    if mode == "dead":
        return "停检", [("停检", "停检", ONE)]
    wait, retry = {"direct": (0, False), "retry": (0, True),
                   "delayed_retry": (2, True), "long": (128, False)}[mode]
    return _delayed(wait, retry)


def _issue(station, catalog, bench, mode):
    start, edges = _protocol(mode)
    states = dict.fromkeys([start, "通过", "失败"])
    for source, target, _ in edges:
        states[source] = None
        states[target] = None
    revision = revise(station, bench, states=tuple(states), start=start,
                      pass_state="通过", fail_state="失败",
                      transitions=(Transition(*edge) for edge in edges))
    _, frozen = freeze(station, revision)
    package = pack(frozen)
    return accept(catalog, package, package.identity)


def issue_pair(station, catalog, case):
    left_mode, right_mode, _, _ = CASES[case]
    return (_issue(station, catalog, "左台", left_mode),
            _issue(station, catalog, "右台", right_mode))


def run_case(case):
    _, _, joint, conditional = CASES[case]
    with TemporaryDirectory(prefix="stagger-inputs-") as temporary:
        directory = Path(temporary)
        archive_path = directory / "archive.sqlite"
        with closing(IntakeCatalog(directory / "intake.sqlite")) as catalog:
            catalog.initialize()
            with closing(RevisionStore(directory / "station.sqlite")) as station:
                station.initialize()
                parents = issue_pair(station, catalog, case)
            with closing(connect_archive(archive_path)) as archive:
                initialize_archive(archive)
                signed = sign(catalog, archive, *parents)
        with closing(connect_archive(archive_path)) as archive:
            retrieved = get(archive, signed.report_id)
        if retrieved != signed:
            raise AssertionError(f"{case}: V1 领回结果与签发不符")
        draft = retrieved.draft
        if (draft.joint_pass, draft.conditional_sync) != (joint, conditional):
            raise AssertionError(f"{case}: V1 概率不符")
        if (tuple(parent.accepted_id for parent in draft.parents) != parents
                or retrieved.receipt.accepted_ids != parents):
            raise AssertionError(f"{case}: V1 父件顺序不符")
        print(f"{case} {retrieved.report_id} 同起点共同通过={draft.joint_pass} "
              f"同拍条件={draft.conditional_sync} 父件={parents}")


def main():
    parser = argparse.ArgumentParser(description="用错峰规程样例演示现有同起点签发")
    parser.add_argument("case", nargs="?", choices=tuple(CASES))
    case = parser.parse_args().case
    for name in (case,) if case else CASES:
        run_case(name)


if __name__ == "__main__":
    main()
