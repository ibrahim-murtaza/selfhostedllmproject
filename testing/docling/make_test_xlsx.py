"""
Makes test.xlsx: a small, fictional, non-confidential two-sheet workbook.

  Sheet "Sales" : region x quarter table of plain numbers
  Sheet "Notes" : two text cells with marker codes (tests multi-sheet reading)

Values only, no formulas, on purpose: a file written by a script has no cached
formula results, which some readers show as empty. Files saved by real Excel
do have them.

Run:
    pip install openpyxl
    python make_test_xlsx.py
"""

from openpyxl import Workbook
from openpyxl.styles import Font

wb = Workbook()

sales = wb.active
sales.title = "Sales"
sales.append(["Region", "Q1", "Q2", "Q3", "Q4"])
for row in (
    ("North", 1200, 1350, 1100, 1500),
    ("South", 900, 980, 1020, 1100),
    ("East", 1450, 1600, 1580, 1720),
    ("West", 800, 875, 910, 990),
    ("Central", 1010, 1090, 1150, 1230),
):
    sales.append(row)
for cell in sales[1]:
    cell.font = Font(bold=True)

notes = wb.create_sheet("Notes")
notes["A1"] = "Fictional sales workbook for testing."
notes["A2"] = "Reference code: XLSX-ALPHA-2207"
notes["A4"] = "Closing code: XLSX-OMEGA-6419"

wb.save("test.xlsx")
print("Wrote test.xlsx\n")
print("Expected answers:")
print("  'what are the Q2 sales for the West region?'   -> 875")
print("  'which region had the highest Q4 sales?'       -> East (1720)")
print("  'what is the closing code?'                    -> XLSX-OMEGA-6419   (second sheet)")