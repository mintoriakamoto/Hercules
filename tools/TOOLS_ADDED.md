# New Tools Added to Hercules

Simple, practical tools that extend Hercules' core capabilities. These follow the same "plain and easy" philosophy as existing tools like Read, Write, Edit, Grep, Glob.

## 1. find_tool.py - File Discovery

Search for files by name or pattern.

```python
from tools.find_tool import find_tool

# Find all Python files
find_tool(".", pattern="*.py")

# Find directories named 'tests'
find_tool(".", pattern="tests", file_type="dir")

# Limit results
find_tool("./src", pattern="*.py", max_results=50)
```

**Features:**
- Pattern matching (fnmatch)
- Filter by type (file, dir)
- Skip hidden files by default
- Structured output (list of paths, count, truncation info)

---

## 2. compare_files_tool.py - File Comparison & Line Counting

### Compare two files
```python
from tools.compare_files_tool import compare_files_tool

# Show unified diff
compare_files_tool("old.py", "new.py")

# More context
compare_files_tool("config.yaml", "config.new.yaml", context_lines=5)
```

**Output:** additions/deletions/changes, unified diff format

### Count file lines
```python
from tools.compare_files_tool import count_file_lines_tool

# Get line statistics
count_file_lines_tool("main.py")
```

**Output:** total lines, empty lines, comments, code lines

---

## 3. data_transform_tool.py - Data Format Conversion

Convert between JSON and CSV, format/validate JSON, query JSON.

```python
from tools.data_transform_tool import (
    json_to_csv_tool,
    csv_to_json_tool,
    json_format_tool,
    json_query_tool,
)

# Convert JSON array to CSV
json_to_csv_tool("data.json", "data.csv")

# Convert CSV to JSON
csv_to_json_tool("data.csv", "data.json")

# Format and validate JSON
json_format_tool("messy.json", sort_keys=True)

# Query JSON by key path
json_query_tool("data.json", "user.profile.email")
json_query_tool("items.json", "items.0.name")  # Array access
```

**Features:**
- Automatic column detection
- Dot-notation JSON queries
- Pretty-printing with customizable indentation
- Validation with line/column error reporting

---

## 4. dir_stats_tool.py - Directory Analysis

### Get directory statistics
```python
from tools.dir_stats_tool import directory_stats_tool

# Analyze directory
directory_stats_tool("/home/user/projects", max_depth=3)

# Include hidden files
directory_stats_tool(".", include_hidden=True)
```

**Output:**
- Total files/dirs/size
- Breakdown by file extension
- Breakdown by file type (source code, config, images, etc.)
- Largest 10 files
- Largest 5 directories

### Show directory tree
```python
from tools.dir_stats_tool import tree_view_tool

# ASCII tree view
tree_view_tool("./src", max_depth=3)
```

**Output:** Pretty-printed directory tree with file sizes

---

## Why These Tools?

| Tool | Solves | Replaces |
|------|--------|----------|
| find_tool | File discovery, no more `terminal_tool("find ...")` | Terminal-based find |
| compare_files_tool | File diffs in structured format | Manual diff reading |
| data_transform_tool | JSON/CSV conversions, queries | Python scripting or jq |
| dir_stats_tool | Directory analysis without calculations | Manual file iteration |

---

## Integration

All tools return structured dictionaries (no raw terminal output). Ready to integrate with:
- File tools API
- Hercules' tool registry
- Model-visible tools

Each tool includes:
- Error handling (file not found, permission denied)
- Path expansion (`~` support)
- Reasonable defaults (max_results=100, context_lines=3)
- Human-readable output alongside raw data

---

## Next Steps

1. Register tools in `tools/registry.py`
2. Add to Hercules' core toolset if desired
3. Extend with additional simple tools:
   - `sort_unique_tool` - Sort and deduplicate file lines
   - `text_stats_tool` - Word count, character analysis
   - `timestamp_tool` - Convert/format timestamps
   - `regex_tool` - Test regex patterns on files
   - `summary_tool` - Extract first/last N lines from files
