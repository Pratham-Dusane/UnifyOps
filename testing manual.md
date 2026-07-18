# UnifyOps — Manual Testing Guide

This manual testing guide provides step-by-step instructions to verify all core functional features of the UnifyOps platform. It details prerequisites, input test data, UI click flows, and expected results.

---

## Prerequisites & Setup

### 1. Run the Backend API
Navigate to the `backend` directory, activate your virtual environment, and start the Uvicorn reload server:
```bash
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```
- Verify API docs are accessible at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run the Frontend Web Application
Navigate to the `frontend` directory and start the Next.js development server:
```bash
cd frontend
npm run dev
```
- Open the application in your browser at: [http://localhost:3000](http://localhost:3000)

### 3. Log In / Register
- Go to [http://localhost:3000/login](http://localhost:3000/login) (or register a test user first at `/register`).
- Default credentials will log you in to the plant workspace. Select any role (e.g., **Plant Head** or **Supervisor**) to begin.

---

## Feature 1: Document Ingestion Pipeline & Review Queue (Phases 1 & 2)

Tests uploading documents and verifying that they are correctly classified and indexed.

### Steps to Test:
1. Click **Documents** in the left navigation sidebar.
2. In the upload dropzone, upload a sample PDF, Word document, or Text file.
   * *Example Test File*: Create a simple text file containing:
     ```text
     WORK ORDER WO-402
     Equipment Tag: P-204 Reflux Pump
     Plant Area: CDU-1
     Task: Swap graphite gasket and perform shaft alignment. Overdue maintenance since March.
     ```
3. Click the **Upload** button.
4. Locate the newly uploaded file in the list below. It will show a loading spinner through the pipeline stages: `UPLOADED` ➔ `TEXT_EXTRACTED` ➔ `CLASSIFYING` ➔ `ENTITIES_EXTRACTED` ➔ `COMPLETED`.
5. Click on the document name. Verify that the correct document type (**Work Order**) and extracted entities (e.g., `P-204`) are listed.
6. Click **Review Queue** in the sidebar. If the classification confidence was low or a manual check was flagged, click **Edit/Verify** to adjust the extracted entities, then click **Approve Record** to finalize graph ingestion.

---

## Feature 2: Expert Knowledge Copilot (Phase 3)

Tests query retrieval, citations, language localization, hands-free voice, and offline fallback.

### Steps to Test:
1. Click **Copilot Chat** in the left navigation sidebar.
2. **Basic Query**:
   - Type: `What gasket is recommended for reflux pump P-204?` and press Enter.
   - **Expected Result**: An answering card surfaces indicating that a graphite swap gasket is recommended. Verify that a bracketed source tag (e.g., `[Captured Knowledge: P-204 gasket swap]`) is displayed. Click the citation link to verify it navigates to the document source viewer.
3. **Multi-Turn Context (Follow-Up)**:
   - Immediately follow up by typing: `What is its torque value?` (without repeating the pump tag).
   - **Expected Result**: Copilot resolves the context to P-204 and answers: `The torque sequence for graphite gaskets requires a cross-pattern torque of 85 Nm.`
4. **Hands-Free Voice Interface (Speech-to-Text & Text-to-Speech)**:
   - Click the **Microphone** icon inside the chat bar. Grant browser microphone permissions when prompted.
   - Speak your query clearly. Verify that the voice is transcribed into the input field.
   - Click the **Speaker** icon on any Assistant reply card. Verify the browser synthesizes voice and reads back the text (automatically ignoring citation bracket tags).
5. **Language Switching**:
   - Click **Settings** in the left sidebar, and change the preferred language to **Hindi (हिन्दी)** or **Marathi (मराठी)**.
   - Go back to Copilot and ask a query. Verify the reply is translated. Click the Speaker icon to verify speech synthesis matches the selected language.
6. **Offline-First Resilience**:
   - Disconnect your internet connection (or toggle the browser to Offline Mode in developer tools).
   - Verify that an **"Offline Mode"** banner appears in the header.
   - Ask a cached query (e.g., `P-204 gasket torque`). Verify the copilot answers immediately using the local cache.
   - Click the **Upvote / Downvote** button on the reply. Reconnect the internet. Verify that cached feedback synchronization runs and sends queued votes to the backend.

---

## Feature 3: Maintenance Advisor & RCA Workspace (Phase 4)

Tests plant risk telemetry, timelines, collaborative root cause analysis, and camera lookup.

### Steps to Test:
1. Click **Maintenance** in the left navigation sidebar.
2. **Plant Attention Map**:
   - Observe the grid representing high-risk equipment tags. Verify that **P-204** is listed with a high risk score (e.g. `86%`) and highlighted in red/amber.
3. **Dynamic Timeline**:
   - Click on the **P-204** card.
   - Verify that a unified chronological timeline appears below, grouping drawings (P&ID), SOP isolation steps, recent work orders, and historical incident report events for P-204.
4. **Automated RCA Generation**:
   - Click the **Generate RCA Draft** button.
   - **Expected Result**: A structured Root Cause Analysis document is created containing: *Summary, Event Timeline, Physical Evidence Analysis, Human/Organizational Factors, and Action Items*.
5. **RCA Collaborative Loop**:
   - Scroll to the RCA draft block sections. Click the **Edit** icon next to any section. Add manual technician notes (e.g., `Added safety checks for gasket thermal expansion during CDU restart`). Click **Save**.
   - Rate the criticality using the slider, choose actions, and click **Approve and Export RCA**. Verify it compiles into a final printable PDF/Markdown document.
6. **Camera-Based Lookup**:
   - Click **Camera Lookup** next to the equipment search bar on the Maintenance Dashboard.
   - Grant device camera permissions and simulate taking a photo of a nameplate, or upload a photo (e.g. `p-204_plate.jpg`).
   - **Expected Result**: The OCR service processes the photo, extracts `P-204`, and redirects you directly to the P-204 timeline page.

---

## Feature 4: Quality & Regulatory Compliance (Phase 5)

Tests regulatory clause parsing, compliance gap scans, and audit package compilation.

### Steps to Test:
1. Click **Compliance** in the left navigation sidebar.
2. **Clause Segmenter**:
   - Upload a regulatory manual under the Compliance section (or observe already parsed rules).
   - Verify that regulations are split into numbered verbatim clauses with simplified, plain-language summaries for technicians.
3. **Compliance Gap Scan**:
   - Click **Run Gap Agent**.
   - **Expected Result**: The agent scans safety SOPs and identifies non-conformance flags. Verify that the following gaps appear in the table:
     * *Missing Procedure*: Clause lacks a linked safety procedure.
     * *Stale SOP*: Linked procedure has not been revised in over 12 months.
     * *Unresolved Incident*: An active incident report remains open against the equipment.
4. **Audit Evidence Packager**:
   - Select multiple clauses using the checkboxes in the list.
   - Click **Assemble Audit Evidence Package**.
   - **Expected Result**: A compiled audit report is generated containing the regulatory requirements, governing procedures, and active gap records, formatted with inline citations. Click **Export Audit Package** to download.

---

## Feature 5: Lessons Learned & Proactive Warning Engine (Phase 6)

Tests structured incident summaries, pattern detection, and real-time warnings.

### Steps to Test:
1. Click **Lessons Learned** in the left navigation sidebar.
2. **Incident Enrichment**:
   - Open any ingested Incident Report document. Verify that the platform has structured it into: *Incident Severity, Contributing Conditions (e.g., Training Gap, Inadequate Maintenance), and Actions Taken*.
3. **Pattern Detection Agent**:
   - Click **Detect Cross-Incident Patterns**.
   - **Expected Result**: The system clusters incidents. Verify it displays candidate patterns such as: `Recurring 'Inadequate Maintenance' condition detected across 3 incidents involving reflux pumps`.
   - Click **Confirm Pattern** to move the pattern from Candidate to Active.
4. **Proactive Warning Alert**:
   - Navigate back to **Documents** and upload a new Work Order or Permit file that mentions the same equipment tag (e.g. `P-204`) or shared factors of the confirmed pattern.
   - **Expected Result**: A modal alert/notification banner pops up immediately stating: `Pattern Alert: A confirmed failure pattern involving P-204 has been triggered by your upload. Review the pattern evidence before starting work.`

---

## Feature 6: Expert Knowledge Capture (Phase 7)

Tests query gap suggestions, guided conversational interview loops, and graph ingestion.

### Steps to Test:
1. Click **Knowledge Capture** in the left navigation sidebar.
2. **Suggested Topics**:
   - Verify a list of suggested interview topics appears, scored by criticality and documented depth.
   - *Example topic*: `P-204 bearing temperature spikes and gasket selection`.
3. **Start Guided Interview**:
   - Click **Start Interview** next to any topic.
   - **Expected Result**: The guided agent asks the first technically precise question (e.g., `Could you describe the specific operating symptoms you observed during the gasket maintenance?`).
4. **Interview Turn Loop**:
   - Type your answer in the text box (e.g., `We noticed the gasket faces were warped, and we swapped them out with graphite gaskets`) and click **Send**.
   - Repeat the conversation loop for 4 turns. The progress tracker will count up to 4.
5. **Synthesise Transcript**:
   - After the 4th response, verify the agent automatically compiles the conversation into a structured markdown document containing: *Metadata, Summary, Deep Technical Procedures, and Prevention Rules*.
6. **Graph Ingestion**:
   - Click **Approve and Ingest**.
   - **Expected Result**: The transcript is saved as a new document source. Navigate to the **Documents** page to verify the new captured knowledge document is listed, with entities fully linked to the graph.
