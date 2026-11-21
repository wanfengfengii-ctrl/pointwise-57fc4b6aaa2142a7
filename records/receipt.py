import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Receipt:
    receipt_id: str
    report_id: str
    accepted_ids: tuple[str, str]


def make_receipt(report_id: str, accepted_ids: tuple[str, str]) -> Receipt:
    left, right = accepted_ids
    return Receipt(f'RC-{report_id}', report_id, (left, right))


def encode_receipt(receipt: Receipt) -> bytes:
    return json.dumps({
        'receipt_id': receipt.receipt_id,
        'report_id': receipt.report_id,
        'accepted_ids': receipt.accepted_ids,
    }, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('ascii')


def decode_receipt(body: bytes) -> Receipt:
    data = json.loads(body)
    left, right = data['accepted_ids']
    return Receipt(data['receipt_id'], data['report_id'], (left, right))
