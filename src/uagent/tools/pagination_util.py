"""Pagination utility for search and grep tools."""

from __future__ import annotations

from typing import Any


def paginate_results(
    results: list[Any],
    page: int,
    max_results: int,
) -> tuple[list[Any], int, int, int]:
    """Paginate a list of results.

    Args:
        results: The full list of matched items.
        page: The requested page number (1-based).
        max_results: The maximum number of items per page.

    Returns:
        A tuple containing:
        - page_results: The sliced list of items for the current page.
        - page: The normalized current page number.
        - total_pages: The total number of pages.
        - total_results: The total number of items.
    """
    total_results = len(results)
    if total_results == 0:
        return [], 1, 1, 0

    total_pages = (total_results + max_results - 1) // max_results
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * max_results
    end_idx = start_idx + max_results
    page_results = results[start_idx:end_idx]

    return page_results, page, total_pages, total_results
