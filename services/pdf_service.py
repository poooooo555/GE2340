import io
from fpdf import FPDF


def generate_timetable_pdf(schedule: dict) -> io.BytesIO:
    # 用橫向 A4 (Landscape) 放整星期時間表會靚好多
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()

    # 標題
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.cell(0, 10, "Full-Semester Timetable Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    days = schedule.get("days") or []
    rows = schedule.get("rows") or []

    # 1. 畫時間表 Grid
    if days and rows:
        pdf.set_font("Helvetica", style="B", size=10)
        time_col_w = 32
        day_col_w = (277 - time_col_w) / len(days)  # A4 橫向可用闊度約 277mm

        # 表頭
        pdf.set_fill_color(230, 236, 245)
        pdf.cell(time_col_w, 9, "Time", border=1, align="C", fill=True)
        for day in days:
            pdf.cell(day_col_w, 9, str(day), border=1, align="C", fill=True)
        pdf.ln()

        # 每一行時段
        pdf.set_font("Helvetica", size=8)
        for row in rows:
            time_str = row.get("time", "")
            cells = row.get("cells") or {}

            # 準備每個儲存格嘅文字，並計算該行所需高度
            cell_texts = []
            max_lines = 1
            for day in days:
                entries = cells.get(day) or []
                lines = []
                for e in entries:
                    code = e.get("course", "")
                    sec = f" ({e.get('section')})" if e.get("section") else ""
                    room = f" @ {e.get('room')}" if e.get("room") else ""
                    wk = f" [{e.get('weeks_display')}]" if e.get("weeks_display") else ""
                    lines.append(f"{code}{sec}{room}{wk}")
                text = "\n".join(lines)
                cell_texts.append(text)
                if len(lines) > max_lines:
                    max_lines = len(lines)

            row_h = max(10, max_lines * 5 + 3)

            # 檢查係咪需要自動換頁
            if pdf.get_y() + row_h > 190:
                pdf.add_page()

            x_start = pdf.get_x()
            y_start = pdf.get_y()

            # 畫 Time 欄
            pdf.multi_cell(time_col_w, row_h, time_str, border=1, align="C")
            pdf.set_xy(x_start + time_col_w, y_start)

            # 畫星期幾各欄
            for i, text in enumerate(cell_texts):
                curr_x = x_start + time_col_w + i * day_col_w
                pdf.set_xy(curr_x, y_start)
                # 先畫外框確保高度一致
                pdf.rect(curr_x, y_start, day_col_w, row_h)
                if text:
                    pdf.multi_cell(day_col_w, 4.5, text, border=0, align="L")

            pdf.set_xy(x_start, y_start + row_h)

    # 2. 畫 Courses Detected 列表
    courses = schedule.get("courses") or []
    if courses:
        pdf.ln(8)
        pdf.set_font("Helvetica", style="B", size=12)
        pdf.cell(0, 8, "Courses Summary", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", style="B", size=9)
        pdf.set_fill_color(240, 240, 240)
        c_widths = [30, 110, 55, 82]
        headers = ["Code", "Course Name", "Weeks", "Schedule"]
        for w, h in zip(c_widths, headers):
            pdf.cell(w, 8, h, border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", size=9)
        for c in courses:
            pdf.cell(c_widths[0], 7, str(c.get("code", ""))[:15], border=1)
            pdf.cell(c_widths[1], 7, str(c.get("name", ""))[:55], border=1)
            pdf.cell(c_widths[2], 7, str(c.get("weeks_display", ""))[:28], border=1)
            pdf.cell(c_widths[3], 7, str(c.get("schedule", ""))[:42], border=1)
            pdf.ln()

    return io.BytesIO(pdf.output())