from __future__ import annotations

import re
from functools import lru_cache

from app.models.schemas import Issue, Priority

GENERIC_CORPORATE_TERMS = [
    'innovative', 'scalable', 'human-centric', 'cutting-edge', 'best-in-class', 'synergy',
    'seamless solutions', 'transformative', 'empower', 'world-class', 'enterprise-grade',
    'data-driven', 'future-ready', 'holistic solutions', 'robust ecosystem', 'next-generation',
    'leveraging technology', 'unlock potential', 'tailored solutions', 'revolutionize',
]

CATEGORY_PROFILES = {
    'tire': 'tire tyre shop wheel alignment balancing vulcanizing replacement repair car motorcycle vehicle roadside service air pressure battery oil change brands sizes',
    'tyre': 'tire tyre shop wheel alignment balancing vulcanizing replacement repair car motorcycle vehicle roadside service air pressure battery oil change brands sizes',
    'salon': 'salon beauty hair haircut manicure pedicure nails spa massage facial waxing lashes makeup appointment walk in stylist treatment',
    'restaurant': 'restaurant food menu dishes meals breakfast lunch dinner dine in delivery takeout reservation cuisine coffee drinks chef',
    'clinic': 'clinic doctor dentist healthcare medical appointment consultation treatment patient checkup care pharmacy vaccination',
    'store': 'store shop products retail delivery order pickup customer service location brands stock items prices',
    'gym': 'gym fitness training workout membership coach personal training classes equipment strength cardio',
    'cafe': 'cafe coffee drinks pastry breakfast brunch dessert dine in takeaway beans menu',
}

CUSTOMER_LANGUAGE_HINTS = {
    'tire': ['tire', 'tyre', 'wheel', 'alignment', 'balancing', 'vulcanizing', 'vehicle', 'car', 'motorcycle'],
    'tyre': ['tire', 'tyre', 'wheel', 'alignment', 'balancing', 'vulcanizing', 'vehicle', 'car', 'motorcycle'],
    'salon': ['hair', 'beauty', 'salon', 'spa', 'massage', 'facial', 'nails', 'appointment'],
    'restaurant': ['menu', 'food', 'dish', 'meal', 'restaurant', 'dine', 'delivery', 'reservation'],
    'clinic': ['clinic', 'doctor', 'patient', 'consultation', 'appointment', 'treatment'],
}


def semantic_alignment_issues(text: str, business_type: str, location: str) -> list[Issue]:
    issues: list[Issue] = []
    lowered = text.lower()
    category_key = resolve_category_key(business_type)

    generic_hits = [term for term in GENERIC_CORPORATE_TERMS if term in lowered]
    if generic_hits:
        issues.append(Issue(
            id='semantic-generic-corporate-copy',
            priority=Priority.medium,
            dimension='Semantic alignment',
            issue='Copy uses generic/corporate language that may not fit a local business',
            evidence=', '.join(generic_hits[:12]),
            why_it_matters='Local business pages need concrete customer language. SaaS-style words can make a tire shop, salon, or restaurant feel AI-generated and less trustworthy.',
            suggested_fix='Replace vague adjectives with verified services, location, products, owner/team details, opening hours, brands, or customer use cases.',
            source='semantic_alignment',
        ))

    if category_key:
        hints = CUSTOMER_LANGUAGE_HINTS.get(category_key, [])
        hint_hits = [hint for hint in hints if re.search(rf'\b{re.escape(hint)}s?\b', lowered)]
        if len(hint_hits) < max(2, min(4, len(hints) // 3)):
            issues.append(Issue(
                id='semantic-category-language-gap',
                priority=Priority.medium,
                dimension='Semantic alignment',
                issue='Page language does not strongly match the stated business type',
                evidence=f'Business type: {business_type}; detected category-specific terms: {hint_hits or "very few"}',
                why_it_matters='Visitors should immediately understand what the business actually does. Weak category language is a common sign of generic AI copy.',
                suggested_fix=f'Add concrete terms customers expect for a {business_type}, including real services/products and local buying/booking details.',
                source='semantic_alignment',
            ))

    score_issue = embedding_similarity_issue(text, business_type, category_key)
    if score_issue:
        issues.append(score_issue)

    if location and location.lower() not in lowered:
        issues.append(Issue(
            id='semantic-location-grounding-gap',
            priority=Priority.medium,
            dimension='Semantic alignment',
            issue='Location is not sufficiently grounded in the page copy',
            evidence=f'Expected location: {location}',
            why_it_matters='For local businesses, place-specific copy increases trust and makes the page useful for nearby customers.',
            suggested_fix='Mention the verified area/city, nearby landmark, service area, or directions in natural customer-facing copy.',
            source='semantic_alignment',
        ))
    return issues


def resolve_category_key(business_type: str) -> str | None:
    lowered = (business_type or '').lower()
    for key in CATEGORY_PROFILES:
        if key in lowered:
            return key
    return None


def embedding_similarity_issue(text: str, business_type: str, category_key: str | None) -> Issue | None:
    """Optional embedding check. Falls back silently if model is unavailable.

    In production, mount/cache the model image instead of downloading at runtime.
    """
    if not business_type or not category_key:
        return None
    try:
        model = get_embedding_model()
        if not model:
            return None
        page_sample = text[:5000]
        profile = CATEGORY_PROFILES.get(category_key, business_type)
        embeddings = model.encode([page_sample, profile], normalize_embeddings=True)
        similarity = float(embeddings[0] @ embeddings[1])
        if similarity < 0.22:
            return Issue(
                id='semantic-embedding-low-fit',
                priority=Priority.medium,
                dimension='Semantic alignment',
                issue='Embedding similarity between page copy and business category is low',
                evidence=f'Business type: {business_type}; similarity: {similarity:.2f}',
                why_it_matters='Low semantic fit suggests the generated page may be too generic or off-category.',
                suggested_fix='Rewrite with concrete category-specific services, products, local details, and real customer tasks.',
                source='sentence_transformers',
            )
    except Exception:
        return None
    return None


@lru_cache(maxsize=1)
def get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    except Exception:
        return None
