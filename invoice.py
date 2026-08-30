"""
invoice.py
Generates a professional PDF invoice/receipt for a clinic bill using reportlab.
Kept in its own module so app.py stays focused on UI/navigation.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

# NOTE: reportlab's base-14 fonts don't reliably render the Rupee glyph (₹),
# so invoices use "Rs." to guarantee correct rendering on every system.


def build_invoice_pdf(clinic, patient, bill) -> bytes:
    """
    clinic: dict-like with name, city, address, phone
    patient: dict-like with name, patient_code, age, gender, mobile
    bill: dict-like with id, consultation_fee, medicine_fee, other_charges,
          discount, total, payment_mode, paid_on
    Returns raw PDF bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ClinicTitle", parent=styles["Title"], fontSize=16, spaceAfter=2)
    sub_style = ParagraphStyle("ClinicSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph(clinic.get("name", "Clinic"), title_style))
    addr_line = ", ".join(filter(None, [clinic.get("address"), clinic.get("city")]))
    story.append(Paragraph(addr_line or "&nbsp;", sub_style))
    if clinic.get("phone"):
        story.append(Paragraph(f"Phone: {clinic['phone']}", sub_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("PAYMENT RECEIPT / INVOICE", h2_style))
    meta_table = Table(
        [
            ["Invoice No.", f"INV-{bill['id']:06d}", "Date", bill.get("paid_on", "-")],
        ],
        colWidths=[65, 90, 45, 90],
    )
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, 0), colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Patient Details", h2_style))
    story.append(Paragraph(
        f"<b>Name:</b> {patient.get('name', '-')} &nbsp;&nbsp; "
        f"<b>Code:</b> {patient.get('patient_code', '-')}<br/>"
        f"<b>Age/Gender:</b> {patient.get('age', '-') or '-'} / {patient.get('gender', '-') or '-'} &nbsp;&nbsp; "
        f"<b>Mobile:</b> {patient.get('mobile', '-') or '-'}",
        normal,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Charges", h2_style))
    rows = [["Description", "Amount (Rs.)"]]
    rows.append(["Consultation Fee", f"{bill.get('consultation_fee', 0):,.2f}"])
    rows.append(["Medicine Fee", f"{bill.get('medicine_fee', 0):,.2f}"])
    rows.append(["Other Charges", f"{bill.get('other_charges', 0):,.2f}"])
    rows.append(["Discount", f"- {bill.get('discount', 0):,.2f}"])
    rows.append(["TOTAL", f"{bill.get('total', 0):,.2f}"])

    charge_table = Table(rows, colWidths=[190, 90])
    charge_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284c7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(charge_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>Payment Mode:</b> {bill.get('payment_mode', '-')}", normal))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>This is a computer-generated receipt and does not require a signature.</i>",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# =============================================================================
# PRESCRIPTION (OPD consultation slip) — matches a standard clinic Rx layout:
# doctor info + clinic info header, patient/vitals line, chief complaints /
# clinical findings, diagnosis, medicine table (Rx), advice, follow-up date.
# =============================================================================
def build_prescription_pdf(clinic, doctor, patient, consultation, prescription_items, investigations=None) -> bytes:
    """
    clinic: dict-like with name, city, address, phone, timing, closed_day
    doctor: dict-like with name, qualification, registration_no
    patient: dict-like with id, name, age, gender, mobile, address
    consultation: dict-like with visit_date, chief_complaints, clinical_findings,
                  diagnosis, advice, next_visit, weight, height, bp
    prescription_items: list of dicts with medicine_name, composition, dosage,
                         duration, total_qty
    investigations: optional list of dicts with test_name — lab tests advised
                     during this consultation, printed as their own section.
    Returns raw PDF bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5,
        topMargin=10 * mm, bottomMargin=10 * mm, leftMargin=12 * mm, rightMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    doc_name_style = ParagraphStyle("DocName", parent=styles["Normal"], fontSize=13, leading=16,
                                     fontName="Helvetica-Bold", spaceAfter=1)
    doc_sub_style = ParagraphStyle("DocSub", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#333333"))
    clinic_name_style = ParagraphStyle("ClinicName2", parent=styles["Normal"], fontSize=14, leading=17,
                                        fontName="Helvetica-Bold", textColor=colors.HexColor("#1a3d8f"),
                                        alignment=2, spaceAfter=1)
    clinic_sub_style = ParagraphStyle("ClinicSub2", parent=styles["Normal"], fontSize=8, leading=11,
                                       textColor=colors.HexColor("#333333"), alignment=2)
    section_head = ParagraphStyle("SecHead", parent=styles["Normal"], fontSize=9.5, fontName="Helvetica-Bold")
    normal = ParagraphStyle("RxNormal", parent=styles["Normal"], fontSize=9, leading=12)
    small_grey = ParagraphStyle("SmallGrey", parent=styles["Normal"], fontSize=7.5, textColor=colors.grey)

    story = []

    # ---- Header: doctor (left) | clinic (right) ----
    doc_block = [
        Paragraph(doctor.get("name", "Doctor"), doc_name_style),
        Paragraph(doctor.get("qualification", "") or "", doc_sub_style),
        Paragraph(f"Reg. No: {doctor.get('registration_no', '')}" if doctor.get("registration_no") else "", doc_sub_style),
    ]
    clinic_lines = [f"<b>{clinic.get('name', 'Clinic')}</b>"]
    addr_bits = ", ".join(filter(None, [clinic.get("address"), clinic.get("city")]))
    if addr_bits:
        clinic_lines.append(addr_bits)
    phone_timing = []
    if clinic.get("phone"):
        phone_timing.append(f"Ph: {clinic['phone']}")
    if clinic.get("timing"):
        phone_timing.append(f"Timing: {clinic['timing']}")
    if phone_timing:
        clinic_lines.append(", ".join(phone_timing))
    if clinic.get("closed_day"):
        clinic_lines.append(f"Closed: {clinic['closed_day']}")

    clinic_block = [Paragraph(clinic_lines[0], clinic_name_style)]
    for line in clinic_lines[1:]:
        clinic_block.append(Paragraph(line, clinic_sub_style))

    header_table = Table([[doc_block, clinic_block]], colWidths=[190, 190])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#999999")))
    story.append(Spacer(1, 4))

    # ---- Date ----
    story.append(Paragraph(f"<b>Date:</b> {consultation.get('visit_date', '-')}",
                            ParagraphStyle("DateLine", parent=normal, alignment=2)))

    # ---- Patient line ----
    age_gender = f"{patient.get('age', '-')} Y" if patient.get("age") else "-"
    gender_letter = (patient.get("gender") or "-")[:1].upper()
    patient_name = patient.get("name") or "-"
    story.append(Paragraph(
        f"<b>Name: {patient_name} &nbsp;&nbsp; ID: {patient.get('id', '-')} - OPD PATIENT ({gender_letter}) / {age_gender}"
        f" &nbsp;&nbsp; Mob. No.: {patient.get('mobile', '-')}</b>", normal
    ))
    if patient.get("address"):
        story.append(Paragraph(f"Address: {patient['address']}", normal))

    # ---- Vitals ----
    vitals_bits = []
    weight = consultation.get("weight")
    height = consultation.get("height")
    if weight:
        vitals_bits.append(f"Weight (Kg): {weight}")
    if height:
        vitals_bits.append(f"Height (Cm): {height}")
    if weight and height:
        try:
            bmi = float(weight) / ((float(height) / 100) ** 2)
            vitals_bits.append(f"(B.M.I. = {bmi:.2f})")
        except (ValueError, ZeroDivisionError):
            pass
    if consultation.get("bp"):
        vitals_bits.append(f"BP: {consultation['bp']} mmHg")
    if vitals_bits:
        story.append(Paragraph(", ".join(vitals_bits), normal))

    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#bbbbbb")))
    story.append(Spacer(1, 4))

    # ---- Chief Complaints | Clinical Findings ----
    cc = (consultation.get("chief_complaints") or "-").replace("\n", "<br/>")
    cf = (consultation.get("clinical_findings") or "-").replace("\n", "<br/>")
    two_col = Table(
        [[Paragraph("<b>Chief Complaints</b>", section_head), Paragraph("<b>Clinical Findings</b>", section_head)],
         [Paragraph(cc, normal), Paragraph(cf, normal)]],
        colWidths=[190, 190],
    )
    two_col.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#bbbbbb")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#bbbbbb")))
    story.append(Spacer(1, 6))

    # ---- Diagnosis ----
    if consultation.get("diagnosis"):
        story.append(Paragraph("<b>Diagnosis:</b>", section_head))
        story.append(Paragraph((consultation["diagnosis"] or "-").replace("\n", "<br/>"), normal))
        story.append(Spacer(1, 6))

    # ---- Investigations Advised (lab tests ordered during this visit) ----
    if investigations:
        story.append(Paragraph("<b>Investigations Advised:</b>", section_head))
        test_names = ", ".join(it.get("test_name", "-") for it in investigations)
        story.append(Paragraph(test_names, normal))
        story.append(Spacer(1, 6))

    # ---- Rx / Medicine table ----
    if prescription_items:
        story.append(Paragraph("<b>R</b>", ParagraphStyle("RxSymbol", parent=styles["Normal"], fontSize=13, fontName="Helvetica-Bold")))
        med_head_style = ParagraphStyle("MedHead", parent=normal, fontName="Helvetica-Bold")
        rows = [[Paragraph("Medicine Name", med_head_style),
                 Paragraph("Dosage", med_head_style),
                 Paragraph("Duration", med_head_style)]]
        for idx, item in enumerate(prescription_items, start=1):
            name_html = f"{idx}) {item.get('medicine_name', '')}"
            if item.get("composition"):
                name_html += f"<br/><font size=7 color='grey'>{item['composition']}</font>"
            dosage_html = (item.get("dosage") or "-").replace("\n", "<br/>")
            duration_html = item.get("duration") or "-"
            if item.get("total_qty"):
                duration_html += f"<br/><font size=7.5>({item['total_qty']})</font>"
            rows.append([
                Paragraph(name_html, normal),
                Paragraph(dosage_html, normal),
                Paragraph(duration_html, normal),
            ])
        med_table = Table(rows, colWidths=[150, 130, 100])
        med_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(med_table)
        story.append(Spacer(1, 4))

    # ---- Advice ----
    if consultation.get("advice"):
        story.append(Paragraph("<b>Advice:</b>", section_head))
        story.append(Paragraph((consultation["advice"] or "").replace("\n", "<br/>"), normal))
        story.append(Spacer(1, 3))

    # ---- Follow up ----
    if consultation.get("next_visit"):
        story.append(Paragraph(f"<b>Follow Up:</b> {consultation['next_visit']}", normal))
        story.append(Spacer(1, 4))

    story.append(Paragraph(
        "<i>Substitute with equivalent Generics as required.</i>",
        ParagraphStyle("RxFooter", parent=styles["Normal"], fontSize=7.5, textColor=colors.grey, alignment=1),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# =============================================================================
# MEDICINE SALE RECEIPT (pharmacy counter — separate from OPD fee billing)
# =============================================================================
def build_medicine_sale_receipt(clinic, customer_name, mobile, items, sale) -> bytes:
    """
    clinic: dict-like with name, city, address, phone
    customer_name, mobile: str
    items: list of dicts with medicine_name, quantity, unit_price, subtotal
    sale: dict-like with id, subtotal, discount, total, payment_mode, sold_on
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PharmClinicTitle", parent=styles["Title"], fontSize=16, fontName="Helvetica-Bold", spaceAfter=2)
    sub_style = ParagraphStyle("PharmClinicSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h2_style = ParagraphStyle("PharmH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph(clinic.get("name", "Clinic"), title_style))
    addr_line = ", ".join(filter(None, [clinic.get("address"), clinic.get("city")]))
    story.append(Paragraph(addr_line or "&nbsp;", sub_style))
    if clinic.get("phone"):
        story.append(Paragraph(f"Phone: {clinic['phone']}", sub_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("MEDICINE SALE RECEIPT", h2_style))
    meta_table = Table(
        [["Receipt No.", f"MS-{sale['id']:06d}", "Date", sale.get("sold_on", "-")]],
        colWidths=[65, 90, 45, 90],
    )
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, 0), colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"<b>Customer:</b> {customer_name or 'Walk-in Customer'} &nbsp;&nbsp; <b>Mobile:</b> {mobile or '-'}",
        normal,
    ))
    story.append(Spacer(1, 10))

    rows = [["Medicine", "Qty", "Unit Price (Rs.)", "Amount (Rs.)"]]
    for it in items:
        rows.append([
            it["medicine_name"], str(it["quantity"]),
            f"{it['unit_price']:,.2f}", f"{it['subtotal']:,.2f}",
        ])
    rows.append(["", "", "Subtotal", f"{sale.get('subtotal', 0):,.2f}"])
    rows.append(["", "", "Discount", f"- {sale.get('discount', 0):,.2f}"])
    rows.append(["", "", "TOTAL", f"{sale.get('total', 0):,.2f}"])

    item_table = Table(rows, colWidths=[130, 40, 70, 70])
    item_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0891b2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Payment Mode:</b> {sale.get('payment_mode', '-')}", normal))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>This is a computer-generated receipt and does not require a signature.</i>",
        ParagraphStyle("PharmFooter", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# =============================================================================
# PATHOLOGY LAB — test report and lab bill
# =============================================================================
def build_lab_report_pdf(clinic, patient, order, order_items) -> bytes:
    """
    order: dict-like with id, doctor_name, order_date
    order_items: list of dicts with test_name, result_value, normal_range, unit
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("LabClinicTitle", parent=styles["Title"], fontSize=16, fontName="Helvetica-Bold", spaceAfter=2)
    sub_style = ParagraphStyle("LabClinicSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h2_style = ParagraphStyle("LabH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph(clinic.get("name", "Clinic"), title_style))
    addr_line = ", ".join(filter(None, [clinic.get("address"), clinic.get("city")]))
    story.append(Paragraph(addr_line or "&nbsp;", sub_style))
    if clinic.get("phone"):
        story.append(Paragraph(f"Phone: {clinic['phone']}", sub_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("PATHOLOGY LAB REPORT", h2_style))
    story.append(Paragraph(
        f"<b>Patient:</b> {patient.get('name', '-')} ({patient.get('patient_code', '-')}) "
        f"&nbsp;&nbsp; <b>Age/Gender:</b> {patient.get('age', '-')}/{patient.get('gender', '-')}",
        normal,
    ))
    story.append(Paragraph(
        f"<b>Referred by:</b> {order.get('doctor_name') or '-'} &nbsp;&nbsp; "
        f"<b>Report Date:</b> {order.get('order_date', '-')}",
        normal,
    ))
    story.append(Spacer(1, 10))

    rows = [["Test Name", "Result", "Normal Range", "Unit"]]
    for it in order_items:
        rows.append([
            it.get("test_name", "-"), it.get("result_value") or "-",
            it.get("normal_range") or "-", it.get("unit") or "-",
        ])
    result_table = Table(rows, colWidths=[110, 80, 90, 60])
    result_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(result_table)
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>This is a computer-generated report. Please correlate clinically.</i>",
        ParagraphStyle("LabFooter", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def build_lab_bill_pdf(clinic, patient, order, order_items, total, payment_mode) -> bytes:
    """Simple itemized bill for the tests ordered in a lab order."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("LabBillTitle", parent=styles["Title"], fontSize=16, fontName="Helvetica-Bold", spaceAfter=2)
    sub_style = ParagraphStyle("LabBillSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h2_style = ParagraphStyle("LabBillH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph(clinic.get("name", "Clinic"), title_style))
    addr_line = ", ".join(filter(None, [clinic.get("address"), clinic.get("city")]))
    story.append(Paragraph(addr_line or "&nbsp;", sub_style))
    if clinic.get("phone"):
        story.append(Paragraph(f"Phone: {clinic['phone']}", sub_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("PATHOLOGY LAB BILL", h2_style))
    story.append(Paragraph(
        f"<b>Patient:</b> {patient.get('name', '-')} ({patient.get('patient_code', '-')}) "
        f"&nbsp;&nbsp; <b>Bill No.:</b> LAB-{order['id']:06d} &nbsp;&nbsp; "
        f"<b>Date:</b> {order.get('order_date', '-')}",
        normal,
    ))
    story.append(Spacer(1, 10))

    rows = [["Test Name", "Amount (Rs.)"]]
    for it in order_items:
        rows.append([it.get("test_name", "-"), f"{it.get('price', 0):,.2f}"])
    rows.append(["TOTAL", f"{total:,.2f}"])

    bill_table = Table(rows, colWidths=[220, 90])
    bill_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Payment Mode:</b> {payment_mode or '-'}", normal))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>This is a computer-generated receipt and does not require a signature.</i>",
        ParagraphStyle("LabBillFooter", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
