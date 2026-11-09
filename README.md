# STLab02 - EduCommerce Requirement-based Test Execution

Data-driven automated tests (Python + CSV) for the in-memory EduCommerce checkout module.

**Selected requirements (not REQ-06/08/11):** REQ-02, REQ-07, REQ-09, REQ-15, REQ-16
(5 REQs, 12 conditions, 13 scenarios, 17 test cases)

## Files
| File | Purpose |
|---|---|
| `ecommerce_app.py` | Application under test (unmodified lab source, contains the intentional defects) |
| `test_runner.py` | fixture, CSV reader, dispatcher, assertions, PASS/FAIL/BLOCKED, report export |
| `test_cases.csv` | Test cases (expected values come from the requirements) |
| `STLab02_Colab.ipynb` | Notebook that recreates and runs everything on Google Colab |
| `reports/` | `test_execution.csv`, `test_dashboard.html`, `chart_by_requirement.png` (sample run) |

## How to run (Google Colab, nothing to install)
1. Open https://colab.research.google.com -> File -> Upload notebook -> choose `STLab02_Colab.ipynb`.
2. Runtime -> Run all. The notebook writes the 3 source files, runs the suite and shows the dashboard.
3. Results are in `reports/` (download with the last cell).

Or on any machine with Python 3 + pandas + matplotlib: `python test_runner.py`

## Reference result
17 executed - 15 PASS - 2 FAIL - 0 BLOCKED (pass rate 88.2%).
FAIL: TC-SAF-002, TC-SAF-003 (stock is reduced although the payment method is rejected - DEF-001).
