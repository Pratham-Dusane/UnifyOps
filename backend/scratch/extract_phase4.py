with open("PRD_V1.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

with open("backend/scratch/phase4_details.txt", "w", encoding="utf-8") as out:
    for i in range(964, 1064):
        if i < len(lines):
            out.write(lines[i])

print("Phase 4 details written to backend/scratch/phase4_details.txt")
