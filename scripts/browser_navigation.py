"""Shared navigation for production Chromium smokes, including collapsed mobile menus."""

SMOKE_FEATURES = (
    "dashboard",
    "agile",
    "experiments",
    "organizational",
    "operating",
    "review",
    "business_discovery",
    "people",
    "conversation_audio",
    "skills",
    "artifacts",
    "runs",
    "workflow_queue",
    "knowledge",
    "dashboard_design",
)


def open_view(page, name):
    """Open a named workspace destination and wait for its actual page heading."""
    nav = page.get_by_role(
        "navigation", name="Company views", exact=True, include_hidden=True
    )
    nav.wait_for(state="attached")
    if not nav.is_visible():
        page.get_by_role("button", name="Toggle company navigation", exact=True).click()
        nav.wait_for(state="visible")
    nav.get_by_role("button", name=name, exact=True).click()
    page.get_by_role("heading", name=name, level=1, exact=True).wait_for(
        state="visible"
    )


def open_business_section(page, name):
    """Select one business section without broad text matching or draft resets."""
    open_view(page, "Business research")
    tabs = page.get_by_role("navigation", name="Business research sections", exact=True)
    tabs.get_by_role("button", name=name, exact=True).click()
    if name == "Research & practice":
        page.get_by_label("Research title", exact=True).wait_for(state="visible")
    else:
        region = "Executive skill library" if name == "Executive skills" else name
        page.get_by_role("region", name=region, exact=True).wait_for(state="visible")
