import json
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis import freeze
from intake import IntakeCatalog, accept, pack
from protocol import RevisionStore, Transition, revise
from records import connect_archive, get, initialize_archive
from review import sign, sign_stagger
import stagger_examples


def prepare(station_path, intake, bench, wait_after_miss):
    half = Fraction(1, 2)
    states = ['试验', '通过', '失败']
    edges = [Transition('试验', '通过', half)]
    if wait_after_miss:
        states.append('等待')
        edges.extend((Transition('试验', '等待', half), Transition('等待', '试验', Fraction(1))))
    else:
        edges.append(Transition('试验', '试验', half))
    with closing(RevisionStore(station_path)) as station:
        station.initialize()
        revision = revise(station, bench, states=states, start='试验', pass_state='通过',
                          fail_state='失败', transitions=edges)
        metrics, frozen = freeze(station, revision)
        package = pack(frozen)
    accepted = accept(intake, package, package.identity)
    print(f'{bench} {revision} {accepted} 首拍 {metrics.first_tick_pass} '
          f'最终通过 {metrics.eventual_pass} 永不通过 {metrics.never_pass}')
    return accepted


def check_report(case_id, signed, retrieved, expected, parents, input_data, oracle):
    if retrieved != signed or (signed.draft.joint_pass, signed.draft.conditional_sync) != (1, expected):
        raise AssertionError(f'{case_id} report calculation or retrieval mismatch')
    if tuple(parent.accepted_id for parent in retrieved.draft.parents) != parents:
        raise AssertionError(f'{case_id} report parent mismatch')
    if retrieved.receipt.accepted_ids != parents:
        raise AssertionError(f'{case_id} receipt parent mismatch')
    print(f'{retrieved.report_id} 共同通过 {retrieved.draft.joint_pass} '
          f'同拍条件 {retrieved.draft.conditional_sync} 首执 {retrieved.receipt.receipt_id}')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': input_data,
        'expected': {'joint_pass': '1', 'conditional_sync': str(expected)},
        'actual': {'joint_pass': str(signed.draft.joint_pass),
                   'conditional_sync': str(signed.draft.conditional_sync)},
        'downstream_expected': {'parents': parents, 'conditional_sync': str(expected)},
        'downstream_actual': {'parents': [parent.accepted_id for parent in retrieved.draft.parents],
                              'conditional_sync': str(retrieved.draft.conditional_sync)},
        'code_paths': ['analysis/freeze.py', 'intake/admit.py', 'review/sync.py',
                       'records/publish.py', 'records/lookup.py'],
        'oracle': oracle,
    }, ensure_ascii=False, sort_keys=True))


def stagger_demo(directory):
    station_path = directory / 'stagger-station.sqlite'
    intake_path = directory / 'stagger-intake.sqlite'
    archive_path = directory / 'stagger-archive.sqlite'
    catalog = IntakeCatalog(intake_path)
    catalog.initialize()
    with closing(RevisionStore(station_path)) as station:
        station.initialize()
        tie_parents = stagger_examples.issue_pair(station, catalog, 'tie')
        retry_parents = stagger_examples.issue_pair(station, catalog, 'retry')
    # 站库关闭；夜班只凭实收件向档案库签发。
    with closing(connect_archive(archive_path)) as archive:
        initialize_archive(archive)
        tie = sign_stagger(catalog, archive, *tie_parents)
        retry = sign_stagger(catalog, archive, *retry_parents)
        swapped = sign_stagger(catalog, archive, *tie_parents[::-1])
    # 实收库关闭后重开档案，按号原样领取。
    catalog.close()
    with closing(connect_archive(archive_path)) as reopened:
        for case_id, signed, parents, expected_offsets, expected_conditional in (
            ('stagger.tie', tie, tie_parents, (0, 2), Fraction(1, 2)),
            ('stagger.retry', retry, retry_parents, (2,), Fraction(1, 3)),
            ('stagger.tie.swapped', swapped, tie_parents[::-1], (-2, 0), Fraction(1, 2)),
        ):
            retrieved = get(reopened, signed.report_id)
            if retrieved != signed:
                raise AssertionError(f'{case_id} retrieval mismatch')
            draft = retrieved.draft
            if draft.offsets != expected_offsets or draft.conditional_sync != expected_conditional:
                raise AssertionError(f'{case_id} stagger result mismatch')
            ordered = [parent.accepted_id for parent in draft.parents]
            if tuple(ordered) != parents or retrieved.receipt.accepted_ids != parents:
                raise AssertionError(f'{case_id} ordered parents mismatch')
            print(f'{retrieved.report_id} 共同通过={draft.joint_pass} 最优差={draft.offsets} '
                  f'条件概率={draft.conditional_sync} 首执={retrieved.receipt.receipt_id}')
            print('POINTWISE_SCENARIO ' + json.dumps({
                'case_id': case_id,
                'expected': {'offsets': list(expected_offsets),
                             'conditional_sync': str(expected_conditional)},
                'actual': {'joint_pass': str(draft.joint_pass),
                           'offsets': list(draft.offsets),
                           'conditional_sync': str(draft.conditional_sync)},
                'ordered_parents': ordered,
                'report_id': retrieved.report_id,
                'source_disconnected': True,
                'code_paths': ['review/stagger.py', 'review/stagger_report.py',
                               'records/stagger_publish.py', 'records/stagger_lookup.py'],
            }, ensure_ascii=False, sort_keys=True))


def main():
    with TemporaryDirectory(prefix='bench-review-') as temporary:
        directory = Path(temporary)
        station_path = directory / 'station.sqlite'
        archive_path = directory / 'archive.sqlite'
        with closing(IntakeCatalog(directory / 'intake.sqlite')) as intake:
            intake.initialize()
            left = prepare(station_path, intake, '左台', False)
            right = prepare(station_path, intake, '右台', False)
            with closing(connect_archive(archive_path)) as archive:
                initialize_archive(archive)
                old = sign(intake, archive, left, right)
                new_left = prepare(station_path, intake, '左台', True)
                new = sign(intake, archive, new_left, right)
        with closing(connect_archive(archive_path)) as reopened:
            initialize_archive(reopened)
            check_report('v4', old, get(reopened, old.report_id), Fraction(1, 3), (left, right),
                         {'尝试通过率': '1/2', '左台失败后额外等待': 0, '右台失败后额外等待': 0},
                         '两台最终都必过。同拍联合质量为首项 1/4、公比 1/4 的几何级数。')
            check_report('v7.shifted_retry', new, get(reopened, new.report_id), Fraction(2, 7),
                         (new_left, right),
                         {'尝试通过率': '1/2', '左台失败后额外等待': 1, '右台失败后额外等待': 0},
                         '左台只在奇数拍尝试。同拍联合质量为首项 1/4、公比 1/8 的几何级数。')
        stagger_demo(directory)


if __name__ == '__main__':
    main()
