with open("PRD_V1.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

with open("backend/scratch/prd_sections.txt", "w", encoding="utf-8") as out:
    for i, line in enumerate(lines):
        if line.startswith("##") or line.startswith("###") or "Phase 4" in line or "Stage 4" in line:
            out.write(f"Line {i+1}: {line.strip()}\n")
            
print("Search completed. Output written to backend/scratch/prd_sections.txt")
