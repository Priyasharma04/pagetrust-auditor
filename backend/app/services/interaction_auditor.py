from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from app.core.config import get_settings
from app.models.schemas import ClickableItem, Priority

CTA_WORDS = re.compile(r'\b(book|call|contact|visit|order|reserve|whatsapp|message|get directions|directions|buy|schedule|quote|inquire|enquire)\b', re.I)

VALID_INTERACTION_STATUSES = {
    'working_anchor',
    'working_interaction',
    'working_same_page_anchor',
}


def _is_hash_target(target: str | None) -> bool:
    if not target:
        return False
    parsed = urlparse(target)
    # raw href like #features, or resolved URL containing only a same-page fragment
    return bool(target.strip().startswith('#') or parsed.fragment)


def _fragment(target: str | None) -> str:
    if not target:
        return ''
    target = target.strip()
    if target.startswith('#'):
        return target[1:]
    return urlparse(target).fragment


def _needs_interaction_check(item: ClickableItem) -> bool:
    raw = (item.raw_target or '').strip().lower()
    resolved = (item.resolved_target or '').strip().lower()
    label = (item.label or '').strip()

    # Same-page anchors like #features, #menu, #contact
    if _is_hash_target(item.raw_target) or _is_hash_target(item.resolved_target):
        return True

    # JS-based clickable links/buttons
    if raw.startswith('javascript:') or resolved.startswith('javascript:'):
        return True

    # Placeholder links may still trigger JS scroll/modal/accordion
    if raw in {'#', '/#'} or resolved in {'#', '/#'}:
        return True

    # Any non-standard clickable element should be browser-tested
    if item.kind in {
        'button',
        'role-button',
        'input-submit',
        'input-button',
        'input-reset',
        'card',
        'interactive',
        'div',
        'span',
        'clickable',
    }:
        return True

    # Clickable-looking element with label but no target
    if label and not raw and not resolved:
        return True

    return False
async def audit_browser_interactions(url: str, items: list[ClickableItem]) -> list[ClickableItem]:
    """Use Playwright to verify click behavior for same-page anchors and JS/UI buttons.

    The normal link checker is good for href/tel/mailto/http links, but it cannot know whether:
    - a hash nav item actually scrolls anywhere, or
    - a button with no href is a real accordion/card interaction.

    This pass intentionally updates only ambiguous same-page/JS/no-target clickables.
    """
    settings = get_settings()
    if not settings.use_playwright or not any(_needs_interaction_check(i) for i in items):
        return items

    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
    except Exception:  # noqa: BLE001
        return items

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent='PageTrustAuditor/1.0')
            page.set_default_timeout(2500)
            await page.goto(url, wait_until='networkidle', timeout=25000)

            for item in items[:80]:
                if not _needs_interaction_check(item):
                    continue

                try:
                    await page.evaluate('window.scrollTo(0, 0)')
                    locator = _locator_for_item(page, item)
                    if locator is None or await locator.count() == 0:
                        # Keep it unknown; deterministic checker will still handle missing targets.
                        continue
                    locator = locator.first()
                    if not await locator.is_visible():
                        item.status = 'not_visible'
                        item.reason = 'Clickable element exists in HTML but is not visible/clickable in the rendered page.'
                        item.priority = Priority.medium
                        continue

                    raw_target = item.raw_target or item.resolved_target or ''
                    if _is_hash_target(raw_target):
                        await _audit_anchor(page, locator, item)
                    else:
                        await _audit_button_like(page, locator, item)
                except PlaywrightTimeoutError:
                    # Do not falsely accuse working UI when browser probing times out.
                    if item.kind in {'button', 'role-button', 'input-submit', 'input-button'} and not item.raw_target:
                        item.status = 'interaction_timeout'
                        item.reason = 'Could not verify the interaction within the browser timeout.'
                        item.priority = Priority.medium
                except Exception:  # noqa: BLE001
                    # Fail open; the deterministic link checker will handle clear link issues.
                    continue

            await browser.close()
            return items
    except Exception:  # noqa: BLE001
        return items


def _locator_for_item(page, item: ClickableItem):
    raw = (item.raw_target or '').strip()
    label = (item.label or '').strip()

    # Prefer exact href matching for links, including #features and javascript:void(0)
    if raw:
        href_locator = page.locator(f'a[href={json.dumps(raw)}]')
        return href_locator

    # If no raw href, use visible label across common interactive elements
    if label and label != '[no visible label]':
        return page.locator(
            'a, button, [role="button"], input[type="submit"], input[type="button"], '
            '[onclick], [tabindex], .cursor-pointer'
        ).filter(has_text=label)

    # Last fallback
    return page.locator(
        'a, button, [role="button"], input[type="submit"], input[type="button"], '
        '[onclick], [tabindex], .cursor-pointer'
    )

async def _audit_anchor(page, locator, item: ClickableItem) -> None:
    target = item.raw_target or item.resolved_target or ''
    frag = _fragment(target)
    exists = await page.evaluate(
        """frag => Boolean(
            document.getElementById(frag) ||
            document.querySelector(`[name="${CSS.escape(frag)}"]`)
        )""",
        frag,
    )
    target_offset = await page.evaluate(
        """frag => {
            const el = document.getElementById(frag) || document.querySelector(`[name="${CSS.escape(frag)}"]`);
            if (!el) return null;
            const rect = el.getBoundingClientRect();
            return Math.round(rect.top + window.scrollY);
        }""",
        frag,
    )

    if not exists:
        item.status = 'missing_anchor_target'
        item.reason = f'Anchor target #{frag} was not found in the rendered page.'
        item.priority = Priority.medium
        return

    before = await _page_state(page, locator)
    await locator.click(force=False)
    await page.wait_for_timeout(600)
    after = await _page_state(page, locator)

    scroll_changed = abs(after['scrollY'] - before['scrollY']) > 25
    target_is_top_or_current = target_offset is not None and int(target_offset) <= 120

    if scroll_changed or target_is_top_or_current:
        item.status = 'working_anchor'
        item.reason = None
        item.priority = None
    else:
        item.status = 'anchor_no_visible_movement'
        item.reason = f'Anchor target #{frag} exists, but clicking it did not visibly move the page from the hero/top view.'
        item.priority = Priority.medium


async def _audit_button_like(page, locator, item: ClickableItem) -> None:
    before = await _page_state(page, locator)
    await locator.click(force=False)
    await page.wait_for_timeout(700)
    after = await _page_state(page, locator)

    url_changed = after['url'] != before['url']
    scroll_changed = abs(after['scrollY'] - before['scrollY']) > 25
    text_changed = abs(after['bodyTextLength'] - before['bodyTextLength']) > 15
    expanded_changed = after['expandedCount'] != before['expandedCount']
    bbox_changed = abs((after['height'] or 0) - (before['height'] or 0)) > 8

    if url_changed or scroll_changed or text_changed or expanded_changed or bbox_changed:
        item.status = 'working_interaction'
        item.reason = None
        item.priority = None
    else:
        item.status = 'no_detectable_action'
        item.reason = 'Clicking this element did not change URL, scroll position, visible text, expanded state, or element size.'
        item.priority = Priority.high if CTA_WORDS.search(item.label or '') else Priority.medium


async def _page_state(page, locator) -> dict:
    box = await locator.bounding_box()
    dom_state = await page.evaluate(
        """() => ({
            url: location.href,
            scrollY: Math.round(window.scrollY),
            bodyTextLength: (document.body?.innerText || '').length,
            expandedCount: [...document.querySelectorAll('[aria-expanded="true"]')].length
        })"""
    )
    return {
        **dom_state,
        'height': round(box['height']) if box else None,
    }
