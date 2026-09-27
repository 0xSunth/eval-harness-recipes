import json
import re
from pathlib import Path

import pytest

CASES_DIR = Path("cases/raw")
CASES = sorted(p for p in CASES_DIR.iterdir() if p.is_dir())


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_case_has_its_files(case_dir):
    for name in ("input.txt", "page.ld.json", "source.txt"):
        assert (case_dir / name).is_file(), f"missing {name}"


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_input_carries_the_header_durations(case_dir):
    text = (case_dir / "input.txt").read_text(encoding="utf-8")
    for label in ("Préparation :", "Cuisson :", "Temps total :"):
        assert label in text, f"missing '{label}'"


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_input_carries_the_yield(case_dir):
    lines = (case_dir / "input.txt").read_text(encoding="utf-8").splitlines()
    yield_line = lines[lines.index("Ingrédients") + 1]
    assert re.fullmatch(r"\d+ \S+", yield_line), (
        f"no yield after 'Ingrédients': {yield_line!r}"
    )


def test_split_covers_every_case_exactly_once():
    split = json.loads(Path("cases/split.json").read_text(encoding="utf-8"))
    dev, test = set(split["dev"]), set(split["test"])
    assert not dev & test, f"in both halves: {dev & test}"
    assert dev | test == {p.name for p in CASES}