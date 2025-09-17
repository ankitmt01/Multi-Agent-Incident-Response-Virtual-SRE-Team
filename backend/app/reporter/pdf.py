from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def build_pdf(incident, result) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=36, bottomMargin=36, leftMargin=42, rightMargin=42)
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]; h2 = styles["Heading2"]; body = styles["BodyText"]
    mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=9, leading=11)

    story = []
    story.append(Paragraph(f"Incident Report — {incident.id}", h1))
    story.append(Paragraph(f"<b>Service:</b> {incident.service}", body))
    story.append(Paragraph(f"<b>Severity:</b> {incident.severity}", body))
    story.append(Paragraph(f"<b>Created:</b> {incident.created_at.isoformat()}", body))
    if incident.suspected_cause:
        story.append(Paragraph(f"<b>Suspected Cause:</b> {incident.suspected_cause}", body))
    story.append(Spacer(1, 10))

    # Evidence
    story.append(Paragraph("Evidence", h2))
    if result.evidence:
        data = [["Title", "Score", "Source"]]
        for e in result.evidence:
            data.append([e.title, f"{e.score:.3f}", e.source_file or ""])
        tbl = Table(data, colWidths=[260, 60, 160])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No evidence found.", body))
    story.append(Spacer(1, 10))

    # Candidates
    story.append(Paragraph("Candidate Plans", h2))
    for c in result.candidates:
        mark = "✅" if not c.policy_violations else "⛔"
        story.append(Paragraph(f"{mark} <b>{c.name}</b>", body))
        story.append(Paragraph(f"<i>Rationale:</i> {c.rationale}", body))
        story.append(Paragraph(f"<i>Predicted Impact:</i> {c.predicted_impact}", body))
        if c.policy_violations:
            story.append(Paragraph("<b>Policy Violations:</b>", body))
            for v in c.policy_violations:
                story.append(Paragraph(f"• {v}", body))
        story.append(Paragraph("<b>Steps:</b>", body))
        for s in c.steps:
            story.append(Paragraph(f"• [{s.action_type}] {s.action}", body))
        story.append(Spacer(1, 6))

    # Validation
    story.append(Paragraph("Validation", h2))
    if result.validation:
        v = result.validation
        data = [
            ["Metric", "Before", "After", "Delta"],
            ["error_rate", f"{v.before['error_rate']:.4f}", f"{v.after['error_rate']:.4f}", f"{v.kpi_deltas['error_rate']:.4f}"],
            ["p95_ms", f"{v.before['p95_ms']:.1f}", f"{v.after['p95_ms']:.1f}", f"{v.kpi_deltas['p95_ms']:.1f}"],
        ]
        tbl = Table(data, colWidths=[120, 120, 120, 120])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ]))
        story.append(tbl)
        story.append(Paragraph(f"Status: <b>{v.status}</b>", body))
    else:
        story.append(Paragraph("No validation executed.", body))
    story.append(Spacer(1, 10))

    # Summary / Policies
    story.append(Paragraph("Policy Summary", h2))
    story.append(Paragraph(result.policy_summary or "All policies ✅", body))

    doc.build(story)
    return buf.getvalue()
