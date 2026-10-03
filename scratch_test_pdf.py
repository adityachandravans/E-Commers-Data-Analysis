import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os

def generate_pdf_report(pdf_filename="test_report.pdf"):
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=12
    )
    story.append(Paragraph("Olist E-Commerce Executive Summary Report", title_style))
    story.append(Spacer(1, 10))

    body_style = styles['BodyText']
    story.append(Paragraph("<b>Key Headline Metrics:</b>", body_style))
    story.append(Spacer(1, 6))

    data = [
        ["Metric", "Value"],
        ["Total Unique Customers", "94,989"],
        ["Repeat Purchase Rate", "3.04%"],
        ["Average Order Value (AOV)", "R$ 160.27"],
        ["Top Revenue Segment", "Potential Loyalists (R$ 3.74M)"]
    ]

    t = Table(data, colWidths=[200, 250])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Add chart image if exists
    chart_path = os.path.join("fr4_customers", "rfm_customer_count.png")
    if os.path.exists(chart_path):
        story.append(Paragraph("<b>RFM Customer Segment Distribution:</b>", body_style))
        story.append(Spacer(1, 6))
        story.append(Image(chart_path, width=450, height=225))

    doc.build(story)
    print("PDF generated successfully:", pdf_filename)

generate_pdf_report()
