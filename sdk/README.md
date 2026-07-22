# UnifyOps Python SDK (`unifyops`)

[![PyPI Version](https://img.shields.io/pypi/v/unifyops.svg)](https://pypi.org/project/unifyops/)
[![Python Versions](https://img.shields.io/pypi/pyversions/unifyops.svg)](https://pypi.org/project/unifyops/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**UnifyOps** is an enterprise-grade AI Industrial Knowledge Intelligence Platform Python SDK for industrial plant operations. It unifies plant manuals, SOPs, work orders, incident logs, and regulatory standard specifications into a continuously-updating Knowledge Graph, exposing callable Python interfaces for:

1. **Expert Knowledge Copilot (RAG Engine)** - Hybrid graph-proximity & vector retrieval with citation grounding and confidence scoring.
2. **Maintenance Intelligence & RCA Agent** - Automated Root Cause Analysis, failure mode prediction, and maintenance timelines.
3. **Quality & Regulatory Compliance Layer** - Automated SOP gap scanning against OISD, API, PNGRB, and ISO standards.
4. **Lessons Learned Engine** - Operational failure intelligence and incident knowledge capture.

---

## 📦 Installation

```bash
pip install unifyops
```

---

## 🚀 Quickstart Guide

### 1. Initialize Client & Ingest Plant SOP Document

```python
from unifyops import UnifyOpsClient, DocumentType

# Initialize UnifyOps Client for your plant organization
client = UnifyOpsClient(org_id="refinery_unit_2")

# Ingest an SOP document into the Knowledge Graph
doc_text = """
SOP-204: Emergency Shutdown and Trip Protocol for Pump P-204.
When bearing temperature exceeds 95°C or vibration exceeds 6.5 mm/s,
execute immediate trip sequence. Refer to OISD-STD-154 for safety clearance.
"""

doc = client.ingest_document(
    text=doc_text,
    filename="SOP_Pump_P204.txt",
    document_type=DocumentType.SOP,
    plant_id="Unit-2"
)

print(f"Ingested Document ID: {doc.id} with {doc.chunk_count} chunk(s).")
```

---

### 2. Query Expert Knowledge Copilot

```python
from unifyops import CopilotQuery

# Ask a technical question to the RAG engine
query = CopilotQuery(
    query="What are the trip thresholds for Pump P-204?",
    user_role="maintenance_engineer"
)

response = client.copilot.query(query, org_id="refinery_unit_2")

print(f"Answer: {response.answer}")
print(f"Confidence Score: {response.confidence_score}%")
for citation in response.citations:
    print(f"Citation: {citation.citation_id} -> {citation.document_name}")
```

---

### 3. Execute Automated Root Cause Analysis (RCA)

```python
from unifyops import RCARequest

rca_request = RCARequest(
    equipment_tag="P-204",
    incident_description="Centrifugal pump tripped unexpectedly with high vibration and seal leak."
)

rca = client.maintenance.analyze_root_cause(rca_request, org_id="refinery_unit_2")

print(f"Equipment: {rca.equipment_tag}")
print(f"Root Cause: {rca.root_cause}")
print("Recommended Actions:")
for action in rca.recommended_actions:
    print(f"  - {action}")
```

---

### 4. Scan Regulatory Compliance Gaps

```python
from unifyops import ComplianceScanRequest

scan_req = ComplianceScanRequest(
    standard="OISD-STD-154",
    plant_unit="Unit-2"
)

report = client.compliance.scan_gaps(scan_req, org_id="refinery_unit_2")

print(f"Standard: {report.standard}")
print(f"Compliance Score: {report.compliance_percentage}%")
for gap in report.gaps:
    print(f"Gap [{gap.severity}]: {gap.description}")
    print(f"Recommendation: {gap.recommendation}")
```

---

## 🛠️ API Reference Summary

| Module | Core Class / Method | Description |
|---|---|---|
| `unifyops.client` | `UnifyOpsClient` | Main SDK orchestrator |
| `unifyops.store` | `KnowledgeStore` | Knowledge Graph & Document Chunk Registry |
| `unifyops.copilot` | `CopilotEngine` | Hybrid RAG Q&A with Grounded Citations |
| `unifyops.maintenance` | `MaintenanceEngine` | Root Cause Analysis & Maintenance Intelligence |
| `unifyops.compliance` | `ComplianceEngine` | SOP vs Regulatory Standard Gap Analysis |
| `unifyops.lessons` | `LessonsEngine` | Lessons Learned & Failure Intelligence |

---

## 📄 License

MIT License. Copyright (c) 2026 UnifyOps Team.
