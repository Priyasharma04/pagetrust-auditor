from __future__ import annotations

import json
import re
from collections import Counter

import httpx

from app.core.config import get_settings
from app.models.schemas import BusinessDetails, Issue, Priority

CITY_WORDS = ['manila', 'makati', 'cebu', 'davao', 'quezon city', 'taguig', 'pasig', 'mandaluyong', 'pasay', 'caloocan', 'baguio', 'iloilo']


def rule_based_contradiction_issues(text: str, details: BusinessDetails, expected_location: str = '') -> list[Issue]:
    issues: list[Issue] = []
    lowered = text.lower()

    says_247 = bool(re.search(r'\b(24\s*/\s*7|24\s*hours?|open\s+24|always open)\b', lowered))
    limited_hours = bool(re.search(r'\b(mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.*\b\d{1,2}\s*(am|pm)?\s*(?:-|to|–)\s*\d{1,2}', lowered, re.I))
    if says_247 and limited_hours:
        issues.append(Issue(
            id='contradiction-247-hours',
            priority=Priority.high,
            dimension='Contradictions',
            issue='Operating hours may contradict “24/7” or “24 hours” copy',
            evidence='Page contains both 24/7-style wording and limited day/hour ranges.',
            why_it_matters='Wrong hours create immediate customer frustration and reduce trust in a local business listing.',
            suggested_fix='Confirm actual hours with the business owner and use one consistent operating-hours statement across hero, footer, schema, and CTA sections.',
            source='contradiction_rules',
        ))

    if re.search(r'\bwalk[- ]?ins? welcome\b', lowered) and re.search(r'\bappointment only\b', lowered):
        issues.append(Issue(
            id='contradiction-walkin-appointment',
            priority=Priority.high,
            dimension='Contradictions',
            issue='Walk-in and appointment-only messaging conflict',
            evidence='The page mentions both walk-ins welcome and appointment only.',
            why_it_matters='Customers need clear instructions on whether they can visit immediately or must book.',
            suggested_fix='Clarify whether walk-ins are accepted, appointment is preferred, or appointment is required for specific services.',
            source='contradiction_rules',
        ))

    if re.search(r'\bfree delivery\b', lowered) and re.search(r'\bdelivery fee|paid delivery|fee applies|additional delivery\b', lowered):
        issues.append(Issue(
            id='contradiction-delivery-price',
            priority=Priority.medium,
            dimension='Contradictions',
            issue='Delivery pricing may be inconsistent',
            evidence='The page appears to mention both free delivery and delivery fees.',
            why_it_matters='Pricing contradictions create support issues and lower conversion confidence.',
            suggested_fix='Specify delivery terms: free within area, minimum order, delivery fee range, or pickup-only.',
            source='contradiction_rules',
        ))

    if re.search(r'\btransparent pricing|clear pricing|affordable packages\b', lowered) and not re.search(r'₱|php|price|starts at|from \d|\d+\s*pesos', lowered):
        issues.append(Issue(
            id='claim-pricing-without-prices',
            priority=Priority.low,
            dimension='Contradictions',
            issue='Pricing language appears without actual pricing details',
            evidence='The copy mentions transparent/affordable pricing but no price/menu/range was detected.',
            why_it_matters='This is not always wrong, but it can make generated copy feel vague if no real pricing exists.',
            suggested_fix='Either add owner-approved price ranges/menu items or remove pricing claims and use “contact for current pricing”.',
            source='contradiction_rules',
        ))

    cities_found = [city for city in CITY_WORDS if city in lowered]
    if expected_location and expected_location.lower() not in lowered and cities_found:
        issues.append(Issue(
            id='contradiction-location-expected',
            priority=Priority.high,
            dimension='Contradictions',
            issue='Detected location may not match expected location',
            evidence=f'Expected: {expected_location}; detected city terms: {", ".join(cities_found[:5])}',
            why_it_matters='Wrong city/address can send customers to the wrong place and damage trust.',
            suggested_fix='Confirm the exact address and city from creator field notes before publishing.',
            source='contradiction_rules',
        ))
    elif len(set(cities_found)) > 2:
        issues.append(Issue(
            id='contradiction-multiple-cities',
            priority=Priority.medium,
            dimension='Contradictions',
            issue='Multiple cities detected; location may be unclear',
            evidence=', '.join(cities_found[:8]),
            why_it_matters='Local businesses usually need one clear physical location or defined service area.',
            suggested_fix='Clarify primary address and service area. Remove unrelated city names unless they are actual service areas.',
            source='contradiction_rules',
        ))
    return issues


async def llm_contradiction_issues(text: str, business_type: str, location: str) -> list[Issue]:
    settings = get_settings()
    if not settings.openai_api_key:
        return []
    sample = text[:12000]
    prompt = f"""
You are auditing an AI-generated local business website before publishing.
Return only valid JSON array. Each item must have: priority(high|medium|low), issue, evidence, why_it_matters, suggested_fix.
Find factual contradictions, unsupported claims, mismatched business language, and local-business gaps.
Business type: {business_type or 'unknown'}
Expected location: {location or 'unknown'}
Page text:
{sample}
""".strip()
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {settings.openai_api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': settings.openai_model,
                    'messages': [
                        {'role': 'system', 'content': 'Return strict JSON only. Do not include markdown.'},
                        {'role': 'user', 'content': prompt},
                    ],
                    'temperature': 0.1,
                },
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            data = json.loads(content)
            issues: list[Issue] = []
            for idx, item in enumerate(data[:12]):
                priority = str(item.get('priority', 'medium')).lower()
                if priority not in {'high', 'medium', 'low'}:
                    priority = 'medium'
                issues.append(Issue(
                    id=f'llm-contradiction-{idx}',
                    priority=Priority(priority),
                    dimension='LLM/NLI review',
                    issue=str(item.get('issue', 'Potential issue'))[:180],
                    evidence=str(item.get('evidence', ''))[:320],
                    why_it_matters=str(item.get('why_it_matters', 'This may reduce trust or accuracy.'))[:320],
                    suggested_fix=str(item.get('suggested_fix', 'Verify with the business owner before publishing.'))[:420],
                    source='llm_nli',
                ))
            return issues
    except Exception:
        return []
