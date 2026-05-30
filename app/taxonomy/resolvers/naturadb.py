import re
from urllib.parse import unquote

from .base import normalize_scientific_name_for_lookup
from .html_search import HtmlSearchResolver, search_page_html, search_page_taxonomy_id


def normalize_naturadb_slug(raw_slug):
    slug = unquote(raw_slug or '')
    slug = re.split(r'[?#]', slug, maxsplit=1)[0]
    slug = slug.replace('\\', '/').strip().strip('/').lower()
    segments = []
    for segment in slug.split('/'):
        normalized_segment = re.sub(r'[^a-z0-9\-]+', '-', segment)
        normalized_segment = re.sub(r'-{2,}', '-', normalized_segment).strip('-')
        if normalized_segment:
            segments.append(normalized_segment)
    return '/'.join(segments) or None


class NaturadbResolver(HtmlSearchResolver):
    mode = 'naturadb_search'
    patterns = [
        r'https?://(?:www\.)?naturadb\.de/pflanzen/([^"\'\s\?#]+)',
        r'/pflanzen/([^"\'\s\?#]+)',
        r'\/pflanzen\/([^\"\s\?#]+)',
        r'%2Fpflanzen%2F([^\s\?#]+)',
    ]

    def suggest_id(self, request):
        page_html = search_page_html(request.scientific_name, request.config)
        if not page_html:
            return None

        # Bevorzugt den ersten Treffer im naturaDB-Kartenlayout:
        # <a class="card__title no-link" href="/pflanzen/<slug>/">…</a>
        for anchor_match in re.finditer(r'<a\b[^>]*>', page_html, flags=re.IGNORECASE):
            anchor_tag = anchor_match.group(0)
            class_match = re.search(r'class\s*=\s*["\']([^"\']+)["\']', anchor_tag, flags=re.IGNORECASE)
            if not class_match:
                continue
            class_names = set((class_match.group(1) or '').lower().split())
            if 'card__title' not in class_names or 'no-link' not in class_names:
                continue
            href_match = re.search(r'href\s*=\s*["\'](/pflanzen/([^"\']+)?)["\']', anchor_tag, flags=re.IGNORECASE)
            if not href_match:
                continue
            href_value = (href_match.group(1) or '').strip()
            if not href_value.startswith('/pflanzen/'):
                continue
            candidate_slug = normalize_naturadb_slug(href_value[len('/pflanzen/'):])
            if candidate_slug:
                return candidate_slug

        requested_slug = re.sub(r'[^a-z0-9\-]+', '-', normalize_scientific_name_for_lookup(request.scientific_name) or '')
        requested_slug = re.sub(r'-{2,}', '-', requested_slug).strip('-')

        raw_id = search_page_taxonomy_id(request.scientific_name, request.config, self.patterns)
        if not raw_id:
            return None

        slug = normalize_naturadb_slug(raw_id)
        if requested_slug and slug == requested_slug:
            return slug

        # Suche auf Ergebnislisten bevorzugt nach exakt passendem wissenschaftlichen Namen.
        if requested_slug:
            exact_link_patterns = [
                r'href="/pflanzen/([^"\'\s\?#]+)"[^>]*>\s*([^<]+)\s*</a>',
                r'<a[^>]*href="/pflanzen/([^"\'\s\?#]+)"[^>]*>\s*([^<]+)\s*</a>',
            ]
            for link_pattern in exact_link_patterns:
                for match in re.finditer(link_pattern, page_html, flags=re.IGNORECASE):
                    candidate_slug = normalize_naturadb_slug(match.group(1))
                    candidate_text = (match.group(2) or '').strip()
                    normalized_candidate_text = (normalize_scientific_name_for_lookup(candidate_text) or '').strip().lower()
                    if normalized_candidate_text == (requested_slug.replace('-', ' ').strip().lower()):
                        return candidate_slug or None
                    if candidate_slug == requested_slug:
                        return candidate_slug or None

        return slug or None


def naturadb_taxonomy_id(scientific_name, config):
    from .base import ResolverRequest

    return NaturadbResolver().suggest_id(ResolverRequest('naturadb', scientific_name, config))
