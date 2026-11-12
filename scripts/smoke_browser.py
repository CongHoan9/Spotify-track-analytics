"""Optional browser integration test: pip install playwright; playwright install chromium."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request

import pandas as pd
from playwright.sync_api import sync_playwright

from music.baseline import build
from music.data import FEATURES


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    rows = []
    for i in range(25):
        row = dict.fromkeys(FEATURES, .1 + i/40)
        row.update(track_id=f"fixture{i}", track_name=f"Demo Song {i}", artists=f"Demo Artist {i}",
                   track_genre="pop", popularity=50+i, duration_ms=180000+i, tempo=80+i, loudness=-12+i/10)
        rows.append(row)
    csv = root/'fixture.csv'
    pd.DataFrame(rows).to_csv(csv,index=False)
    build(csv,root/'model')
    env = os.environ | {"SECRET_KEY": secrets.token_hex(32), "MODEL_DIR": str(root/'model'),
                        "DATABASE_URL": f"sqlite:///{root / 'app.db'}"}
    process = subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:create_app','--factory',
                                '--host','127.0.0.1','--port','8765'],env=env,stdout=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=1)
                break
            except OSError:
                time.sleep(.5)
        with sync_playwright() as p:
            try:
                browser=p.chromium.launch(headless=True)
            except Exception:
                browser=p.chromium.launch(channel='chrome',headless=True)
            page=browser.new_page(viewport={"width":1440,"height":1000})
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:8765')
            page.locator('#username').fill('browser_test')
            page.locator('#password').fill('safe-test-password')
            page.locator('#register').click()
            page.locator('.card').first.wait_for()
            page.locator('.card').first.get_by_role('button',name='♡ Thích',exact=True).click()
            page.get_by_text('Đã ghi nhận phản hồi của bạn',exact=True).wait_for()
            page.locator('[data-view="playlists"]').click()
            page.locator('#playlistName').fill('Browser playlist')
            page.locator('#newPlaylist').click()
            page.get_by_role('heading',name='Browser playlist').wait_for()
            page.locator('[data-view="discover"]').click()
            page.locator('.card').first.wait_for()
            Path('reports/figures').mkdir(parents=True,exist_ok=True)
            page.screenshot(path='reports/figures/browser-desktop.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path='reports/figures/browser-mobile.png',full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile overflow'
            assert not errors, errors
            browser.close()
            print('Browser smoke passed: register, recommend, like, playlist, responsive layout; synthetic fixture.')
    finally:
        process.terminate()
        process.wait(timeout=15)
