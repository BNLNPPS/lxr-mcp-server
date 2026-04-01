# LXR Code Browser MCP Server

MCP server for cross-referenced code navigation across the [EIC](https://www.bnl.gov/eic/) codebase, powered by the [LXR](https://eic-code-browser.sdcc.bnl.gov/lxr/source) engine at BNL.

Provides AI assistants with structured access to 55+ indexed EIC repositories — identifier cross-references, ripgrep search, source file reading, and directory browsing.

## Tools

| Tool | Description |
|------|-------------|
| `lxr_ident` | Find where a symbol (class, function, variable) is defined and referenced across all repos |
| `lxr_search` | Ripgrep-powered regex/text search across the entire codebase |
| `lxr_source` | Read source files with line numbers and optional range filtering |
| `lxr_list` | Browse directory contents and repository structure |

## Usage

### As a stdio MCP server

```bash
pip install -r requirements.txt
python lxr_mcp_server.py
```

### With Claude Code

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "lxr": {
      "command": "python",
      "args": ["/path/to/lxr-mcp-server/lxr_mcp_server.py"]
    }
  }
}
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LXR_BASE_URL` | `https://eic-code-browser.sdcc.bnl.gov/lxr` | LXR instance URL |

## Examples

**Find all definitions of a C++ class:**
```
lxr_ident(symbol="CalorimeterHitDigi", definitions_only=True)
```

**Search for a pattern in header files:**
```
lxr_search(pattern="InitPlugin", file_pattern="*.cc", max_results=20)
```

**Read specific lines of a source file:**
```
lxr_source(path="EICrecon/src/algorithms/calorimetry/CalorimeterHitDigi.h", start_line=40, end_line=60)
```

**List top-level repositories:**
```
lxr_list(path="")
```

## Architecture

Currently parses HTML from the LXR web interface. A future version could run directly on the LXR host and query the cross-reference index natively for better performance.

## License

Apache 2.0 — see [LICENSE](LICENSE).
