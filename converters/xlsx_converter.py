"""
XLSX to Markdown Converter - Enhanced Version
Extracts data from Excel spreadsheets with improved handling for:
  - Multi-row / merged-cell title blocks (auto-detects real header row)
  - Wide cross-tab / matrix layouts (detected and transposed to row-per-record)
  - Chart-only sheets (skipped cleanly)
  - Colour-coded RAG cells (resolved to text labels via Legend sheet if present)
  - Multi-line cell values (newlines flattened safely for pipe tables)
  - Frozen formula values (annotated so reader knows they are snapshots)
"""

from pathlib import Path
import logging
import re

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell_str(value) -> str:
    """Convert a cell value to a clean single-line string."""
    if value is None:
        return ""
    text = str(value).strip()
    # Flatten internal newlines so they don't break pipe-table rows
    text = re.sub(r'\r\n|\r|\n', ' ', text)
    # Escape pipe characters so they don't break table columns
    text = text.replace('|', '\\|')
    return text


def _is_empty_row(row_values: list) -> bool:
    return not any(v for v in row_values)


def _count_non_empty(grid: list) -> int:
    return sum(1 for row in grid for v in row if v)


def _sheet_is_chart_only(ws) -> bool:
    """
    Return True if the sheet looks like a chart/dashboard placeholder â€”
    i.e. the used range has very few non-empty cells relative to its size.
    openpyxl exposes chart objects but not their data; these sheets are noise.
    """
    used_cells = ws.max_row * ws.max_column
    if used_cells == 0:
        return True
    # Count non-empty cells in the used range (cap scan at 200 rows for speed)
    non_empty = 0
    scan_rows = min(ws.max_row, 200)
    for row in ws.iter_rows(min_row=1, max_row=scan_rows,
                             min_col=1, max_col=ws.max_column):
        for cell in row:
            if cell.value is not None and str(cell.value).strip():
                non_empty += 1
    density = non_empty / max(scan_rows * ws.max_column, 1)
    return density < 0.04   # less than 4% cells populated â†’ likely chart sheet


def _find_header_row(grid: list, max_search: int = 8) -> int:
    """
    Find the index (0-based) of the first row that looks like a real data header:
    - Has the most non-empty cells of any row in the first `max_search` rows, AND
    - Is followed by at least one row that also has non-empty cells.
    Falls back to 0 if nothing better is found.
    """
    best_idx = 0
    best_count = 0
    for i, row in enumerate(grid[:max_search]):
        non_empty = sum(1 for v in row if v)
        if non_empty > best_count:
            # Make sure there's at least one data row after it
            remaining = grid[i + 1:]
            if any(not _is_empty_row(r) for r in remaining[:5]):
                best_count = non_empty
                best_idx = i
    return best_idx


def _detect_wide_matrix(grid: list, header_idx: int) -> bool:
    """
    Return True if the sheet looks like a cross-tab / wide matrix where the
    columns ARE the meaningful dimension (e.g. initiatives, domains) and rows
    are role families.  Heuristic: column count significantly exceeds the
    number of non-empty data rows, AND column count > 15.
    """
    if not grid:
        return False
    header = grid[header_idx]
    col_count = sum(1 for v in header if v)
    data_rows = [r for r in grid[header_idx + 1:] if not _is_empty_row(r)]
    if col_count <= 15:
        return False
    # Wide if columns outnumber non-empty data rows by more than 2:1
    return col_count > len(data_rows) * 2 and col_count > 15


def _build_legend_map(wb) -> dict:
    """
    Scan all sheets for a 'Legend' or 'Instructions' sheet and build a
    colour-hex â†’ label mapping.  Very basic: looks for rows that have a
    colour in col A and text in col B.
    """
    legend = {}
    legend_sheet_names = [n for n in wb.sheetnames
                          if any(kw in n.lower()
                                 for kw in ('legend', 'instruction', 'guide'))]
    for name in legend_sheet_names:
        ws = wb[name]
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row,
                                min_col=1, max_col=3):
            cell = row[0]
            if cell.fill and cell.fill.fgColor:
                colour = cell.fill.fgColor.rgb  # e.g. 'FFFF0000'
                label_cell = row[1] if len(row) > 1 else None
                if label_cell and label_cell.value:
                    legend[colour] = _cell_str(label_cell.value)
    return legend


def _cell_colour_label(cell, legend: dict) -> str:
    """Return a [Label] annotation if the cell has a colour in the legend map."""
    if not legend:
        return ""
    try:
        rgb = cell.fill.fgColor.rgb if cell.fill and cell.fill.fgColor else None
        if rgb and rgb != '00000000' and rgb != 'FF000000' and rgb in legend:
            return f" [{legend[rgb]}]"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Sheet renderers
# ---------------------------------------------------------------------------

# Row count above which a sheet is summarised instead of fully dumped.
# LlamaIndex / LangChain loaders have no built-in cap; production RAG practice
# treats ~500 rows as the upper limit for full-fidelity table rendering and
# uses statistical summaries above that threshold.
_MAX_FULL_ROWS = 500

# Row count above which a sheet is skipped entirely.
# Sheets this large are raw operational data dumps (rosters, transaction logs,
# audit trails) that have no value as AI context and may contain PII.
# A clear notice is embedded in the output so the omission is transparent.
_MAX_SKIP_ROWS = 10000



# ---------------------------------------------------------------------------
# Smart summary engine  (replaces _render_summary_block for large flat sheets)
# ---------------------------------------------------------------------------

# Constants for the smart summary engine
_MAX_PIVOT_DIMS = 8     # max dimension columns to pivot
_MAX_PIVOT_ROWS = 30    # max rows per pivot table before capping
_MAX_CAT_VALUES = 30    # max unique values in enhanced-generic distributions


def _fmt_num(val, is_currency=False) -> str:
    """Format a number for markdown - comma thousands, 2dp for floats."""
    try:
        f = float(val)
        if f != f:      # NaN
            return "-"
        if is_currency:
            return f"${f:,.0f}"
        if f == int(f):
            return f"{int(f):,}"
        return f"{f:,.2f}"
    except (TypeError, ValueError):
        return str(val)


def _detect_currency_col(col_name: str) -> bool:
    """Heuristic: column name suggests a monetary value."""
    kw = ("cost", "spend", "budget", "revenue", "impact", "amount",
          "value", "sales", "profit", "loss", "fee", "price")
    return any(k in col_name.lower() for k in kw)


def _build_smart_summary(df, headers: list, total_rows: int,
                          sheet_name: str) -> list:
    """
    Main entry point for the smart summary engine.
    Replaces _render_summary_block for sheets with 501-10,000 rows.

    Routes to:
      - _render_pivot_summary    if numeric metric columns detected
      - _render_enhanced_generic if no live metrics (trackers, Jira exports)

    Always appends _render_quality_flags and _render_sample.
    Returns a list of markdown lines, or None on error (caller falls back).
    """
    try:
        import pandas as pd
    except ImportError:
        return None

    lines = []

    # -- 1. Classify columns --------------------------------------------------
    constant_cols = {}   # col -> single value
    metric_cols   = []   # numeric, sum > 0, not constant
    dim_cols      = []   # low-cardinality categorical (2-50 unique)
    text_cols     = []   # object with median length > 20 chars
    other_cols    = []   # everything else

    for col in df.columns:
        series = df[col]
        n_uniq = series.nunique(dropna=True)

        # Constant (same value every row)
        if n_uniq <= 1:
            val = series.dropna().iloc[0] if len(series.dropna()) > 0 else "(empty)"
            constant_cols[col] = str(val)
            continue

        # Numeric - use coerce so [NULL]/string cells become NaN
        # (errors='ignore' silently leaves column as object if ANY cell is non-numeric)
        num_series = pd.to_numeric(series, errors="coerce")
        frac_numeric = num_series.notna().sum() / max(len(series), 1)

        if frac_numeric >= 0.7:
            # Classify by sum, not cardinality - high-cardinality numerics
            # like total_impact (301 unique vals) are still metrics, not IDs
            col_sum = num_series.sum()
            if col_sum > 0:
                metric_cols.append(col)
            else:
                other_cols.append(col)
        else:
            # Categorical / text
            median_len = series.dropna().astype(str).str.len().median()
            if 2 <= n_uniq <= 50:
                dim_cols.append(col)
            elif median_len and median_len > 20:
                text_cols.append(col)
            else:
                other_cols.append(col)

    has_metrics = len(metric_cols) > 0

    # -- 2. Header block ------------------------------------------------------
    lines.append(f"> **{'Metric dataset' if has_metrics else 'Categorical dataset'}** "
                 f"- {total_rows:,} records x {len(headers)} columns.\n")

    if constant_cols:
        cv = ", ".join(f"{k}={v}" for k, v in list(constant_cols.items())[:6])
        if len(constant_cols) > 6:
            cv += f" (+{len(constant_cols)-6} more)"
        lines.append(f"> *Constant columns (same value every row - excluded from analysis): {cv}*\n")

    if metric_cols:
        metric_totals = []
        for mc in metric_cols[:4]:
            num_s = pd.to_numeric(df[mc], errors="coerce")
            total = num_s.sum()
            curr  = _detect_currency_col(mc)
            metric_totals.append(f"{mc} (total: {_fmt_num(total, curr)})")
        lines.append(f"> *Metrics: {', '.join(metric_totals)}*\n")

    if dim_cols:
        dim_info = []
        for dc in dim_cols[:8]:
            n = df[dc].nunique(dropna=True)
            dim_info.append(f"{dc} ({n} values)")
        lines.append(f"> *Dimensions: {', '.join(dim_info)}*\n")

    lines.append("\n")

    # -- 3. Branch: pivot summary OR enhanced generic -------------------------
    if has_metrics:
        lines += _render_pivot_summary(df, metric_cols, dim_cols)
    else:
        lines += _render_enhanced_generic(df, dim_cols, text_cols)

    # -- 4. Quality flags -----------------------------------------------------
    lines += _render_quality_flags(df, metric_cols, dim_cols)

    # -- 5. Sample rows - three-point coverage --------------------------------
    lines += _render_sample(df, headers)

    return lines


def _render_pivot_summary(df, metric_cols: list, dim_cols: list) -> list:
    """Pre-aggregate every dimension x every metric. The core new value."""
    import pandas as pd

    lines = ["---\n", "### Pre-aggregated pivot tables\n\n"]
    lines.append("*Python pre-computes every group-by so the AI does not have to.*\n\n")

    dims_sorted = sorted(dim_cols, key=lambda c: df[c].nunique())[:_MAX_PIVOT_DIMS]
    metrics = metric_cols[:4]
    currency_flags = [_detect_currency_col(m) for m in metrics]

    df_agg = df.copy()
    for _mc in metrics:
        df_agg[_mc] = pd.to_numeric(df_agg[_mc], errors="coerce")

    for dim in dims_sorted:
        n_uniq = df[dim].nunique(dropna=False)
        lines.append(f"#### By {dim}\n\n")

        grp = df_agg.groupby(dim, dropna=False)[metrics].sum()
        grp = grp.sort_values(metrics[0], ascending=False)

        capped = len(grp) > _MAX_PIVOT_ROWS
        if capped:
            grp = grp.head(_MAX_PIVOT_ROWS)

        lines.append("| " + dim + " | " + " | ".join(metrics) + " |")
        lines.append("|" + "|".join([" --- "] * (len(metrics) + 1)) + "|")

        for idx_val, row in grp.iterrows():
            idx_str = str(idx_val) if str(idx_val) not in ("nan", "None", "") else "*(null/blank)*"
            vals = [_fmt_num(row[m], currency_flags[i]) for i, m in enumerate(metrics)]
            lines.append("| " + idx_str + " | " + " | ".join(vals) + " |")

        totals = [_fmt_num(df_agg[m].sum(), currency_flags[i]) for i, m in enumerate(metrics)]
        lines.append("| **Total** | " + " | ".join(f"**{t}**" for t in totals) + " |")

        if capped:
            lines.append(f"\n*(showing top {_MAX_PIVOT_ROWS} of {n_uniq} values by {metrics[0]})*\n")

        lines.append("\n")

    return lines


def _render_enhanced_generic(df, dim_cols: list, text_cols: list) -> list:
    """
    For large sheets without meaningful numeric metrics
    (trackers, question registers, Jira exports).
    """
    lines = ["---\n", "### Value distributions\n\n"]
    lines.append("*No numeric metrics detected. Showing full categorical breakdowns.*\n\n")

    all_cat = dim_cols + [c for c in df.columns
                          if c not in dim_cols and df[c].dtype == object
                          and df[c].nunique() <= _MAX_CAT_VALUES]

    if not all_cat:
        lines.append("*No low-cardinality categorical columns found.*\n\n")
        return lines

    for col in all_cat[:10]:
        vc = df[col].value_counts(dropna=False).head(_MAX_CAT_VALUES)
        total = len(df)
        n_total = df[col].nunique(dropna=False)
        cap_note = f" *(showing top {_MAX_CAT_VALUES} of {n_total})*" if n_total > _MAX_CAT_VALUES else ""

        lines.append(f"#### {col} ({n_total} unique values){cap_note}\n\n")
        lines.append("| Value | Count | % |")
        lines.append("| --- | --- | --- |")
        for val, cnt in vc.items():
            label = str(val) if str(val) not in ("nan", "None") else "*(null/blank)*"
            pct   = cnt / total * 100
            lines.append(f"| {label} | {cnt:,} | {pct:.1f}% |")
        lines.append("\n")

    return lines


def _render_quality_flags(df, metric_cols: list, dim_cols: list) -> list:
    """Surface null patterns and outliers for the AI to flag."""
    import pandas as pd

    issues = []
    for col in df.columns:
        null_count = df[col].isna().sum()
        str_nulls = df[col].astype(str).str.lower().isin(
            ["[null]", "null", "n/a", "na", "none"]
        ).sum()
        total_null = null_count + str_nulls
        if total_null > 0:
            pct = total_null / len(df) * 100
            note = ""
            if str_nulls > 0 and null_count == 0:
                note = " (as literal string)"
            elif str_nulls > 0:
                note = f" ({str_nulls} as literal string, {null_count} as true null)"
            issues.append(f"- **{col}:** {total_null:,} null/missing ({pct:.1f}%){note}")

    outlier_notes = []
    for mc in metric_cols:
        num_s = pd.to_numeric(df[mc], errors="coerce").dropna()
        if len(num_s) < 10:
            continue
        mean, std = num_s.mean(), num_s.std()
        if std == 0:
            continue
        curr = _detect_currency_col(mc)
        threshold = mean + 3 * std
        outliers  = (num_s > threshold).sum()
        if outliers > 0:
            outlier_notes.append(
                f"- **{mc}:** {outliers} outlier row(s) above 3\u03c3 threshold "
                f"({_fmt_num(threshold, curr)}) - max value: {_fmt_num(num_s.max(), curr)}"
            )
        median = num_s.median()
        if median > 0 and mean > 3 * median:
            outlier_notes.append(
                f"- **{mc}:** right-skewed - median {_fmt_num(median, curr)} "
                f"vs mean {_fmt_num(mean, curr)} - a few high-value rows pull the average up"
            )

    if not issues and not outlier_notes:
        return []

    lines = ["---\n", "### Data quality notes\n\n"]
    if issues:
        lines.append("**Null / missing values:**\n")
        lines += [i + "\n" for i in issues]
        lines.append("\n")
    if outlier_notes:
        lines.append("**Outliers & distribution notes:**\n")
        lines += [n + "\n" for n in outlier_notes]
        lines.append("\n")

    return lines


def _render_sample(df, headers: list) -> list:
    """Three-point sample: first 5, 5 from middle, last 3."""
    import re as _re

    def _cell_str_local(value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        text = _re.sub(r'\r\n|\r|\n', ' ', text)
        text = text.replace('|', '\\|')
        return text

    lines = ["---\n", "### Sample records\n\n"]
    last_col = min(len(headers), 15)
    display_headers = headers[:last_col]
    sep = "| " + " | ".join(["---"] * last_col) + " |"

    def emit_rows(slice_df, label):
        lines.append(f"**{label}:**\n\n")
        lines.append("| " + " | ".join(display_headers) + " |")
        lines.append(sep)
        for _, row in slice_df.iterrows():
            def _clean_val(v):
                s = str(v)
                if s in ("nan", "None", ""):
                    return ""
                if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
                    return s[:-2]
                return _cell_str_local(s)
            vals = [_clean_val(v) for v in list(row)[:last_col]]
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("\n")

    emit_rows(df.head(5), "First 5 rows")

    if len(df) > 15:
        mid_start = max(5, len(df) // 2 - 2)
        mid_slice = df.iloc[mid_start:mid_start + 5]
        emit_rows(mid_slice, f"5 rows from middle of dataset (rows {mid_start+1}-{mid_start+5})")

    if len(df) > 8:
        emit_rows(df.tail(3), "Last 3 rows")

    return lines

def _render_normal_table(grid: list, header_idx: int, legend: dict,
                          ws, sheet_name: str = "") -> list:
    """
    Render a standard row-per-record sheet as a Markdown pipe table.
    Sheets exceeding _MAX_FULL_ROWS data rows are summarised instead of dumped.
    Returns list of line strings.
    """
    data_rows = [r for r in grid[header_idx + 1:] if not _is_empty_row(r)]

    # Hard skip: raw operational data dumps / PII-risk sheets
    if len(data_rows) > _MAX_SKIP_ROWS:
        logging.warning(
            f"  Sheet '{sheet_name}': {len(data_rows):,} rows exceeds "
            f"_MAX_SKIP_ROWS={_MAX_SKIP_ROWS} — sheet skipped (raw data/PII risk)"
        )
        return [
            f"> **⚠ Sheet skipped — {len(data_rows):,} rows of raw operational data.**\n",
            f"> This sheet exceeds the {_MAX_SKIP_ROWS:,}-row limit for AI context inclusion.\n",
            f"> Likely contains transactional records or PII (names, dates, IDs).\n",
            f"> To include this data, pre-aggregate it in Excel and reconvert.\n",
        ]

    # Large-sheet guard: summarise instead of dumping thousands of raw rows
    # Large-sheet guard: smart summary instead of dumping raw rows
    if len(data_rows) > _MAX_FULL_ROWS:
        logging.info(
            f"  Sheet '{sheet_name}': {len(data_rows):,} rows exceeds "
            f"_MAX_FULL_ROWS={_MAX_FULL_ROWS} - generating smart summary"
        )
        try:
            import pandas as pd
            header_row  = grid[header_idx]
            last_col    = max((i for i, v in enumerate(header_row) if v), default=0) + 1
            headers     = header_row[:last_col]
            data_matrix = [r[:last_col] + [""] * max(0, last_col - len(r))
                           for r in data_rows]
            df = pd.DataFrame(data_matrix, columns=headers)
            # Coerce numeric - use coerce so [NULL]/string cells become NaN
            # (errors='ignore' silently leaves column as object if ANY cell is non-numeric)
            for col in df.columns:
                _coerced = pd.to_numeric(df[col], errors="coerce")
                if _coerced.notna().sum() / max(len(df), 1) >= 0.5:
                    df[col] = _coerced
            smart = _build_smart_summary(df, headers, len(data_rows), sheet_name)
            if smart is not None:
                return smart
        except Exception as e:
            logging.warning(
                f"  Sheet '{sheet_name}': smart summary failed ({e}) - falling back to generic"
            )

        # Fallback: generic statistical summary
        try:
            import pandas as pd
            header_row  = grid[header_idx]
            last_col    = max((i for i, v in enumerate(header_row) if v), default=0) + 1
            headers     = header_row[:last_col]
            data_matrix = [r[:last_col] + [""] * max(0, last_col - len(r))
                           for r in data_rows]
            df = pd.DataFrame(data_matrix, columns=headers)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='ignore')
            total = len(df)
            fb = [
                f"> **Large dataset - summary view** ({total:,} rows x {len(headers)} columns). "
                f"Full row dump suppressed; statistical summary shown instead.\n",
                f"\n**Columns:** {', '.join(headers)}\n",
            ]
            num_cols = df.select_dtypes(include='number').columns.tolist()
            if num_cols:
                fb.append("\n**Numeric column statistics:**\n")
                desc = df[num_cols].describe().round(2)
                fb.append("| Stat | " + " | ".join(num_cols) + " |")
                fb.append("|" + "|".join([" --- "] * (len(num_cols) + 1)) + "|")
                for stat_name, stat_row in desc.iterrows():
                    fb.append("| " + stat_name + " | " + " | ".join(str(v) for v in stat_row.values) + " |")
            cat_cols = df.select_dtypes(exclude='number').columns.tolist()
            useful   = [c for c in cat_cols if 1 < df[c].nunique() <= 200][:5]
            if useful:
                fb.append("\n**Key categorical breakdowns:**\n")
                for col in useful:
                    vc = df[col].value_counts().head(10)
                    fb.append(f"\n*{col}* (top {len(vc)}):\n")
                    for val, cnt in vc.items():
                        fb.append(f"- {val}: {cnt:,} ({cnt/total*100:.1f}%)")
            fb.append(f"\n**Sample (first 5 rows):**\n")
            fb.append("| " + " | ".join(headers) + " |")
            fb.append("|" + "|".join([" --- "] * len(headers)) + "|")
            for _, row in df.head(5).iterrows():
                fb.append("| " + " | ".join(str(v) for v in row.values) + " |")
            return fb
        except Exception as e2:
            return [f"> **Could not summarise sheet** - {e2}\n"]


    lines = []
    header_row = grid[header_idx]

    # Strip trailing empty columns
    last_col = max((i for i, v in enumerate(header_row) if v), default=0) + 1
    header_row = header_row[:last_col]

    lines.append("| " + " | ".join(header_row) + " |")
    lines.append("|" + "|".join([" --- "] * len(header_row)) + "|")

    # Iterate actual ws rows for colour access
    all_ws_rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row,
                                     min_col=1, max_col=ws.max_column))

    for row_idx, row_data in enumerate(grid[header_idx + 1:], start=header_idx + 1):
        if _is_empty_row(row_data):
            continue
        # Skip numbered placeholder rows — only a sequential integer in col 0,
        # all other cells empty. These are pre-allocated blank rows that Excel
        # users leave for future entries and carry no content.
        if (row_data[0] and not any(row_data[1:last_col])
                and re.match(r'^\d+$', str(row_data[0]).strip())):
            continue
        cells = row_data[:last_col]
        # Pad if needed
        while len(cells) < last_col:
            cells.append("")

        # Annotate colours where we have legend data
        annotated = []
        for col_idx, val in enumerate(cells):
            try:
                ws_cell = all_ws_rows[row_idx][col_idx]
                colour_note = _cell_colour_label(ws_cell, legend)
            except (IndexError, Exception):
                colour_note = ""
            annotated.append(val + colour_note)

        lines.append("| " + " | ".join(annotated) + " |")

    return lines


def _render_wide_matrix(grid: list, header_idx: int, ws) -> list:
    """
    For cross-tab / wide matrix sheets, render as a series of
    row-record blocks: one section per data row, listing each column
    header and its value as a key: value pair.
    This is far more LLM-readable than a 40-column pipe table.
    """
    lines = []
    col_headers = grid[header_idx]
    # Build secondary header labels from the row above header if it exists
    # (handles two-row column headings like 'Initiative > Sub-metric')
    parent_headers = []
    if header_idx > 0:
        parent_row = grid[header_idx - 1]
        # Fill forward (merged cells leave blanks in the row above)
        current = ""
        for v in parent_row:
            if v:
                current = v
            parent_headers.append(current)
    
    def col_label(i):
        base = col_headers[i] if i < len(col_headers) else ""
        parent = parent_headers[i] if i < len(parent_headers) else ""
        if parent and parent != base:
            return f"{parent} â€º {base}" if base else parent
        return base or f"Col{i+1}"

    # Row identifier column heuristic: first non-empty column header
    id_col = next((i for i, v in enumerate(col_headers) if v), 0)

    lines.append(f"> **Layout note:** This sheet uses a wide cross-tab matrix "
                 f"({sum(1 for v in col_headers if v)} columns). "
                 f"Each section below is one row of the matrix.\n")

    for row_data in grid[header_idx + 1:]:
        if _is_empty_row(row_data):
            continue
        row_id = row_data[id_col] if id_col < len(row_data) else ""
        lines.append(f"\n#### {row_id or '(unnamed row)'}\n")
        for col_i, val in enumerate(row_data):
            if col_i >= len(col_headers):
                break
            label = col_label(col_i)
            if val and label:
                lines.append(f"- **{label}:** {val}")

    return lines


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

def convert_xlsx_to_markdown(xlsx_path, output_path=None):
    """
    Convert XLSX to markdown, extracting all sheet data with improved
    structural handling.

    Args:
        xlsx_path: Path to XLSX file
        output_path: Optional output path (defaults to same name with .md extension)

    Returns:
        Path to created markdown file
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError(
            "Required library not installed. Run setup.ps1 or install manually:\n"
            "pip install openpyxl"
        )

    xlsx_path = Path(xlsx_path)
    if output_path is None:
        output_path = xlsx_path.with_suffix('.md')
    else:
        output_path = Path(output_path)

    logging.info(f"Converting XLSX: {xlsx_path}")

    try:
        # data_only=True: read cached formula results, not the formula strings
        wb = load_workbook(str(xlsx_path.resolve()), data_only=True)
    except Exception as e:
        error_msg = str(e)
        if "Permission" in error_msg or "Access" in error_msg:
            raise PermissionError(
                f"Cannot access file. Make sure it's not open in Excel. Error: {error_msg}"
            )
        else:
            logging.error(f"Failed to open XLSX file: {e}")
            raise

    # Build a legend colour map once for the whole workbook
    legend = _build_legend_map(wb)
    if legend:
        logging.info(f"Found legend with {len(legend)} colour mappings")

    markdown_lines = []
    markdown_lines.append(f"# {xlsx_path.stem}\n")
    markdown_lines.append(f"*Converted from: {xlsx_path.name}*\n")
    markdown_lines.append(f"*Sheets: {len(wb.sheetnames)} â€” {', '.join(wb.sheetnames)}*\n")
    if legend:
        markdown_lines.append(
            f"*Colour legend detected: {chr(44).join(list(legend.values())[:6])}*\n"
        )
    markdown_lines.append("\n")

    sheets_converted = 0
    sheets_skipped = 0

    for sheet_name in wb.sheetnames:
        logging.info(f"Processing sheet: {sheet_name}")
        ws = wb[sheet_name]

        markdown_lines.append(f"\n---\n\n## Sheet: {sheet_name}\n\n")

        # --- Skip chart/dashboard-only sheets ---
        if _sheet_is_chart_only(ws):
            markdown_lines.append(
                f"*[Sheet skipped — appears to be a chart or dashboard placeholder "
                f"with fewer than 4% populated cells. Data is in the source rows.]*\n"
            )
            sheets_skipped += 1
            logging.info(f"  Skipped (chart/sparse): {sheet_name}")
            continue

        # --- Early row-count skip: avoid reading PII/data-dump sheets into memory ---
        # ws.max_row is an O(1) openpyxl property — no row iteration needed.
        # Subtract a small header allowance; if still over the hard limit, skip now.
        if ws.max_row > _MAX_SKIP_ROWS + 8:
            logging.warning(
                f"  Sheet '{sheet_name}': {ws.max_row} rows (ws.max_row) exceeds "
                f"_MAX_SKIP_ROWS={_MAX_SKIP_ROWS} — skipping before grid load"
            )
            markdown_lines.append(
                f"> **⚠ Sheet skipped — {ws.max_row:,} rows of raw operational data.**\n"
                f"> This sheet exceeds the {_MAX_SKIP_ROWS:,}-row limit for AI context inclusion.\n"
                f"> Likely contains transactional records or PII (names, dates, IDs).\n"
                f"> To include this data, pre-aggregate it in Excel and reconvert.\n"
            )
            sheets_skipped += 1
            continue

        # --- Extract raw grid ---
        grid = []
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row,
                                 min_col=1, max_col=ws.max_column):
            grid.append([_cell_str(cell.value) for cell in row])

        # Strip trailing empty or placeholder rows (numbered-but-empty rows
        # that Excel users leave for future entries, e.g. ['38','','',''])
        while grid and (
            _is_empty_row(grid[-1])
            or (grid[-1][0] and not any(grid[-1][1:])
                and re.match(r'^\d+$', str(grid[-1][0]).strip()))
        ):
            grid.pop()

        if not grid:
            markdown_lines.append("*[No data]*\n")
            sheets_skipped += 1
            continue

        # --- Find real header row ---
        header_idx = _find_header_row(grid)
        if header_idx > 0:
            # Emit the skipped title/blank rows as prose context, not table noise
            markdown_lines.append("**Sheet context:**\n")
            for pre_row in grid[:header_idx]:
                text = " | ".join(v for v in pre_row if v)
                if text:
                    markdown_lines.append(f"> {text}\n")
            markdown_lines.append("\n")

        # --- Metadata line ---
        data_rows = [r for r in grid[header_idx + 1:] if not _is_empty_row(r)]
        col_count = sum(1 for v in grid[header_idx] if v)
        markdown_lines.append(
            f"*{len(data_rows)} data rows Ã— {col_count} columns*\n\n"
        )

        # --- Choose rendering strategy ---
        if _detect_wide_matrix(grid, header_idx):
            logging.info(f"  Detected wide matrix layout ({col_count} cols) — using section rendering")
            markdown_lines.append(
                f"*Wide matrix detected ({col_count} columns). "
                f"Rendered as per-row sections for readability.*\n\n"
            )
            lines = _render_wide_matrix(grid, header_idx, ws)
        else:
            lines = _render_normal_table(grid, header_idx, legend, ws, sheet_name=sheet_name)

        markdown_lines.extend(lines)
        markdown_lines.append("\n")
        sheets_converted += 1
        logging.info(f"  Done: {len(data_rows)} rows, {col_count} cols")

    # Summary footer
    markdown_lines.append(
        f"\n---\n*Conversion summary: {sheets_converted} sheet(s) converted, "
        f"{sheets_skipped} skipped (chart/empty).*\n"
    )

    content = '\n'.join(markdown_lines)
    output_path.write_text(content, encoding='utf-8')

    logging.info(f"Created markdown: {output_path}")
    return output_path

# Made with Bob - Enhanced Version
