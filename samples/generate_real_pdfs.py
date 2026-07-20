import subprocess
import sys
import os

# 1. Install reportlab
print("Installing reportlab for PDF generation...")
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
except Exception as e:
    print(f"Failed to install reportlab: {e}")

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_pdf(filename, title, content_paragraphs):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=15
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=11,
        leading=15,
        spaceAfter=10
    )
    
    story = [
        Paragraph(title, title_style),
        Spacer(1, 10)
    ]
    
    for p in content_paragraphs:
        story.append(Paragraph(p, body_style))
        
    doc.build(story)
    print(f"Generated valid PDF: {filename}")

# Generate real sample files
# 1. Regulatory Standard (OISD-STD-189)
create_pdf(
    "samples/real_regulatory_standards.pdf",
    "Federal Safety & Compliance Regulation: OISD-STD-189",
    [
        "Document: OISD-STD-189. Category: Safety Legislation.",
        "This document outlines mandatory guidelines for isolation procedures and lockout safety in industrial distillation plants.",
        "Rule 12.1: Electrical Isolation (LOTO) Rule 12.1: Electrical switchgear panels must be isolated and locked out (LOTO) using physical padlocks prior to starting mechanical repair on heavy pumps. No technician shall work on pump systems like P-204 without LOTO confirmation.",
        "Rule 12.2: Stale Safety SOP Reviews Rule 12.2: Governing safety procedures and LOTO checklists must be reviewed and re-approved by the plant manager annually to ensure procedures are not stale.",
        "Rule 12.3: Unresolved Non-Conformance checks Rule 12.3: Plant supervisors must verify that any active LOTO incidents or safety non-conformance records on equipment like pump P-204 are resolved before resuming operational status."
    ]
)

# 2. SOP-17: P-204 Maintenance
create_pdf(
    "samples/sop_17_p204_maintenance.pdf",
    "SOP-17: Reflux Pump P-204 Maintenance Procedure",
    [
        "Document Type: Standard Operating Procedure (SOP)",
        "Target Equipment: P-204 (Reflux Pump, Crude Distillation Unit)",
        "Last Reviewed: January 2025 (Overdue for review)",
        "1. PREPARATION:",
        "Ensure LOTO is applied to P-204 electrical breaker as per OISD-STD-189 Rule 12.1.",
        "2. MECHANICAL SEAL REPLACEMENT:",
        "Remove coupling guard. Detach the pump casing. Remove the mechanical seal assembly.",
        "Install new mechanical seal. NOTE: Use Graphite Grade A gaskets for all flange connections.",
        "3. REASSEMBLY:",
        "Reattach the casing and tighten bolts to 120 Nm. Reinstall the coupling guard securely. Failure to reinstall the guard is a violation of Factory Act Section 41.",
        "4. TESTING:",
        "Remove LOTO. Start pump P-204 and monitor bearing temperature for 30 minutes. If temperature exceeds 85°C, shut down immediately."
    ]
)

# 3. Incident Report INC-2025
create_pdf(
    "samples/inc_2025_report.pdf",
    "Incident Report: INC-2025 (P-204 Seal Failure)",
    [
        "Document Type: Incident Investigation Report",
        "Incident ID: INC-2025",
        "Date of Occurrence: 15-May-2025",
        "Equipment Involved: Reflux Pump P-204, Pump P-205",
        "Unit: Crude Distillation Unit (CDU)",
        "INCIDENT DESCRIPTION:",
        "At 14:30 hrs, a significant hydrocarbon leak was detected from the mechanical seal of pump P-204. The unit was safely shut down. A subsequent check of the standby pump, P-205, revealed that its coupling guard had been removed during maintenance under WO-2025-0441 and never reinstalled.",
        "ROOT CAUSE ANALYSIS:",
        "1. The mechanical seal on P-204 failed due to the use of an incompatible gasket. SOP-17 incorrectly specifies Graphite Grade A gaskets, whereas the fluid service requires Graphite Grade C.",
        "2. The missing coupling guard on P-205 is a direct violation of Factory Act Section 41.",
        "RECOMMENDATIONS:",
        "1. Immediately revise SOP-17 to specify Graphite Grade C gaskets. Review all other pump SOPs for similar errors.",
        "2. Audit all rotating equipment in the CDU to ensure coupling guards are installed.",
        "3. Deploy a proactive warning to all field technicians regarding proper gasket selection and guard installation."
    ]
)
# 2. Safety Procedure SOP
create_pdf(
    "samples/real_maintenance_sop.pdf",
    "Standard Operating Procedure: Pump Isolation & Maintenance",
    [
        "Document ID: SOP-COKE-OVEN-14. Version: 2.1.",
        "Governing Equipment: Pump P-204, Pump P-205, Heat Exchanger HE-301.",
        "This document describes the safety steps required before performing coupling alignment or bearing replacement on critical unit pumps.",
        "<b>Step 1: Electrical Isolation (LOTO)</b> Isolate the primary breaker at switchgear panel CP-03. Apply physical lock and LOTO tag. Verify isolation by attempting a local start.",
        "<b>Step 2: Process Isolation</b> Close suction valve HV-204A and discharge valve HV-204B. Open drain valve DV-204 to depressurize casing. Confirm pressure gauge reads 0 PSI before opening pump casing.",
        "<b>Step 3: Mechanical Alignment</b> When replacing bearings, ensure coupling alignment is checked using the laser alignment tool. Misalignment of coupling must not exceed 0.05 mm."
    ]
)

# 3. Incident Report 1 (Pump P-204 High Vibration)
create_pdf(
    "samples/real_incident_report_1.pdf",
    "Incident Report: Pump P-204 Tripping Event",
    [
        "Incident ID: INC-2025-882. Date: 2025-06-15. Plant Area: Unit 3 Distillation.",
        "Description: At 14:15, pump P-204 tripped on high vibration and motor overcurrent. The backup pump P-205 was started manually to maintain crude flow.",
        "Root Cause Analysis (RCA): Inspection revealed mechanical bearing failure on the pump shaft. High vibration caused coupling misalignment. The shaft bearings showed severe scoring due to lack of lubrication and deferred maintenance.",
        "Corrective Actions: Replaced bearings with SKF 6205. Realigned coupling. Updated maintenance schedule to inspect lubrication levels bi-weekly."
    ]
)

# 4. Incident Report 2 (Valve V-301 Overpressure Leakage)
create_pdf(
    "samples/real_incident_report_2.pdf",
    "Incident Report: Valve V-301 Leakage",
    [
        "Incident ID: INC-2025-889. Date: 2025-06-18. Plant Area: Unit 3 Distillation.",
        "Description: Steam leakage was observed from control valve V-301 flange gasket.",
        "Root Cause Analysis (RCA): The gasket degradation was due to deferred maintenance. Flange bolts were loose and showed corrosion.",
        "Corrective Actions: Flange gasket replaced with high-temperature graphite gasket. Flange bolts retorqued."
    ]
)

# 5. Incident Report 3 (Pump P-204 Gasket Blowout)
create_pdf(
    "samples/real_incident_report_3.pdf",
    "Incident Report: Pump P-204 Gasket Swap Failure",
    [
        "Incident ID: INC-2025-894. Date: 2025-06-22. Plant Area: Unit 3 Distillation.",
        "Description: Pump P-204 experienced minor fluid blowout from casing during restart.",
        "Root Cause Analysis (RCA): The blowout occurred due to operator error and procedural violation. The torque sequence for the gasket casing bolts was not followed properly.",
        "Corrective Actions: Gasket replaced, bolts retorqued using standard star-pattern torque sequence."
    ]
)

# 6. Work Order (For Triggering Warnings)
create_pdf(
    "samples/real_work_order_p204.pdf",
    "Work Order: Pump P-204 Shaft Realignment",
    [
        "Work Order ID: WO-991244. Date: 2025-06-25. Asset Tag: P-204.",
        "Description: Perform laser coupling alignment and bearing greasing on Pump P-204 shaft.",
        "Target Equipment: Pump P-204. Target Location: Unit-A.",
        "Assigned Department: Mechanical Maintenance. Supervisor: Priya."
    ]
)
