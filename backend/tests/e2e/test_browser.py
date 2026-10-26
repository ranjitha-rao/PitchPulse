"""Browser tests against the built app. Run: npm run build (frontend), then pytest -m e2e."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "frontend" / "dist"
PORT = 8765

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def base_url():
    if not (DIST / "index.html").exists():
        pytest.skip("frontend/dist missing: run `npm run build` in frontend first")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--port", str(PORT)],
                            cwd=ROOT / "backend", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 20
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                break
        time.sleep(0.2)
    yield f"http://127.0.0.1:{PORT}"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        exe = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    pg = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url)
    pg.get_by_text("Live", exact=False).first.wait_for()
    pg.get_by_role("button", name="40x").click()
    yield pg
    assert not errors, errors
    pg.close()


def seek(page, minute):
    page.get_by_role("button", name=f"{minute}'", exact=True).click()


def test_fan_view_shows_score_and_story(page):
    seek(page, 60)
    page.locator(".sb-score", has_text="0 – 2").wait_for(timeout=15000)
    page.locator(".feed li").first.wait_for(timeout=15000)
    assert page.locator(".wp-bar span").count() == 3


def test_analyst_mode_in_arabic_is_right_to_left(page):
    page.get_by_role("button", name="Analyst").click()
    page.get_by_role("button", name="العربية").click()
    page.get_by_text("Control vs Chaos").wait_for()
    seek(page, 60)
    page.locator(".ov[dir='rtl']").first.wait_for(timeout=30000)
    assert page.locator("svg.chart").count() >= 4


def test_player_focus_follows_the_player(page):
    page.get_by_role("button", name="Player focus").click()
    page.get_by_text("Following Daniel Okafor").wait_for()
    seek(page, 75)
    page.locator(".feed li", has_text="Okafor").first.wait_for(timeout=30000)


def test_full_time_recap_appears(page):
    seek(page, 87)
    recap = page.locator(".recap")
    recap.get_by_text("Full-time recap").wait_for(timeout=30000)
    assert "3-2" in recap.inner_text()


def test_studio_view_approves_a_cue_and_explains_it(page):
    seek(page, 60)
    page.locator(".feed li").first.wait_for(timeout=30000)
    page.get_by_role("button", name="Studio view").click()
    row = page.locator(".queue tbody tr").first
    row.get_by_role("button", name="Approve").click()
    assert "approved" in row.get_attribute("class")
    page.get_by_text("Why this cue?").wait_for()
    assert page.locator(".facts tr.driver").count() >= 1


def test_studio_shows_the_agent_newsroom_and_trace(page):
    seek(page, 60)
    page.locator(".feed li").first.wait_for(timeout=30000)
    page.get_by_role("button", name="Studio view").click()
    assert page.locator(".agents .agent").count() == 4
    page.get_by_text("Agent trace").wait_for()
    agents = page.locator(".trace li b").all_inner_texts()
    assert agents == ["Analyst", "Producer", "Narrator", "Fact-checker"]


def test_studio_offers_webvtt_download(page):
    page.get_by_role("button", name="Studio view").click()
    link = page.get_by_role("link", name="Download WebVTT")
    assert "/api/captions.vtt?mode=casual&lang=en" in link.get_attribute("href")
    body = page.request.get(page.url.rstrip("/") + link.get_attribute("href")).text()
    assert body.startswith("WEBVTT")
