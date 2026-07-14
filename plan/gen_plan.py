"""gen_plan.py — minimal plan content builder utility."""

content: list[str] = []


def append_line(s: str) -> None:
    content.append(s)
