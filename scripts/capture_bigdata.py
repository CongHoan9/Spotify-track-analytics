"""Optional visual QA and figures for defense slides (requires playwright + Chromium)."""
from pathlib import Path
import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

out=Path('reports/bigdata/figures');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    try:browser=p.chromium.launch(headless=True)
    except Exception:browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:8050',wait_until='networkidle')
    page.locator('.metric').first.wait_for(timeout=15000)
    assert page.locator('.metric').count()==4
    assert page.locator('.card').count()==9
    page.screenshot(path=str(out/'dashboard.png'),full_page=True)
    for i,card in enumerate(page.locator('.card').all()):
        card.screenshot(path=str(out/f'chart-{i+1:02}.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors,errors
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto('http://localhost:8080',wait_until='networkidle')
    page.screenshot(path=str(out/'spark-master.png'),full_page=True)
    with urllib.request.urlopen('http://localhost:8080/json/',timeout=10) as response:
        state=json.load(response)
    assert sum(w['state']=='ALIVE' for w in state['workers'])==2
    (out.parent/'cluster.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    run=json.loads((out.parent/'run.json').read_text())
    app_id=run['application_id']
    for _ in range(20):
        with urllib.request.urlopen('http://localhost:18080/api/v1/applications',timeout=10) as response:
            apps=json.load(response)
        if any(a['id']==app_id for a in apps):break
        time.sleep(2)
    else:raise AssertionError('Completed application not visible in History Server')
    page.goto(f'http://localhost:18080/history/{app_id}/jobs/',wait_until='networkidle')
    page.screenshot(path=str(out/'spark-history.png'),full_page=True)
    browser.close()
print('PASS: dashboard, desktop/mobile, two ALIVE workers and completed Spark History; figures exported.')
