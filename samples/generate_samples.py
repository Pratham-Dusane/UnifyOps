"""
Helper script to generate sample test files for UnifyOps Phase 1 manual upload.
Creates normal files, blurry files, uncertain files, P&ID file names, and a ZIP archive.
"""

import os
import zipfile
from pathlib import Path

# Create samples directory
samples_dir = Path("samples")
samples_dir.mkdir(exist_ok=True)

# 1. Create a normal PDF placeholder
normal_pdf = samples_dir / "normal_maintenance_sop.pdf"
normal_pdf.write_text("UnifyOps Standard Operating Procedure: Pump isolation steps.\n1. Isolate voltage at breaker.\n2. Close suction valves.")

# 2. Create an uncertain document classification trigger
uncertain_pdf = samples_dir / "uncertain_incident_report.pdf"
uncertain_pdf.write_text("Unclear Report: Fire alarm sounded in tray 12 crude column area. Incident under review.")

# 3. Create a blurry scan quality trigger
blurry_scan = samples_dir / "blurry_scan_degraded.jpg"
blurry_scan.write_text("Blurry text image simulation. Degraded quality check test scan.")

# 4. Create a P&ID Drawing layout trigger
pid_pdf = samples_dir / "cdu_pid_drawing.pdf"
pid_pdf.write_text("P&ID crude distillation unit 3. Pump P-204A connects to heat exchanger HE-301. Vessel V-102 outlet line.")

# 5. Create a bulk archive ZIP file containing multiple documents
zip_path = samples_dir / "bulk_archive.zip"
with zipfile.ZipFile(zip_path, "w") as zf:
    zf.writestr("archive_doc1.pdf", "Archive Document 1: Work order for boiler valve replacement.")
    zf.writestr("archive_doc2.docx", "Archive Document 2: Inspection logs for crude storage tank.")

print(f"Generated 5 sample testing files in: {samples_dir.absolute()}")
