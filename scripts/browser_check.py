"""Optional real-browser smoke checks. Requires playwright and local Streamlit :8502."""
from pathlib import Path
import json
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts'
OUT.mkdir(exist_ok=True)
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which('google-chrome'), headless=True,
                               chromium_sandbox=True, args=['--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width':1440, 'height':1100})
    page.goto('http://127.0.0.1:8502')
    page.get_by_role('heading', name='Overview', exact=True).wait_for()
    page.locator('[data-testid=stMetricValue]').first.wait_for()
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / '01-overview.png'))
    assert page.locator('[data-testid=stException]').count() == 0
    for name in ['API Connection / Data Source', 'Orders Explorer', 'Sales Analytics', 'Report Export', 'Google Sheets Integration', 'Integrations (Coming Soon)']:
        page.get_by_text(name, exact=True).first.click()
        page.get_by_role('heading', name=name, exact=True).wait_for()
        page.wait_for_timeout(500)
        assert page.locator('[data-testid=stException]').count() == 0
        if name == 'Report Export':
            for label, filename in [('Download orders CSV','orders.csv'), ('Download report JSON','report.json'), ('Download Excel workbook','report.xlsx')]:
                with page.expect_download() as event:
                    page.get_by_role('button', name=label, exact=True).click()
                event.value.save_as(str(OUT / filename))
            payload = json.loads((OUT / 'report.json').read_text())
            assert len(payload['orders']) == 240
        results.append(name)
    # Shared filter must affect actual downloaded JSON.
    page.get_by_label('Search order ID', exact=True).fill('DEMO-00001')
    page.get_by_label('Search order ID', exact=True).press('Enter')
    page.get_by_text('Report Export', exact=True).first.click()
    page.get_by_role('heading', name='Report Export', exact=True).wait_for()
    with page.expect_download() as event:
        page.get_by_role('button', name='Download report JSON', exact=True).click()
    event.value.save_as(str(OUT / 'filtered.json'))
    assert len(json.loads((OUT / 'filtered.json').read_text())['orders']) == 1
    mobile = browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True)
    mobile.goto('http://127.0.0.1:8502')
    mobile.get_by_role('heading', name='Overview', exact=True).wait_for()
    mobile.wait_for_timeout(800)
    assert mobile.locator('[data-testid=stException]').count() == 0
    assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    mobile.screenshot(path=str(OUT / '02-mobile.png'), full_page=True)
    browser.close()
print(json.dumps({'pages':results,'downloads':3,'filtered_export_orders':1,'mobile_width':390,'status':'passed'}, indent=2))
