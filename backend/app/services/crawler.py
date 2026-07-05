from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.models.schemas import ClickableItem, CrawlResult


NOISY_TAGS = ['script', 'style', 'noscript', 'svg', 'canvas']


async def fetch_with_httpx(url: str) -> CrawlResult:
    headers = {
        'User-Agent': 'PageTrustAuditor/1.0 (+prepublish-quality-audit)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            res = await client.get(url)
            text = extract_visible_text(res.text)
            return CrawlResult(
                url=url,
                final_url=str(res.url),
                status_code=res.status_code,
                html=res.text,
                text=text,
                title=extract_title(res.text),
                fetch_method='httpx',
            )
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(url=url, html='', text='', fetch_method='httpx', fetch_error=str(exc))


async def fetch_with_playwright(url: str) -> CrawlResult:
    settings = get_settings()
    if not settings.use_playwright:
        return await fetch_with_httpx(url)
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent='PageTrustAuditor/1.0')
            response = await page.goto(url, wait_until='networkidle', timeout=25000)
            html = await page.content()
            title = await page.title()
            final_url = page.url
            status_code = response.status if response else None
            await browser.close()
            return CrawlResult(
                url=url,
                final_url=final_url,
                status_code=status_code,
                html=html,
                text=extract_visible_text(html),
                title=title or extract_title(html),
                fetch_method='playwright',
            )
    except Exception as exc:  # noqa: BLE001
        fallback = await fetch_with_httpx(url)
        fallback.fetch_method = 'httpx_fallback_after_playwright_error'
        fallback.fetch_error = f'Playwright failed: {exc}; fallback_error: {fallback.fetch_error}' if fallback.fetch_error else f'Playwright failed: {exc}'
        return fallback


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html or '', 'lxml')
    title = soup.find('title')
    return title.get_text(' ', strip=True) if title else ''


def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html or '', 'lxml')
    for tag in soup(NOISY_TAGS):
        tag.decompose()
    text = soup.get_text('\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text[:120000]


def extract_clickables(html: str, base_url: str) -> list[ClickableItem]:
    soup = BeautifulSoup(html or '', 'lxml')
    items: list[ClickableItem] = []

    def clean_label(raw: str | None) -> str:
        label = re.sub(r'\s+', ' ', raw or '').strip()
        return label[:140] or '[no visible label]'

    for a in soup.find_all('a'):
        href = a.get('href')
        label = clean_label(a.get_text(' ', strip=True) or a.get('aria-label') or a.get('title'))
        items.append(
            ClickableItem(
                kind='link',
                label=label,
                raw_target=href,
                resolved_target=urljoin(base_url, href) if href else None,
            )
        )

    for button in soup.find_all('button'):
        label = clean_label(button.get_text(' ', strip=True) or button.get('aria-label') or button.get('title'))
        onclick = button.get('onclick')
        form_action = None
        parent_form = button.find_parent('form')
        if parent_form:
            form_action = parent_form.get('action')
        raw = infer_target_from_onclick(onclick) or form_action
        items.append(
            ClickableItem(
                kind='button',
                label=label,
                raw_target=raw,
                resolved_target=urljoin(base_url, raw) if raw else None,
            )
        )

    for role_button in soup.select('[role="button"]'):
        if role_button.name == 'button':
            continue
        label = clean_label(role_button.get_text(' ', strip=True) or role_button.get('aria-label') or role_button.get('title'))
        href = role_button.get('href') or role_button.get('data-href')
        items.append(
            ClickableItem(
                kind='role-button',
                label=label,
                raw_target=href,
                resolved_target=urljoin(base_url, href) if href else None,
            )
        )

    for inp in soup.find_all('input'):
        typ = (inp.get('type') or '').lower()
        if typ in {'submit', 'button', 'reset'}:
            label = clean_label(inp.get('value') or inp.get('aria-label') or typ)
            parent_form = inp.find_parent('form')
            raw = parent_form.get('action') if parent_form else None
            items.append(
                ClickableItem(
                    kind=f'input-{typ}',
                    label=label,
                    raw_target=raw,
                    resolved_target=urljoin(base_url, raw) if raw else None,
                )
            )

    # De-duplicate exact kind/label/target combinations
    seen = set()
    unique: list[ClickableItem] = []
    for item in items:
        key = (item.kind, item.label.lower(), item.raw_target or '')
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def infer_target_from_onclick(onclick: str | None) -> str | None:
    if not onclick:
        return None
    patterns = [
        r"window\.location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",
        r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
        r"window\.open\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, onclick)
        if match:
            return match.group(1)
    return None
