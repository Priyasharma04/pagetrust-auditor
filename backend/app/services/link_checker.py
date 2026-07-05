from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse, urldefrag, unquote

import httpx

from app.core.config import get_settings
from app.models.schemas import ClickableItem, Issue, Priority


CTA_WORDS = re.compile(
    r'\b(book|call|contact|visit|order|reserve|whatsapp|message|get directions|directions|buy|schedule|quote|inquire|enquire)\b',
    re.I,
)

UI_CONTROL_WORDS = re.compile(
    r'\b(toggle menu|menu|open menu|close menu|hamburger|expand|collapse|accordion|dropdown|tab|next|previous|prev|slider|carousel|plus|minus|show more|show less|read more|filter|sort)\b',
    re.I,
)


def is_ui_control(item: ClickableItem) -> bool:
    """
    Detect buttons/clickables that are UI controls, not broken lead/contact CTAs.

    Examples:
    - Toggle menu
    - Hamburger menu
    - Accordion expand/collapse
    - Service card plus/minus buttons
    - Slider/carousel next/previous
    - Tabs/dropdowns
    """
    label = item.label or ""
    kind = (item.kind or "").lower()

    if UI_CONTROL_WORDS.search(label):
        return True

    # Generic button without CTA wording is usually a UI action, not a broken link.
    if kind == "button" and not CTA_WORDS.search(label):
        return True

    # Icon-only or symbol buttons are often accordions/sliders/menu controls.
    cleaned = re.sub(r"\s+", "", label)
    if kind == "button" and cleaned in {"+", "-", "×", "x", "☰", "≡", ">", "<", "›", "‹"}:
        return True

    return False


def anchor_exists(html: str, fragment: str) -> bool:
    """
    Checks whether a URL fragment like #featured has a real matching HTML target.

    Valid targets:
    <section id="featured">
    <a name="featured">
    """
    if not fragment:
        return True

    target = re.escape(unquote(fragment))

    patterns = [
        rf'\bid\s*=\s*["\']{target}["\']',
        rf'\bname\s*=\s*["\']{target}["\']',
    ]

    return any(re.search(pattern, html, re.IGNORECASE) for pattern in patterns)


async def check_clickables(items: list[ClickableItem]) -> tuple[list[ClickableItem], list[Issue]]:
    settings = get_settings()
    sem = asyncio.Semaphore(settings.link_check_concurrency)
    issues: list[Issue] = []

    async with httpx.AsyncClient(
        timeout=settings.link_check_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": "PageTrustAuditor/1.0"},
    ) as client:
        checked = await asyncio.gather(*[_check_one(item, client, sem) for item in items])

    for idx, item in enumerate(checked):
        issue = issue_from_clickable(item, idx)
        if issue:
            issues.append(issue)

    return checked, issues


async def _check_one(
    item: ClickableItem,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
) -> ClickableItem:
    # Browser interaction audit may already have verified same-page anchors or JS/UI buttons.
    if item.status not in {"unknown"}:
        return item

    target = (item.resolved_target or item.raw_target or "").strip()
    label = item.label or ""

    if not target:
        if is_ui_control(item):
            item.status = "ui_control"
            item.reason = "Element appears to be an in-page UI control, not a navigation/contact CTA."
            item.priority = None
            return item

        item.status = "missing_target"
        item.reason = "Clickable element has no link, form action, or detectable navigation target."
        item.priority = Priority.high if CTA_WORDS.search(label) else Priority.medium
        return item

    lowered = target.lower()

    if lowered in {"#", "/#"} or lowered.endswith("/#"):
        if is_ui_control(item):
            item.status = "ui_control"
            item.reason = "Element appears to be an in-page UI control using a placeholder target."
            item.priority = None
            return item

        item.status = "placeholder"
        item.reason = "Target is a placeholder (#)."
        item.priority = Priority.high if CTA_WORDS.search(label) else Priority.medium
        return item

    if lowered.startswith("javascript:"):
        if is_ui_control(item):
            item.status = "ui_control"
            item.reason = "Element appears to be an in-page UI control using JavaScript."
            item.priority = None
            return item

        item.status = "javascript_target"
        item.reason = "Target uses javascript: and cannot be verified as a real navigation/action."
        item.priority = Priority.medium
        return item

    if lowered.startswith("mailto:"):
        email = target.split(":", 1)[1].split("?", 1)[0]
        item.status = "valid" if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) else "invalid_email_link"
        item.reason = None if item.status == "valid" else "Mailto link does not contain a valid email address."
        item.priority = None if item.status == "valid" else Priority.high
        return item

    if lowered.startswith("tel:"):
        phone = re.sub(r"\D+", "", target.split(":", 1)[1])
        item.status = "valid" if len(phone) >= 7 else "invalid_phone_link"
        item.reason = None if item.status == "valid" else "Tel link does not contain enough digits for a usable phone number."
        item.priority = None if item.status == "valid" else Priority.high
        return item

    if "wa.me/" in lowered or "api.whatsapp.com" in lowered:
        item.status = "valid" if re.search(r"(wa\.me/\d{7,}|phone=\d{7,})", lowered) else "suspicious_whatsapp_link"
        item.reason = None if item.status == "valid" else "WhatsApp link is present but no clear phone number was detected."
        item.priority = None if item.status == "valid" else Priority.high
        return item

    parsed = urlparse(target)

    if parsed.scheme not in {"http", "https"}:
        if is_ui_control(item):
            item.status = "ui_control"
            item.reason = "Element appears to be an in-page UI control, not an external/page navigation target."
            item.priority = None
            return item

        item.status = "unsupported_target"
        item.reason = f'Unsupported target scheme: {parsed.scheme or "none"}.'
        item.priority = Priority.medium
        return item

    async with sem:
        try:
            base_target, fragment = urldefrag(target)

            # Important:
            # URL fragments like #featured are never sent to the server.
            # So HEAD/GET on https://site.com/#featured only checks https://site.com/.
            # To verify anchor navigation, we must fetch HTML and check id/name manually.
            if fragment:
                response = await client.get(base_target)
            else:
                response = await client.head(base_target)

                if response.status_code in {405, 403} or response.status_code >= 500:
                    response = await client.get(base_target)

            item.status_code = response.status_code

            if 200 <= response.status_code < 400:
                if fragment:
                    if anchor_exists(response.text, fragment):
                        item.status = "working_anchor"
                        item.reason = None
                        item.priority = None
                    else:
                        item.status = "broken_anchor"
                        item.reason = (
                            f"Target returns {response.status_code}, but no matching "
                            f'id/name target was found for #{fragment}.'
                        )
                        item.priority = Priority.medium
                else:
                    item.status = "working"
                    item.reason = None
                    item.priority = None

            elif response.status_code == 404:
                item.status = "broken"
                item.reason = "Target returns 404 Not Found."
                item.priority = Priority.high

            elif response.status_code >= 500:
                item.status = "server_error"
                item.reason = f"Target returns server error {response.status_code}."
                item.priority = Priority.high

            else:
                item.status = "unhealthy"
                item.reason = f"Target returns HTTP {response.status_code}."
                item.priority = Priority.medium

            return item

        except Exception as exc:  # noqa: BLE001
            item.status = "unreachable"
            item.reason = f"Could not verify target: {exc}"
            item.priority = Priority.high if CTA_WORDS.search(label) else Priority.medium
            return item


def issue_from_clickable(item: ClickableItem, idx: int) -> Issue | None:
    if item.status in {
        "working",
        "working_200",
        "valid",
        "working_anchor",
        "working_interaction",
        "working_same_page_anchor",
        "ui_control",
    }:
        return None

    if item.status == "unknown":
        return None

    priority = item.priority or Priority.medium
    label = item.label or "[no label]"
    target = item.raw_target or item.resolved_target or "[missing]"

    if item.status == "broken_anchor":
        suggested_fix = (
            "Add a matching section id/name for the anchor target, or update the link "
            "to point to an existing section. Example: <section id=\"featured\">."
        )
    elif item.status in {"missing_target", "placeholder", "javascript_target"} and CTA_WORDS.search(label):
        suggested_fix = (
            "This looks like a lead/contact CTA. Connect it to a real phone, WhatsApp, booking, "
            "directions, email, form action, or page URL."
        )
    else:
        suggested_fix = (
            "Replace placeholder/broken targets with a real phone, WhatsApp, booking, "
            "directions, email, or page URL. Re-test before publishing."
        )

    return Issue(
        id=f"clickable-{idx}",
        priority=priority,
        dimension="Clickable audit",
        issue=f"{item.kind.title()} needs attention: {label}",
        evidence=f'Target: {target}; status: {item.status}; reason: {item.reason or "not verified"}',
        why_it_matters=(
            "Local business pages depend on calls, bookings, directions, WhatsApp, and contact CTAs. "
            "Broken actions directly reduce leads and trust."
        ),
        suggested_fix=suggested_fix,
        source="link_checker",
    )


def clickable_mismatch_issues(items: list[ClickableItem]) -> list[Issue]:
    """Detect CTA label/action mismatches that HTTP status alone cannot catch."""
    issues: list[Issue] = []

    for idx, item in enumerate(items):
        label = (item.label or "").lower()
        target = (item.resolved_target or item.raw_target or "").lower()

        if not target:
            continue

        # Don't run CTA mismatch checks on pure UI controls.
        if item.status == "ui_control":
            continue

        expected = None

        if re.search(r"\b(call|phone)\b", label) and not target.startswith("tel:"):
            expected = "tel: phone link"

        elif re.search(r"\b(email|mail)\b", label) and not target.startswith("mailto:"):
            expected = "mailto: email link"

        elif re.search(r"\b(whatsapp|message)\b", label) and not (
            "wa.me" in target or "api.whatsapp.com" in target or target.startswith("sms:")
        ):
            expected = "WhatsApp/SMS/message link"

        elif re.search(r"\b(directions|map|visit us|location)\b", label) and not (
            "map" in target or "waze" in target or "goo.gl" in target
        ):
            expected = "maps/directions link"

        elif (
            re.search(r"\b(book|reserve|appointment|schedule)\b", label)
            and ("instagram.com" in target or "facebook.com" in target)
            and item.status in {"working", "valid"}
        ):
            expected = "booking form/calendar/phone action, not only a social profile"

        if expected:
            issues.append(
                Issue(
                    id=f"clickable-mismatch-{idx}",
                    priority=Priority.medium,
                    dimension="Clickable audit",
                    issue=f"CTA label may not match its action: {item.label}",
                    evidence=f"Expected {expected}; detected target: {item.raw_target or item.resolved_target}",
                    why_it_matters=(
                        "Even when a link technically works, a mismatched CTA creates friction "
                        "and feels unpolished."
                    ),
                    suggested_fix="Make the action match the label, or rename the button to reflect the actual destination.",
                    source="clickable_mismatch_checker",
                )
            )

    return issues