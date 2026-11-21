from fractions import Fraction


def joint_pass_probability(left: Fraction, right: Fraction) -> Fraction:
    if not 0 <= left <= 1 or not 0 <= right <= 1:
        raise ValueError('bench probability outside [0, 1]')
    return left * right


def conditional_sync_probability(joint_pass: Fraction, synchronous: Fraction) -> Fraction | None:
    if not 0 <= synchronous <= joint_pass <= 1:
        raise ValueError('synchronous passage must be a subset of joint passage')
    return None if joint_pass == 0 else synchronous / joint_pass
