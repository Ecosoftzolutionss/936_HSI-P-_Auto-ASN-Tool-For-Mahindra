from playwright.sync_api import sync_playwright


def test_google_search():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)

        page = browser.new_page()

        page.goto("https://www.google.com")

        print("Page Title:", page.title())

        page.fill("textarea[name='q']", "Python Playwright automation")

        page.press("textarea[name='q']", "Enter")

        page.wait_for_timeout(3000)

        print("Search completed")

        browser.close()