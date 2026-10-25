"""Launch: streamlit run app.py"""
from dataclasses import asdict
from datetime import timezone
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from src.api_client import APIError, fetch_products
from src.config import STATUSES
from src.demo_data import generate_dataset, offline_products
from src.metrics import Filters, calculate, daily_sales, filter_dataset, order_rows, status_distribution, top_products
from src.reports import export_csv, export_excel, export_json, report

st.set_page_config(page_title='CommerceFlow · Sales Dashboard', page_icon='🛍️', layout='wide')
# This entrypoint is public and preview-only. Private Sheets jobs use the CLI.
if any(os.environ.get(key) for key in ('GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_SERVICE_ACCOUNT_JSON')):
    st.error('Google credentials must not be attached to this public dashboard. Remove them from the web environment and use the standalone CLI for private synchronization.')
    st.stop()
st.markdown('''<style>
.block-container{max-width:1440px;padding-top:2rem;padding-bottom:3rem}
h1{letter-spacing:-.045em} h2,h3{letter-spacing:-.025em}
[data-testid="stMetric"]{background:white;border:1px solid #dfe7ef;border-radius:14px;padding:18px}
[data-testid="stMetricValue"]{font-size:1.9rem}
.hero{padding:20px 24px;background:#162b45;border-radius:16px;color:#fff;margin-bottom:22px}
.hero p{color:#c5d7e6;margin:6px 0 0}.eyebrow{color:#52d5c0;font-size:12px;letter-spacing:2px;font-weight:700}
@media(max-width:640px){.block-container{padding:4.5rem 1rem 2rem}.hero{padding:18px}[data-testid="stMetricValue"]{font-size:1.5rem}}
</style>''', unsafe_allow_html=True)

@st.cache_data(ttl=900, max_entries=2, show_spinner=False)
def cached_products():
    return fetch_products()

@st.cache_data(max_entries=4, show_spinner=False)
def dataset(products):
    return generate_dataset(products)


def dollars(value: int) -> str:
    return f'${value / 100:,.2f}'


def display_rows(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in ('unit_price', 'shipping_fee', 'discount_amount', 'gmv', 'refunds', 'net_sales', 'unit_price_at_purchase', 'net_revenue'):
        if column in frame:
            frame[column] = frame[column].map(lambda value: f'{value / 100:,.2f}')
    return frame


def plot(fig):
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      margin=dict(l=10, r=10, t=25, b=10), font=dict(color='#162b45'),
                      colorway=['#087f8c', '#53b5a7', '#e3ac55', '#617ca5', '#d77777', '#a38cc5'])
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})


def trend():
    frame = pd.DataFrame(daily_sales(selected, filters))
    frame['USD'] = frame['net_sales'] / 100
    st.subheader('Daily recognized sales')
    plot(px.area(frame, x='date', y='USD', color_discrete_sequence=['#087f8c'], labels={'date': 'Order date · UTC'}))


def products_chart():
    st.subheader('Top products')
    rows = top_products(selected)[:8]
    if rows:
        frame = pd.DataFrame(rows).sort_values('net_revenue')
        frame['USD'] = frame['net_revenue'] / 100
        plot(px.bar(frame, x='USD', y='title', orientation='h', color_discrete_sequence=['#087f8c'], labels={'title': ''}))
    else:
        st.info('No recognized product sales match these filters.')
    st.caption('Product revenue is after allocated discounts and excludes shipping.')

st.sidebar.title('CommerceFlow')
st.sidebar.caption('API automation & sales analytics')
page = st.sidebar.radio('Workspace', ['Overview', 'API Connection / Data Source', 'Orders Explorer', 'Sales Analytics', 'Report Export', 'Google Sheets Integration', 'Integrations (Coming Soon)'])
st.sidebar.divider()
source = st.session_state.get('source', 'Bundled fictional products · offline')
products = st.session_state.get('products', offline_products())
data = dataset(products)
first = min(o.order_date.date() for o in data.orders)
last = max(o.order_date.date() for o in data.orders)
st.sidebar.subheader('Report filters')
st.sidebar.caption('Applied to all KPIs, charts, orders, and exports.')
start = st.sidebar.date_input('Start date · UTC', first, min_value=first, max_value=last)
end = st.sidebar.date_input('End date · UTC', last, min_value=first, max_value=last)
statuses = st.sidebar.multiselect('Order statuses', STATUSES, default=list(STATUSES))
search = st.sidebar.text_input('Search order ID', placeholder='DEMO-00042', max_chars=60)
if start > end:
    st.error('Start date must be on or before end date.')
    st.stop()
filters = Filters(start, end, tuple(statuses), search)
selected = filter_dataset(data, filters)
kpis = calculate(selected)
st.sidebar.caption(f'{len(selected.orders)} / {len(data.orders)} orders selected')
st.sidebar.info('DEMO / SYNTHETIC DATA\n\nAll customers, orders, and revenue are fictional. Currency: USD.')
st.markdown('<div class="hero"><div class="eyebrow">INDEPENDENT PORTFOLIO PROJECT</div><h1 style="color:white;font-size:2rem;margin:8px 0">E-commerce API Automation & Sales Dashboard</h1><p>From product API to normalized orders, reliable metrics, and ready-to-use reports.</p></div>', unsafe_allow_html=True)
st.caption(f'DEMO / SYNTHETIC DATA · {source} · {start} → {end} UTC')
st.header(page)
if not selected.orders:
    st.info('No orders match the current filters. Charts and exports reflect the empty selection.')

if page == 'Overview':
    cards = st.columns(4)
    for card, label, value in zip(cards, ['Recognized sales', 'Paid orders', 'Average order value', 'Units sold'],
                                  [dollars(kpis['net_sales']), str(kpis['paid_order_count']), dollars(kpis['average_order_value']), str(kpis['units_sold'])]):
        card.metric(label, value)
    st.caption('Paid orders include paid, shipped, and completed. Recognized sales include shipping; pending, cancelled, and fully refunded orders contribute zero.')
    left, right = st.columns([1.2, 1])
    with left: trend()
    with right: products_chart()
    st.subheader('Recent orders')
    st.dataframe(display_rows(sorted(order_rows(selected), key=lambda r: r['order_date'], reverse=True)[:10]), hide_index=True, width='stretch')
elif page == 'API Connection / Data Source':
    st.write('Retrieve public product metadata from DummyJSON, then generate fictional commerce records. The API does not provide this dashboard’s orders or revenue.')
    a, b = st.columns(2)
    if a.button('Fetch products from DummyJSON', type='primary', width='stretch'):
        try:
            with st.spinner('Fetching validated, paginated products…'):
                result = cached_products()
            st.session_state.pop('last_fetch_error', None)
            st.session_state.update(products=result.products,
                source='DummyJSON public product API + synthetic commerce',
                fetch_info={'status': 'Success', 'timestamp': result.fetched_at.isoformat(), 'requests': result.requests, 'total': result.total},
                source_notice=f'Loaded {len(result.products)} validated products.')
            st.rerun()
        except APIError as error:
            st.session_state['last_fetch_error'] = str(error)
            st.error(str(error))
            st.info('The current dataset is retained. You can use bundled products below.')
    if b.button('Use bundled offline products', width='stretch'):
        st.session_state.update(products=offline_products(), source='Bundled fictional products · offline',
                                source_notice='Offline catalog loaded; no network required.')
        st.rerun()
    if 'source_notice' in st.session_state:
        st.success(st.session_state['source_notice'])
    info = st.session_state.get('fetch_info')
    st.write(f'**Active source:** {source}')
    st.metric('Active product records', len(products))
    if info:
        st.caption(f'Last successful API request: {info["timestamp"]} · {info["requests"]} HTTP attempts · {info["total"]} available products. Responses cached for 15 minutes; at most 500 products loaded.')
    else:
        st.caption('API request status: Not requested. Bundled fictional catalog is active.')
    if 'last_fetch_error' in st.session_state:
        st.warning('Last failed API attempt: ' + st.session_state['last_fetch_error'])
    st.caption('Switching catalogs deterministically regenerates synthetic orders against the selected products. Fetch timestamp is the actual cached retrieval time.')
    st.dataframe(display_rows([asdict(p) for p in products]), hide_index=True, width='stretch')
elif page == 'Orders Explorer':
    st.write('Use the shared sidebar filters to search and narrow every report.')
    st.dataframe(display_rows(order_rows(selected)), hide_index=True, width='stretch')
    if selected.orders:
        oid = st.selectbox('Order detail', [o.order_id for o in selected.orders])
        order = next(o for o in selected.orders if o.order_id == oid)
        customer = next(c for c in selected.customers if c.customer_id == order.customer_id)
        st.write(f'**{customer.display_name}** · {order.status} · {order.order_date.astimezone(timezone.utc).isoformat()}')
        lookup = {p.product_id: p for p in products}
        rows = [{**asdict(i), 'title': lookup[i.product_id].title} for i in selected.items if i.order_id == oid]
        st.dataframe(display_rows(rows), hide_index=True, width='stretch')
        st.caption('Line items use purchase-time prices. Current catalog prices do not change historical revenue.')
elif page == 'Sales Analytics':
    trend()
    a, b = st.columns(2)
    with a: products_chart()
    with b:
        st.subheader('Order status distribution')
        plot(px.bar(pd.DataFrame(status_distribution(selected)), x='status', y='orders'))
    st.subheader('Financial reconciliation · USD')
    st.dataframe(pd.DataFrame([{'Metric': key.replace('_', ' ').title(), 'Value': dollars(kpis[key])} for key in
                              ['gmv', 'paid_gmv', 'discounts', 'shipping_fees', 'refunds', 'cancelled_gmv', 'net_sales']]), hide_index=True, width='stretch')
    st.caption('Selected GMV includes all statuses. Paid GMV − paid discounts + paid shipping = recognized sales. Refunds are full historical charge reversals, shown separately and not subtracted twice. All trends group by original order date.')
elif page == 'Report Export':
    st.write('Download the exact current selection. Files are generated in memory; no customer data is saved to a shared output folder.')
    st.write(f'**{len(selected.orders)} orders · {len(selected.items)} line items · {dollars(kpis["net_sales"])} recognized sales**')
    payload = report(selected, filters, source)
    a, b, c = st.columns(3)
    a.download_button('Download orders CSV', export_csv(payload), 'demo_filtered_orders.csv', 'text/csv', width='stretch', on_click='ignore')
    b.download_button('Download report JSON', export_json(payload), 'demo_sales_report.json', 'application/json', width='stretch', on_click='ignore')
    c.download_button('Download Excel workbook', export_excel(payload), 'demo_sales_report.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', width='stretch', on_click='ignore')
    st.info('Excel sheets: Summary, Orders, OrderItems, TopProducts. CSV contains normalized orders. JSON includes metadata, summary, orders, line items, and product performance.')
    st.caption('All monetary exports use exact USD decimal strings. Spreadsheet formula-like text is escaped. Reports are limited to 10 MB.')
    with st.expander('Preview summary and filter metadata'):
        st.json({'metadata': payload['metadata'], 'summary': payload['summary']})
elif page == 'Google Sheets Integration':
    from src.sheets_auth import credential_status
    from src.sheets import SheetTargets, build_plan
    st.subheader('Google Sheets report synchronization')
    st.write('**Credential status:** ' + credential_status())
    st.caption('Configured does not mean authenticated. No Google request has been made by this page.')
    st.info('Public demo safety: this page only previews reports. Authorized writes run through the standalone CLI on a trusted machine; no credential upload or shared write button is exposed.')
    targets = SheetTargets(os.environ.get('GOOGLE_SHEETS_SUMMARY_SHEET', 'CommerceFlow_Summary'),
                           os.environ.get('GOOGLE_SHEETS_ORDERS_SHEET', 'CommerceFlow_Orders'),
                           os.environ.get('GOOGLE_SHEETS_PRODUCTS_SHEET', 'CommerceFlow_TopProducts'))
    try:
        preview = build_plan(report(selected, filters, source), targets).preview()
        st.json(preview)
    except ValueError as error:
        st.error(str(error))
    st.code('.venv/bin/python -m src.automation --dry-run', language='bash')
    st.caption('Synchronization replaces the complete report snapshot in dedicated app-owned tabs, requires explicit replacement consent on reruns, and refuses existing unmanaged tabs. See README for authorization and scheduling.')
else:
    st.subheader('Automation roadmap')
    st.write('Google Sheets synchronization and a standalone CLI are implemented. No scheduler has been installed or enabled.')
    st.markdown('1. Configure your service account locally and review the dry-run.\n2. Authorize dedicated report tabs with the CLI.\n3. Install a cron or GitHub Actions schedule after reviewing the provided examples.')
    st.caption('This public demo requires no credentials, paid APIs, or authentication.')
st.divider()
st.caption('Independent portfolio demonstration · DEMO / SYNTHETIC DATA · No real customer records or client engagement')
