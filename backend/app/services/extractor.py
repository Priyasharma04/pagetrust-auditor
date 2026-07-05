from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from app.models.schemas import BusinessDetails, Issue, Priority, SeoAudit


EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.I,
)

OBFUSCATED_EMAIL_RE = re.compile(
    r"\b([A-Z0-9._%+-]+)\s*(?:\[at\]|\(at\)|\sat\s)\s*([A-Z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\sdot\s)\s*([A-Z]{2,})\b",
    re.I,
)

PHONE_RE = re.compile(
    r"""
    (?:
        (?<!\w)
        (?:\+|00)?\d{1,4}
        [\s().-]*
        (?:\(?\d{2,5}\)?[\s().-]*)?
        \d{3,4}
        [\s().-]*
        \d{3,4}
        (?:[\s().-]*\d{1,4})?
        (?!\w)
    )
    """,
    re.X,
)

HOURS_RE = re.compile(
    r"""
    (?:
        (?:
            mon|tue|wed|thu|fri|sat|sun|
            monday|tuesday|wednesday|thursday|friday|saturday|sunday
        )
        [\w\s,./-]*
        \d{1,2}
        (?::\d{2})?
        \s*(?:am|pm|a\.m\.|p\.m\.)?
        \s*(?:-|to|–|—)
        \s*
        \d{1,2}
        (?::\d{2})?
        \s*(?:am|pm|a\.m\.|p\.m\.)?
    )
    |
    (?:
        24\s*/\s*7|
        24\s*hours?|
        open\s+daily|
        daily\s+\d{1,2}
        (?::\d{2})?
        \s*(?:am|pm)?
    )
    """,
    re.I | re.X,
)

ADDRESS_LABEL_RE = re.compile(
    r"\b(address|location|visit us|where to find us|find us|directions|our place|come visit|store location|office location)\b",
    re.I,
)

ADDRESS_HINT_RE = re.compile(
    r"""
    \b(
        street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?|boulevard|blvd\.?|
        highway|hwy\.?|way|plaza|square|market|mall|center|centre|building|bldg\.?|
        floor|flr\.?|suite|ste\.?|unit|room|shop|store|lot|block|blk|phase|sector|
        village|subdivision|homes|estate|residences|barangay|brgy|purok|
        city|town|province|state|county|district|municipality|metro|
        near|beside|opposite|behind|corner|landmark|
        manila|cebu|makati|quezon|taguig|davao|bulacan|marilao|pasig|pasay|mandaluyong|
        india|usa|canada|philippines|uk|uae|australia
    )\b
    """,
    re.I | re.X,
)

ADDRESS_STOP_RE = re.compile(
    r"\b(email|e-mail|phone|tel|call|mobile|hours|opening|services|products|menu|follow|instagram|facebook|copyright|privacy|terms)\b",
    re.I,
)

# Keep this generic only. Do NOT add business-specific words like salon/food/clinic.
ADDRESS_NOISE_RE = re.compile(
    r"""
    \b(
        we|our|you|your|customers?|clients?|visitors?|
        focus|offer|offers|offering|provide|provides|
        about|contact|get\s+in\s+touch|book|booking|appointment|
        testimonial|portfolio|gallery|faq|learn\s+more|read\s+more
    )\b
    """,
    re.I | re.X,
)

SERVICE_HINTS = re.compile(
    r"\b(services?|products?|menu|pricing|packages?|repairs?|installation|delivery|massage|salon|tire|tyre|restaurant|clinic|booking|consultation|maintenance|wash|spa|beauty|food|coffee|parts?)\b",
    re.I,
)

CTA_RE = re.compile(
    r"\b(call|book|contact|visit|message|whatsapp|get directions|directions|order|reserve|inquire|enquire|quote|schedule)\b",
    re.I,
)

SOCIAL_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
]

MAP_DOMAINS = [
    "google.com/maps",
    "maps.app.goo.gl",
    "waze.com",
    "maps.google",
    "openstreetmap.org",
    "bing.com/maps",
    "mapbox.com",
]


def extract_business_details(
    html: str,
    text: str,
    url: str,
    expected_location: str = "",
) -> tuple[BusinessDetails, list[Issue]]:
    soup = BeautifulSoup(html or "", "lxml")
    details = BusinessDetails()

    combined_text = build_combined_text(soup, text)

    details.phones = extract_phones(soup, combined_text)[:10]
    details.emails = extract_emails(soup, combined_text)[:10]
    details.hours = extract_hours(combined_text)[:12]

    details.map_links = extract_map_links(soup)[:8]
    details.social_links = extract_social_links(soup)[:10]
    details.ctas = extract_ctas(soup)[:15]

    details.business_name_candidates = extract_business_name_candidates(soup)[:6]

    details.addresses = extract_addresses(
        soup,
        combined_text,
        details.map_links,
        expected_location=expected_location,
    )[:8]

    details.services_or_products = extract_services_or_products(combined_text)[:18]
    details.local_terms = extract_local_terms(combined_text)[:15]

    issues = detail_gap_issues(details)
    return details, issues


def build_combined_text(soup: BeautifulSoup, text: str) -> str:
    parts: list[str] = []

    if text:
        parts.append(text)

    for attr in ["aria-label", "title", "alt", "placeholder", "content"]:
        for tag in soup.find_all(attrs={attr: True}):
            value = str(tag.get(attr) or "").strip()
            if value:
                parts.append(value)

    for meta_name in ["description", "keywords"]:
        meta = soup.find("meta", attrs={"name": meta_name})
        if meta and meta.get("content"):
            parts.append(str(meta.get("content")).strip())

    return "\n".join(parts)


def extract_emails(soup: BeautifulSoup, text: str) -> list[str]:
    emails: list[str] = []

    emails.extend(m.group(0) for m in EMAIL_RE.finditer(text or ""))

    for match in OBFUSCATED_EMAIL_RE.finditer(text or ""):
        emails.append(f"{match.group(1)}@{match.group(2)}.{match.group(3)}")

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if href.lower().startswith("mailto:"):
            email = href.split(":", 1)[1].split("?", 1)[0].strip()
            email = unquote(email)
            if EMAIL_RE.match(email):
                emails.append(email)

    return unique(emails)


def extract_phones(soup: BeautifulSoup, text: str) -> list[str]:
    phones: list[str] = []

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        lowered = href.lower()

        if lowered.startswith("tel:"):
            phones.append(href.split(":", 1)[1].split("?", 1)[0])

        if "wa.me/" in lowered or "api.whatsapp.com" in lowered:
            phones.extend(extract_phone_like_strings(href))

    phones.extend(extract_phone_like_strings(text or ""))

    return unique([normalize_phone(phone) for phone in phones if is_probable_phone(phone)])


def extract_phone_like_strings(value: str) -> list[str]:
    return [m.group(0) for m in PHONE_RE.finditer(value or "")]


def is_probable_phone(raw: str) -> bool:
    if not raw:
        return False

    value = raw.strip()
    digits = re.sub(r"\D+", "", value)

    if len(digits) < 7 or len(digits) > 16:
        return False

    if len(set(digits)) <= 1:
        return False

    # Avoid treating years/dates/times as phone numbers.
    if re.search(r"\b(19|20)\d{2}\b", value) and len(digits) <= 8:
        return False

    return True


def normalize_phone(raw: str) -> str:
    raw = unquote(str(raw or "")).strip()
    raw = re.sub(r"^(tel:|phone=)", "", raw, flags=re.I)
    raw = re.sub(r"\s+", " ", raw)
    raw = raw.strip(" ,;|")

    if raw.startswith("00"):
        raw = "+" + raw[2:]

    return raw


def extract_hours(text: str) -> list[str]:
    return unique([m.group(0).strip() for m in HOURS_RE.finditer(text or "")])


def extract_map_links(soup: BeautifulSoup) -> list[str]:
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        lowered = href.lower()

        if any(domain in lowered for domain in MAP_DOMAINS):
            links.append(href)

    for iframe in soup.find_all("iframe", src=True):
        src = str(iframe.get("src") or "").strip()
        lowered = src.lower()

        if any(domain in lowered for domain in MAP_DOMAINS):
            links.append(src)

    return unique(links)


def extract_social_links(soup: BeautifulSoup) -> list[str]:
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        lowered = href.lower()

        if any(domain in lowered for domain in SOCIAL_DOMAINS):
            links.append(href)

    return unique(links)


def extract_ctas(soup: BeautifulSoup) -> list[str]:
    ctas: list[str] = []

    for tag in soup.find_all(["a", "button"]):
        label = tag.get_text(" ", strip=True)
        aria = str(tag.get("aria-label") or "").strip()
        title = str(tag.get("title") or "").strip()
        combined = " ".join(part for part in [label, aria, title] if part)

        if combined and CTA_RE.search(combined):
            ctas.append(combined[:120])

    return unique(ctas)


def extract_business_name_candidates(soup: BeautifulSoup) -> list[str]:
    candidates: list[str] = []

    title = soup.find("title")
    if title:
        candidates.append(title.get_text(" ", strip=True)[:120])

    for selector in ["h1", "[class*=logo]", "[class*=brand]", "[id*=logo]", "[id*=brand]"]:
        for tag in soup.select(selector):
            value = tag.get_text(" ", strip=True)
            if value and 2 <= len(value) <= 120:
                candidates.append(value[:120])

    for meta_prop in ["og:site_name", "og:title"]:
        meta = soup.find("meta", attrs={"property": meta_prop})
        if meta and meta.get("content"):
            candidates.append(str(meta.get("content")).strip()[:120])

    return unique(candidates)


def extract_addresses(
    soup: BeautifulSoup,
    text: str,
    map_links: list[str],
    expected_location: str = "",
) -> list[str]:
    scored: list[tuple[int, str]] = []

    raw_candidates: list[tuple[str, bool]] = []

    for candidate in extract_addresses_from_json_ld(soup):
        raw_candidates.append((candidate, True))

    for candidate in extract_addresses_from_microdata(soup):
        raw_candidates.append((candidate, True))

    for candidate in extract_addresses_from_labels(text):
        raw_candidates.append((candidate, True))

    for candidate in extract_addresses_from_expected_location(text, expected_location):
        raw_candidates.append((candidate, True))

    for candidate in extract_address_like_lines(text):
        raw_candidates.append((candidate, False))

    for candidate in extract_addresses_near_map_links(soup):
        raw_candidates.append((candidate, True))

    for candidate in extract_address_from_map_urls(map_links):
        raw_candidates.append((candidate, True))

    for candidate, label_context in raw_candidates:
        cleaned = clean_address(candidate)
        score = address_score(
            cleaned,
            expected_location=expected_location,
            allow_label_context=label_context,
        )

        if score >= 5:
            scored.append((score, cleaned))

    scored.sort(key=lambda item: item[0], reverse=True)

    return unique([candidate for _, candidate in scored])


def extract_addresses_from_json_ld(soup: BeautifulSoup) -> list[str]:
    addresses: list[str] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
        except Exception:  # noqa: BLE001
            continue

        addresses.extend(collect_addresses_from_schema(data))

    return addresses


def collect_addresses_from_schema(data) -> list[str]:
    addresses: list[str] = []

    if isinstance(data, dict):
        address = data.get("address")

        if isinstance(address, str):
            addresses.append(address)

        elif isinstance(address, dict):
            parts = [
                address.get("streetAddress"),
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("postalCode"),
                address.get("addressCountry"),
            ]
            joined = ", ".join(str(part).strip() for part in parts if part)
            if joined:
                addresses.append(joined)

        for value in data.values():
            addresses.extend(collect_addresses_from_schema(value))

    elif isinstance(data, list):
        for item in data:
            addresses.extend(collect_addresses_from_schema(item))

    return addresses


def extract_addresses_from_microdata(soup: BeautifulSoup) -> list[str]:
    addresses: list[str] = []

    selectors = [
        "[itemprop=address]",
        "[itemprop=streetAddress]",
        "[itemprop=addressLocality]",
        "[itemprop=addressRegion]",
        "[itemprop=postalCode]",
        "[itemprop=addressCountry]",
        "address",
    ]

    for selector in selectors:
        for tag in soup.select(selector):
            value = tag.get_text(" ", strip=True)
            if value:
                addresses.append(value)

    return addresses


def extract_addresses_from_labels(text: str) -> list[str]:
    lines = normalize_lines(text)
    addresses: list[str] = []

    for i, line in enumerate(lines):
        if not ADDRESS_LABEL_RE.search(line):
            continue

        nearby = lines[i + 1 : i + 6]

        for candidate in nearby:
            if ADDRESS_STOP_RE.search(candidate):
                break

            if len(candidate) < 8:
                continue

            addresses.append(candidate)
            break

    return addresses


def extract_addresses_from_expected_location(text: str, expected_location: str) -> list[str]:
    if not expected_location:
        return []

    lines = normalize_lines(text)
    candidates: list[str] = []

    location_terms = extract_location_terms(expected_location)

    if not location_terms:
        return []

    for line in lines:
        lowered = line.lower()

        if not any(term in lowered for term in location_terms):
            continue

        if len(line) < 8 or len(line) > 220:
            continue

        candidates.append(line)

    return candidates


def extract_address_like_lines(text: str) -> list[str]:
    lines = normalize_lines(text)
    candidates: list[str] = []

    for line in lines:
        if len(line) > 220:
            continue

        if ADDRESS_HINT_RE.search(line) or line.count(",") >= 2:
            candidates.append(line)

    # Merge only short neighboring lines, not long paragraphs.
    for i in range(len(lines) - 1):
        if len(lines[i]) > 90 or len(lines[i + 1]) > 90:
            continue

        merged = f"{lines[i]}, {lines[i + 1]}"

        if ADDRESS_HINT_RE.search(merged) or merged.count(",") >= 2:
            candidates.append(merged)

    return candidates


def extract_addresses_near_map_links(soup: BeautifulSoup) -> list[str]:
    candidates: list[str] = []

    for tag in soup.find_all(["a", "iframe"]):
        href = str(tag.get("href") or tag.get("src") or "").strip().lower()

        if not href or not any(domain in href for domain in MAP_DOMAINS):
            continue

        parent = tag.find_parent()
        if not parent:
            continue

        ancestors = [
            parent,
            parent.find_parent(),
            parent.find_parent().find_parent() if parent.find_parent() else None,
        ]

        for ancestor in ancestors:
            if not ancestor:
                continue

            text = ancestor.get_text("\n", strip=True)
            for line in normalize_lines(text):
                if len(line) >= 8:
                    candidates.append(line)

    return candidates


def extract_address_from_map_urls(map_links: list[str]) -> list[str]:
    candidates: list[str] = []

    for link in map_links:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)

        for key in ["q", "query", "destination", "daddr"]:
            for value in query.get(key, []):
                decoded = unquote(value).strip()
                if decoded:
                    candidates.append(decoded)

        path = unquote(parsed.path or "")
        match = re.search(r"/place/([^/]+)", path)
        if match:
            candidate = match.group(1).replace("+", " ").strip()
            candidates.append(candidate)

    return candidates


def address_score(value: str, expected_location: str = "", allow_label_context: bool = False) -> int:
    text = clean_address(value)
    lowered = text.lower()

    if not text or len(text) < 8 or len(text) > 220:
        return -10

    if EMAIL_RE.search(text):
        return -10

    if HOURS_RE.search(text):
        return -10

    if re.search(r"https?://|www\.", lowered):
        return -10

    score = 0

    location_terms = extract_location_terms(expected_location)

    if location_terms and any(term in lowered for term in location_terms):
        score += 4

    comma_count = text.count(",")

    if comma_count >= 1:
        score += 1

    if comma_count >= 2:
        score += 2

    if ADDRESS_HINT_RE.search(text):
        score += 2

    if any(ch.isdigit() for ch in text):
        score += 1

    if allow_label_context:
        score += 3

    word_count = len(re.findall(r"[A-Za-z]+", text))

    # Generic paragraph penalties.
    if word_count > 18:
        score -= 3

    if text.endswith("."):
        score -= 2

    if ADDRESS_NOISE_RE.search(text):
        score -= 2

    if "·" in text or "•" in text:
        score -= 2

    # Category-like fragments are often not addresses:
    # Example: "Marilao · Barber/Salon"
    if "/" in text and comma_count <= 1 and not any(ch.isdigit() for ch in text):
        score -= 2

    return score


def extract_location_terms(expected_location: str) -> list[str]:
    if not expected_location:
        return []

    raw_terms = re.split(r"[,|/\-–—]+|\s+", expected_location.lower())

    terms = []
    for term in raw_terms:
        clean = re.sub(r"[^a-z0-9]", "", term).strip()
        if len(clean) >= 3:
            terms.append(clean)

    return unique(terms)


def clean_address(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(
        r"^(address|location|visit us|where to find us|find us)\s*[:\-–—]?\s*",
        "",
        text,
        flags=re.I,
    )
    text = text.strip(" ,;|-–—")
    return text


def normalize_lines(text: str) -> list[str]:
    raw = re.split(r"[\n\r]+", text or "")
    lines: list[str] = []

    for line in raw:
        clean = re.sub(r"\s+", " ", line).strip()
        clean = clean.strip("•·|")
        if clean:
            lines.append(clean)

    return lines


def extract_services_or_products(text: str) -> list[str]:
    candidates: list[str] = []

    for line in normalize_lines(text):
        if 5 <= len(line) <= 130 and SERVICE_HINTS.search(line):
            candidates.append(line)

    return unique(candidates)


def extract_local_terms(text: str) -> list[str]:
    candidates: list[str] = []

    for line in normalize_lines(text):
        if 5 <= len(line) <= 180 and ADDRESS_HINT_RE.search(line):
            candidates.append(line)

    return unique(candidates)


def detail_gap_issues(details: BusinessDetails) -> list[Issue]:
    issues: list[Issue] = []

    if not details.phones and not details.emails and not details.ctas:
        issues.append(
            Issue(
                id="local-contact-missing",
                priority=Priority.high,
                dimension="Local business essentials",
                issue="No clear contact method detected",
                evidence="No phone number, email, or strong contact CTA was found in the page text/links.",
                why_it_matters=(
                    "A local business page must make it easy to call, message, book, order, or visit. "
                    "Missing contact information blocks conversions."
                ),
                suggested_fix="Add a visible phone number, WhatsApp/call CTA, booking link, and/or email in the hero and footer.",
                source="business_detail_extractor",
            )
        )

    if not details.addresses and not details.map_links:
        issues.append(
            Issue(
                id="local-address-missing",
                priority=Priority.high,
                dimension="Local business essentials",
                issue="No address or directions link detected",
                evidence="No address-like line or maps/directions link was detected.",
                why_it_matters=(
                    "For local businesses, location is a trust signal and a practical requirement "
                    "for visits and local SEO."
                ),
                suggested_fix="Add full address, nearby landmark if useful, and a Google Maps/Waze directions link.",
                source="business_detail_extractor",
            )
        )

    if not details.hours:
        issues.append(
            Issue(
                id="local-hours-missing",
                priority=Priority.medium,
                dimension="Local business essentials",
                issue="Opening hours not detected",
                evidence="No clear operating hours were found.",
                why_it_matters=(
                    "Hours reduce friction and prevent wrong expectations for walk-ins, orders, bookings, and visits."
                ),
                suggested_fix="Add current opening hours and mention whether walk-ins/appointments are accepted.",
                source="business_detail_extractor",
            )
        )

    if not details.services_or_products:
        issues.append(
            Issue(
                id="services-thin",
                priority=Priority.medium,
                dimension="Local business essentials",
                issue="Services/products are thin or not clearly listed",
                evidence="No clear service/menu/product section was detected.",
                why_it_matters="Visitors need to quickly know what the business actually sells or offers.",
                suggested_fix="Add specific services/products/menu items, not generic category descriptions.",
                source="business_detail_extractor",
            )
        )

    return issues


def extract_seo(html: str, text: str, business_type: str, location: str) -> tuple[SeoAudit, list[Issue]]:
    soup = BeautifulSoup(html or "", "lxml")
    audit = SeoAudit()

    title = soup.find("title")
    audit.title = title.get_text(" ", strip=True) if title else ""

    desc = soup.find("meta", attrs={"name": "description"})
    audit.meta_description = desc.get("content", "").strip() if desc else ""

    audit.h1 = [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:8]
    audit.h2 = [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:16]

    images = soup.find_all("img")
    audit.image_count = len(images)
    audit.images_missing_alt = sum(1 for img in images if not (img.get("alt") or "").strip())

    audit.og_tags = {
        (m.get("property") or m.get("name") or ""): m.get("content", "")
        for m in soup.find_all("meta")
        if (m.get("property") or m.get("name") or "").startswith("og:")
    }

    schema_types = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
            collect_schema_types(data, schema_types)
        except Exception:  # noqa: BLE001
            continue

    audit.schema_types = unique(schema_types)
    audit.has_local_business_schema = any(
        "LocalBusiness" in typ or typ in {"Restaurant", "Store", "BeautySalon", "AutoRepair"}
        for typ in audit.schema_types
    )

    issues: list[Issue] = []

    if not audit.title or len(audit.title) < 15:
        issues.append(
            Issue(
                id="seo-title-missing",
                priority=Priority.low,
                dimension="SEO/local search",
                issue="Title tag is missing or too thin",
                evidence=f'Title: {audit.title or "[missing]"}',
                why_it_matters="A clear title helps search engines and link previews understand the business.",
                suggested_fix="Add a title with business name, category, and city/area.",
                source="seo_auditor",
            )
        )

    if not audit.meta_description or len(audit.meta_description) < 50:
        issues.append(
            Issue(
                id="seo-meta-description-thin",
                priority=Priority.low,
                dimension="SEO/local search",
                issue="Meta description is missing or too short",
                evidence=f'Meta description: {audit.meta_description or "[missing]"}',
                why_it_matters="A specific description improves search previews and reduces generic AI feel.",
                suggested_fix="Add a concise description with services, location, and primary CTA.",
                source="seo_auditor",
            )
        )

    if len(audit.h1) != 1:
        issues.append(
            Issue(
                id="seo-h1-structure",
                priority=Priority.low,
                dimension="SEO/local search",
                issue="H1 structure is not ideal",
                evidence=f"Detected {len(audit.h1)} H1 headings.",
                why_it_matters="A single clear H1 helps structure the page and makes the page easier to understand.",
                suggested_fix="Use one H1 that names the business/category clearly, then H2s for services, location, hours, testimonials, etc.",
                source="seo_auditor",
            )
        )

    if audit.image_count and audit.images_missing_alt / max(audit.image_count, 1) > 0.5:
        issues.append(
            Issue(
                id="seo-alt-text",
                priority=Priority.low,
                dimension="SEO/local search",
                issue="Many images are missing alt text",
                evidence=f"{audit.images_missing_alt}/{audit.image_count} images missing alt text.",
                why_it_matters=(
                    "Alt text improves accessibility and gives local/search context for real business photos."
                ),
                suggested_fix="Add short alt text describing the actual business, service, or product shown.",
                source="seo_auditor",
            )
        )

    if not audit.has_local_business_schema:
        issues.append(
            Issue(
                id="seo-local-schema-missing",
                priority=Priority.medium,
                dimension="SEO/local search",
                issue="LocalBusiness structured data not detected",
                evidence=f'Detected schema types: {audit.schema_types or "none"}',
                why_it_matters=(
                    "Structured data helps search engines understand local business details like address, phone, hours, and category."
                ),
                suggested_fix="Add JSON-LD LocalBusiness schema using verified business name, address, phone, hours, and category.",
                source="seo_auditor",
            )
        )

    combined = f'{audit.title} {audit.meta_description} {" ".join(audit.h1)} {text[:2000]}'.lower()

    if business_type and business_type.lower() not in combined:
        issues.append(
            Issue(
                id="seo-business-category-gap",
                priority=Priority.medium,
                dimension="SEO/local search",
                issue="Business category is not clearly grounded in copy/metadata",
                evidence=f"Expected category: {business_type}",
                why_it_matters="Generated pages should clearly say what the business does in customer language.",
                suggested_fix="Mention the real business category naturally in the hero, title, meta description, and service section.",
                source="seo_auditor",
            )
        )

    if location and location.lower() not in combined:
        issues.append(
            Issue(
                id="seo-location-gap",
                priority=Priority.medium,
                dimension="SEO/local search",
                issue="Location/city is not clearly grounded in copy/metadata",
                evidence=f"Expected location: {location}",
                why_it_matters="Local pages need city/area signals for trust and search relevance.",
                suggested_fix="Mention the verified city/area in the hero, title/meta, address section, and directions CTA.",
                source="seo_auditor",
            )
        )

    return audit, issues


def collect_schema_types(data, out: list[str]) -> None:
    if isinstance(data, dict):
        typ = data.get("@type")

        if isinstance(typ, str):
            out.append(typ)
        elif isinstance(typ, list):
            out.extend(str(x) for x in typ)

        for value in data.values():
            collect_schema_types(value, out)

    elif isinstance(data, list):
        for item in data:
            collect_schema_types(item, out)


def unique(items: list[str]) -> list[str]:
    seen = set()
    result = []

    for item in items:
        clean = re.sub(r"\s+", " ", str(item)).strip()

        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)

    return result