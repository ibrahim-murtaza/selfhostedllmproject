# PPTX comparison: test.pptx

- Docling   : 0.2s; 802 characters
- LibreChat : no captured request contained the deck's text (LibreChat may have refused or ignored the file); 0 characters

## 1. Facts found (each fact is something a good parser should keep)

| Slide | What | Docling | LibreChat |
|---|---|---|---|
| 1 | title (title) | yes | - |
| 1 | subtitle (subtitle_code) | yes | - |
| 2 | bullet (bullet_top) | yes | - |
| 2 | nested bullet (bullet_nested) | yes | - |
| 2 | bullet (bullet_priority2) | yes | - |
| 3 | table header (table_header) | yes | - |
| 3 | table cell in the right row (table_west_q2) | yes | - |
| 3 | table cell in the right row (table_east_q4) | yes | - |
| 4 | chart title (chart_title) | yes | - |
| 4 | chart data value (chart_engineering) | yes | - |
| 5 | text inside a picture (image_text) | MISSING | - |
| 6 | speaker notes (notes_date) | MISSING | - |
| 6 | speaker notes (notes_code) | MISSING | - |
| 6 | bullet (bullet_last) | yes | - |
| | **Total** | **11/14** | **no text** |

## 2. Slide order

- Docling: yes (5 of 6 slides identifiable)
- LibreChat: no text