"""Excel (.xlsx) export helper — one sheet, header row + data rows."""

from datetime import date, datetime
from io import BytesIO
from typing import Any

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.config import TASHKENT_TZ

_HEADER_FILL = PatternFill(start_color="2F496E", end_color="2F496E", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True)


def xlsx_response(title: str, headers: list[str], rows: list[list[Any]], filename: str) -> StreamingResponse:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = title[:31]

    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row in rows:
        ws.append([_cell(v) for v in row])

    for col in range(1, len(headers) + 1):
        width = max(
            len(str(headers[col - 1])),
            *(len(str(_cell(r[col - 1]))) for r in rows[:200]) if rows else (10,),
        )
        ws.column_dimensions[get_column_letter(col)].width = min(width + 3, 50)
    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cell(v: Any) -> Any:
    if isinstance(v, datetime):
        # Aware (UTC) vaqtlar Toshkent zonasida ko'rsatiladi.
        local = v.astimezone(TASHKENT_TZ) if v.tzinfo else v
        return local.strftime("%d.%m.%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d.%m.%Y")
    return v
