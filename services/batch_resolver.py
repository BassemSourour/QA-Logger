"""
Temporary batch resolution logic.

Current workflow:
- If the machine provides a full batch ticket, use it directly.
- If the machine only provides a short batch number, reconstruct the full ticket
  using the previous full batch ticket in the QA workbook.

Future workflow:
Batch ticket and related production information should come from barcode
scanning instead. When barcode scanning is implemented, this resolver should
be replaced or kept only as a fallback.
"""


def resolve_full_batch_ticket(
    beanpro_batch_number: int,
    previous_full_batch_ticket: int,
) -> int:
    if beanpro_batch_number >= 10000:
        return beanpro_batch_number

    previous_prefix = (
        previous_full_batch_ticket // 10000
    )

    candidates = [
        (
            previous_prefix - 1
        ) * 10000
        + beanpro_batch_number,
        previous_prefix * 10000
        + beanpro_batch_number,
        (
            previous_prefix + 1
        ) * 10000
        + beanpro_batch_number,
    ]

    return min(
        candidates,
        key=lambda candidate: abs(
            candidate - previous_full_batch_ticket
        ),
    )