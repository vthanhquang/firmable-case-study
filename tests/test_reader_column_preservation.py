import csv

import openpyxl
import pytest

from firmable.mapping.schema import ReaderSpec
from firmable.sources.readers import iter_records


@pytest.mark.parametrize("kind", ["xlsx", "delimited"])
def test_repeated_headers_preserve_current_and_previous_values(tmp_path, kind):
    path = tmp_path / ("source.xlsx" if kind == "xlsx" else "source.csv")
    rows = [["Employer", "Gap (%)", "Gap (%) ", "Gap (%)_2", None],
            ["Example", "0.244", "0.125", "already named", "last"]]
    if kind == "xlsx":
        wb = openpyxl.Workbook()
        for row in rows:
            wb.active.append(row)
        wb.save(path)
    else:
        with path.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)
    row = next(iter_records(path, ReaderSpec(format=kind)))
    assert len(row) == 5
    assert row == {"Employer": "Example", "Gap (%)": "0.244", "Gap (%)_3": "0.125",
                   "Gap (%)_2": "already named", "column_4": "last"}


def test_repeated_blank_and_generated_labels_do_not_overwrite(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text(",column_0,column_0,column_0_2\na,b,c,d\n", encoding="utf-8")
    row = next(iter_records(path, ReaderSpec(format="delimited")))
    assert len(row) == 4
    assert list(row.values()) == ["a", "b", "c", "d"]
