"""Australian business identifier validation (ABN / ACN checksums).

ABN: subtract 1 from the first digit, weight digits by (10,1,3,5,7,9,11,13,15,17,19), sum mod 89 == 0.
ACN: weight first 8 digits by (8..1), check digit = (10 - sum mod 10) mod 10.
"""
import re

_ABN_W = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


def digits(value) -> str:
    return re.sub(r"\D", "", str(value)) if value is not None else ""


def is_valid_abn(value) -> bool:
    d = digits(value)
    if len(d) != 11 or d == "0" * 11:
        return False
    nums = [int(c) for c in d]
    nums[0] -= 1
    return sum(w * n for w, n in zip(_ABN_W, nums)) % 89 == 0


def is_valid_acn(value) -> bool:
    d = digits(value)
    if len(d) != 9 or d == "0" * 9:
        return False
    s = sum(int(c) * w for c, w in zip(d[:8], range(8, 0, -1)))
    return (10 - s % 10) % 10 == int(d[8])


def is_valid_nzbn(value) -> bool:
    """NZBN is a GS1 GLN-13: standard mod-10 check digit."""
    d = digits(value)
    if len(d) != 13:
        return False
    s = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(d[:12]))
    return (10 - s % 10) % 10 == int(d[12])
