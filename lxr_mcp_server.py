#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Brookhaven National Laboratory
"""
LXR Code Browser MCP Server.

Provides cross-referenced code navigation across the EIC codebase via the
LXR web interface at eic-code-browser.sdcc.bnl.gov. Parses HTML responses
into structured tool results.

Tools:
  lxr_ident    — Find where a symbol is defined and referenced across all repos
  lxr_search   — Ripgrep-powered text/regex search across the entire codebase
  lxr_source   — Read a source file with line numbers
  lxr_list     — Browse directory contents

Run as stdio MCP server:
    python lxr_mcp_server.py
"""

import html
import os
import re

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

LXR_BASE = os.environ.get(
    "LXR_BASE_URL", "https://eic-code-browser.sdcc.bnl.gov/lxr"
)

mcp = FastMCP(
    "lxr-code-browser",
    instructions=(
        "EIC LXR Code Browser — cross-referenced navigation across 55+ EIC repositories. "
        "Use lxr_ident to find where symbols are defined and used. "
        "Use lxr_search for regex/text search across the full codebase. "
        "Use lxr_source to read source files. Use lxr_list to browse directories."
    ),
)

_http = httpx.Client(timeout=30, follow_redirects=True)


def _fetch(path: str, params: dict = None) -> BeautifulSoup:
    """Fetch an LXR page and parse it."""
    url = f"{LXR_BASE}/{path.lstrip('/')}"
    resp = _http.get(url, params=params)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _text(el) -> str:
    """Extract clean text from an element."""
    return el.get_text(strip=True) if el else ""


# ── lxr_ident ──────────────────────────────────────────────────────────────


@mcp.tool()
def lxr_ident(symbol: str, definitions_only: bool = False) -> str:
    """Find where a symbol (function, class, variable, typedef) is defined and referenced.

    Searches the LXR cross-reference index across all 55+ EIC repositories.
    Returns definitions (with type and member-of info) and references with
    file paths and line numbers.

    Args:
        symbol: Exact identifier name (case-sensitive). E.g. "CalorimeterHitDigi".
        definitions_only: If True, return only definitions, not references.
    """
    params = {"_i": symbol, "v": "master"}
    if definitions_only:
        params["_identdefonly"] = "1"
    soup = _fetch("ident", params)

    lines = []

    # Definitions
    def_table = soup.find("table", class_="identdef")
    if def_table:
        defs = []
        for row in def_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 4:
                dtype = _text(cells[0])
                member_of = _text(cells[1])
                fpath = _text(cells[2])
                line_no = _text(cells[3])
                entry = f"  {dtype}"
                if member_of:
                    entry += f" ({member_of})"
                entry += f"  {fpath}:{line_no}"
                defs.append(entry)
        if defs:
            lines.append(f"Definitions of '{symbol}' ({len(defs)}):")
            lines.extend(defs)
        else:
            lines.append(f"No definitions found for '{symbol}'.")
    else:
        lines.append(f"No definitions found for '{symbol}'.")

    # References
    if not definitions_only:
        ref_table = soup.find("table", class_="identref")
        if ref_table:
            refs = []
            current_file = ""
            for row in ref_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    file_cell = cells[0]
                    line_cell = cells[1]
                    # File cell may be empty (searchfilevoid) for continuation
                    ftext = _text(file_cell)
                    if ftext and ftext != "\xa0":
                        current_file = ftext
                    line_no = _text(line_cell)
                    if line_no and current_file:
                        refs.append(f"  {current_file}:{line_no}")
            if refs:
                lines.append(f"\nReferences to '{symbol}' ({len(refs)}):")
                lines.extend(refs)
            else:
                lines.append(f"\nNo references found for '{symbol}'.")
        else:
            lines.append(f"\nNo references found for '{symbol}'.")

    return "\n".join(lines)


# ── lxr_search ─────────────────────────────────────────────────────────────


@mcp.tool()
def lxr_search(
    pattern: str,
    file_pattern: str = "",
    case_sensitive: bool = True,
    max_results: int = 50,
) -> str:
    """Search the entire EIC codebase using ripgrep.

    Searches across all 55+ indexed repositories for text or regex patterns.

    Args:
        pattern: Search pattern (regex supported). E.g. "JApplication", "def\\s+init".
        file_pattern: Optional filename glob filter. E.g. "*.h", "*.py", "CMakeLists.txt".
        case_sensitive: Case-sensitive search (default True).
        max_results: Maximum results to return (default 50, max 200).
    """
    params = {"_string": pattern, "v": "master"}
    if file_pattern:
        params["_filestring"] = file_pattern
    if case_sensitive:
        params["_casesensitive"] = "1"
    soup = _fetch("search", params)

    # Extract occurrence count
    count_text = ""
    for p in soup.find_all("p"):
        text = _text(p)
        if "occurrences found" in text:
            count_text = text
            break

    # Parse results table
    ref_table = soup.find("table", class_="searchref")
    if not ref_table:
        return count_text or f"No results for '{pattern}'."

    results = []
    current_file = ""
    max_results = min(max_results, 200)

    for row in ref_table.find("tbody", recursive=False).find_all("tr") if ref_table.find("tbody") else ref_table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        file_cell = cells[0]
        line_cell = cells[1]
        text_cell = cells[2]

        ftext = _text(file_cell)
        if ftext and ftext != "\xa0":
            current_file = ftext

        line_no = _text(line_cell)
        # Get the text content, stripping HTML tags but preserving the text
        match_text = _text(text_cell)

        if line_no and current_file:
            results.append(f"  {current_file}:{line_no}  {match_text}")

        if len(results) >= max_results:
            break

    lines = [count_text] if count_text else []
    if results:
        lines.append(f"Results for '{pattern}':")
        lines.extend(results)
        if len(results) >= max_results:
            lines.append(f"  ... (truncated at {max_results})")
    else:
        lines.append(f"No results for '{pattern}'.")

    return "\n".join(lines)


# ── lxr_source ─────────────────────────────────────────────────────────────


@mcp.tool()
def lxr_source(
    path: str,
    start_line: int = 1,
    end_line: int = 0,
) -> str:
    """Read a source file from the EIC codebase with line numbers.

    Args:
        path: File path relative to repo root. E.g. "EICrecon/src/algorithms/calorimetry/CalorimeterHitDigi.h".
        start_line: First line to return (default 1).
        end_line: Last line to return (0 = entire file, default 0). Use to read specific ranges.
    """
    soup = _fetch(f"source/{path.lstrip('/')}")

    pre = soup.find("pre", class_="filecontent")
    if not pre:
        return f"File not found or not a source file: {path}"

    # Parse line-numbered source using bs4.
    # Each line: <a class='fline' name='NNNN'>NNNN</a> ...content until next fline...
    lines = []
    for anchor in pre.find_all("a", class_="fline"):
        line_no = int(anchor.get_text())
        content_parts = []
        for sib in anchor.next_siblings:
            if hasattr(sib, "name") and sib.name == "a" and "fline" in (sib.get("class") or []):
                break
            content_parts.append(sib.get_text() if hasattr(sib, "get_text") else str(sib))
        content = "".join(content_parts).rstrip("\n")
        lines.append((line_no, content))

    if not lines:
        return f"Could not parse source content for: {path}"

    # Apply range filter
    if end_line > 0:
        lines = [(n, c) for n, c in lines if start_line <= n <= end_line]
    elif start_line > 1:
        lines = [(n, c) for n, c in lines if n >= start_line]

    if not lines:
        return f"No lines in range {start_line}-{end_line} for: {path}"

    # Format with line numbers
    width = len(str(lines[-1][0]))
    output = [f"{n:{width}d}  {c}" for n, c in lines]
    header = f"{path} (lines {lines[0][0]}-{lines[-1][0]})"
    return header + "\n" + "\n".join(output)


# ── lxr_list ───────────────────────────────────────────────────────────────


@mcp.tool()
def lxr_list(path: str = "") -> str:
    """Browse a directory in the EIC codebase.

    Lists files and subdirectories at the given path. Use to navigate
    the repository structure before reading specific files.

    Args:
        path: Directory path relative to repo root. E.g. "EICrecon/src/algorithms/".
              Empty string lists the top-level repos.
    """
    clean = path.strip("/") + "/" if path.strip("/") else ""
    soup = _fetch(f"source/{clean}")

    table = soup.find("table", class_="dircontent")
    if not table:
        return f"Not a directory or not found: {path}"

    entries = []
    tbody = table.find("tbody")
    if not tbody:
        return f"Empty directory: {path}"

    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        name_cell = cells[1]
        size_cell = cells[2]
        date_cell = cells[3]

        name = _text(name_cell)
        if name == "Parent directory":
            continue

        size = _text(size_cell)
        date = _text(date_cell)

        is_dir = name.endswith("/") or "dirfolder" in str(name_cell)
        kind = "dir " if is_dir else "file"
        size_str = "" if size == "-" else f"  {size}"

        entries.append(f"  {kind}  {name}{size_str}")

    if not entries:
        return f"Empty directory: {path}"

    header = f"/{clean}" if clean else "/ (top-level repos)"
    return header + "\n" + "\n".join(entries)


if __name__ == "__main__":
    mcp.run(transport="stdio")
