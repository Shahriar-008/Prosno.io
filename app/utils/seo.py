"""Helpers for sitewide SEO defaults and crawl directives."""

from flask import current_app, request, url_for


INDEXABLE_ENDPOINTS = {
    "main.about",
    "main.contact",
    "main.generate",
    "main.index",
    "main.public_paper_view",
    "quiz.join_page",
}


def get_site_url():
    """Return the configured site origin or fall back to the active request."""
    configured = (current_app.config.get("SITE_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    return request.url_root.rstrip("/")


def absolute_url(path):
    """Build an absolute URL from a relative path."""
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{get_site_url()}{path}"


def default_meta_robots():
    """Return the default robots directive for the active request."""
    endpoint = request.endpoint or ""
    if request.method != "GET":
        return "noindex, nofollow"
    if endpoint == "quiz.join_page" and request.view_args and request.view_args.get("code"):
        return "noindex, nofollow"
    if endpoint in INDEXABLE_ENDPOINTS:
        return "index,follow"
    return "noindex, nofollow"


def default_og_image_url():
    """Return the absolute fallback social preview image URL."""
    filename = current_app.config.get("DEFAULT_OG_IMAGE", "img/og-default.svg")
    return absolute_url(url_for("static", filename=filename))


def should_send_noindex_header(response):
    """Decide whether the response should carry an X-Robots-Tag header."""
    mimetype = (response.mimetype or "").lower()

    if request.path in {"/robots.txt", "/sitemap.xml"}:
        return False

    if response.status_code >= 400:
        return True

    if mimetype == "text/html":
        return default_meta_robots().startswith("noindex")

    return True
