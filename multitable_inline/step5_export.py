import csv
import os


def export_parts(parts, output_csv):
    if not parts:
        return output_csv

    out_dir = os.path.dirname(output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["page", "title", "part_no", "description"])

        for p in parts:
            writer.writerow([
                p["page"],
                p.get("title", ""),
                p["part_no"],
                p["description"]
            ])

    return output_csv
