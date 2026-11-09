"""STLab02 - CSV-driven test runner for EduCommerce (PASS / FAIL / BLOCKED)."""
import csv, json, time, datetime, html, base64, io
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ecommerce_app import fixture, D, CartLine

REQUIRED = ['test_case_id', 'requirement_id', 'condition_id', 'scenario_id', 'title', 'priority',
            'precondition', 'fixture_key', 'input_json', 'expected_type', 'expected_json']


class Blocked(Exception):
    """The TEST cannot run (bad data / setup). Not a product defect."""


def load_cases(csv_path):
    """E04 - read CSV, reject duplicate IDs."""
    with Path(csv_path).open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    ids = [r.get('test_case_id', '') for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f'DUPLICATE_TEST_IDS:{dup}')
    return rows


def build_env(fixture_key, setup):
    """E03 - fresh Checkout/Customer/Cart for EVERY test case (test isolation)."""
    try:
        service, customer, cart = fixture(fixture_key)
    except ValueError as exc:
        raise Blocked(f'FIXTURE_ERROR:{exc}')
    products = service.catalog.products
    for sku in setup.get('deactivate', []):
        products[sku].active = False
    for sku, qty in setup.get('stock', {}).items():
        products[sku].stock = qty
    if 'cart' in setup:
        cart.lines = [CartLine(s, q) for s, q in setup['cart']]
    if 'used_codes' in setup:
        customer.used_codes = set(setup['used_codes'])
    return service, customer, cart


def stocks(service):
    return {k: p.stock for k, p in service.catalog.products.items()}


def run_operation(inp, service, customer, cart):
    """E05 - dispatcher: call the target function, capture result AND state."""
    op, obs, before = inp['op'], {'error': ''}, stocks(service)
    try:
        if op == 'cart':
            for sku, qty in inp['adds']:
                cart.add(sku, qty)
        elif op == 'shipping':
            obs['shipping'] = int(service.shipping.calculate(D(inp['subtotal']), inp['area']))
        elif op == 'place':
            for call in inp['calls']:
                try:
                    service.place(customer, cart, area=call.get('area', 'inner'), voucher=call.get('voucher'),
                                  method=call.get('method', 'COD'), approved=call.get('approved', True),
                                  key=call.get('key', 'K-' + inp['_id']))
                    obs['error'] = ''
                except ValueError as exc:
                    obs['error'] = str(exc)
    except ValueError as exc:
        obs['error'] = str(exc)
    except Exception as exc:
        obs['error'] = f'UNEXPECTED_EXCEPTION:{type(exc).__name__}'
    obs['lines'] = [[l.sku, l.quantity] for l in cart.lines]
    obs['subtotal'] = int(cart.subtotal())
    obs['orders_count'] = len(service.orders)
    obs['charges_count'] = len(service.payments.charges)
    obs['used_codes'] = sorted(customer.used_codes)
    obs['stock_after'] = stocks(service)
    obs['stock_unchanged'] = before == obs['stock_after']
    return json.loads(json.dumps(obs)), before


def execute_case(row):
    """E06 - compare expected vs actual, handle exceptions, set PASS / FAIL / BLOCKED."""
    t0 = time.perf_counter()
    res = {k: row.get(k, '') for k in REQUIRED}
    res.update(actual_result='', error_message='', execution_status='', stock_before='', stock_after='')
    try:
        missing = [c for c in REQUIRED if not str(row.get(c, '')).strip()]
        if missing:
            raise Blocked(f'MISSING_COLUMNS:{missing}')
        try:
            inp, exp = json.loads(row['input_json']), json.loads(row['expected_json'])
        except json.JSONDecodeError as exc:
            raise Blocked(f'BAD_JSON:{exc.msg}')
        if inp.get('op') not in ('cart', 'shipping', 'place'):
            raise Blocked(f'UNKNOWN_OPERATION:{inp.get("op")}')
        inp['_id'] = row['test_case_id']
        service, customer, cart = build_env(row['fixture_key'], inp.get('setup', {}))
        obs, before = run_operation(inp, service, customer, cart)
        unknown = [k for k in exp if k not in obs]
        if unknown:
            raise Blocked(f'UNSUPPORTED_EXPECTED_KEY:{unknown}')
        diffs = {k: {'expected': v, 'actual': obs[k]} for k, v in exp.items() if obs[k] != v}
        res['actual_result'] = json.dumps({k: obs[k] for k in exp}, separators=(',', ':'))
        res['execution_status'] = 'PASS' if not diffs else 'FAIL'
        res['error_message'] = json.dumps(diffs, separators=(',', ':')) if diffs else ''
        res['stock_before'], res['stock_after'] = json.dumps(before), json.dumps(obs['stock_after'])
    except Blocked as exc:
        res['execution_status'], res['error_message'] = 'BLOCKED', str(exc)
    res['execution_time_ms'] = round((time.perf_counter() - t0) * 1000, 3)
    res['executed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    return res


def run_suite(csv_path='test_cases.csv', out_dir='reports'):
    """Run all cases, export CSV + HTML dashboard (table + chart)."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rows = load_cases(csv_path)
    run_id = 'RUN-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    results = []
    for i, r in enumerate(rows, 1):
        res = execute_case(r); res['run_id'] = f'{run_id}-{i:03d}'; results.append(res)
    df = pd.DataFrame(results)
    n = df.execution_status.value_counts()
    total, p, f_, b = len(df), int(n.get('PASS', 0)), int(n.get('FAIL', 0)), int(n.get('BLOCKED', 0))
    summ = df.groupby(['requirement_id', 'execution_status']).size().unstack(fill_value=0)
    for st in ('PASS', 'FAIL', 'BLOCKED'):
        if st not in summ: summ[st] = 0
    summ = summ[['PASS', 'FAIL', 'BLOCKED']]
    df.to_csv(out / 'test_execution.csv', index=False, encoding='utf-8-sig')
    fig, ax = plt.subplots(figsize=(7, 4)); bottom = None
    for st, col in (('PASS', '#16a34a'), ('FAIL', '#dc2626'), ('BLOCKED', '#f59e0b')):
        ax.bar(summ.index, summ[st], bottom=bottom, label=st, color=col)
        bottom = summ[st] if bottom is None else bottom + summ[st]
    ax.set_title('Results by requirement'); ax.set_ylabel('Test cases'); ax.legend(); fig.tight_layout()
    fig.savefig(out / 'chart_by_requirement.png', dpi=130)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=100); plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()
    colr = {'PASS': '#dcfce7', 'FAIL': '#fee2e2', 'BLOCKED': '#fef3c7'}
    body = ''.join(f'<tr style="background:{colr[r.execution_status]}">' + ''.join(
        f'<td>{html.escape(str(getattr(r, c)))}</td>' for c in
        ['test_case_id', 'requirement_id', 'scenario_id', 'expected_json', 'actual_result', 'execution_status']) + '</tr>'
        for r in df.itertuples())
    rq = ''.join(f'<tr><td>{i}</td><td>{x.PASS}</td><td>{x.FAIL}</td><td>{x.BLOCKED}</td></tr>' for i, x in summ.iterrows())
    page = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>EduCommerce Test Report</title><style>
body{{font:14px Arial;margin:30px}}table{{border-collapse:collapse;width:100%;margin-bottom:20px}}td,th{{border:1px solid #cbd5e1;padding:6px;font-size:12px;text-align:left}}
th{{background:#16385e;color:#fff}}.m{{display:inline-block;margin:6px;padding:10px 16px;border-radius:10px;background:#edf3f9;font-size:18px}}</style></head><body>
<h1>EduCommerce - STLab02 Test Execution</h1><div>{run_id}</div>
<div class="m">Total: {total}</div><div class="m">PASS: {p}</div><div class="m">FAIL: {f_}</div><div class="m">BLOCKED: {b}</div>
<div class="m">Pass rate: {round(100*p/total,1)}%</div><br><img src="data:image/png;base64,{b64}">
<h2>Summary by requirement</h2><table><tr><th>REQ</th><th>PASS</th><th>FAIL</th><th>BLOCKED</th></tr>{rq}</table>
<h2>Execution</h2><table><tr><th>Case</th><th>REQ</th><th>Scenario</th><th>Expected</th><th>Actual</th><th>Status</th></tr>{body}</table></body></html>'''
    (out / 'test_dashboard.html').write_text(page, encoding='utf-8')
    print(f'{run_id} | CSV rows {len(rows)} | Executed {total} | PASS {p} | FAIL {f_} | BLOCKED {b} | pass rate {round(100*p/total,1)}%')
    bad = df[df.execution_status != 'PASS']
    if len(bad):
        print(bad[['test_case_id', 'requirement_id', 'execution_status', 'error_message']].to_string(index=False))
    return df, out


if __name__ == '__main__':
    run_suite()
