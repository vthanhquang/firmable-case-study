"""Export all five report sections to a plain, Overleaf-compatible LaTeX article."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/pdf"


def tex(value):
    value = str(value).replace("—", "--").replace("–", "--").replace("’", "'").replace("→", " to ")
    substitutions = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                     "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(substitutions.get(char, char) for char in value)


def build():
    report = json.loads((ROOT / "frontend/data/assignment-writeup.json").read_text(encoding="utf-8"))
    c = report["cost"]
    lines = [r"\documentclass[10pt,a4paper]{article}",
             r"\usepackage[top=22mm,bottom=20mm,left=20mm,right=20mm,headheight=14pt]{geometry}",
             r"\usepackage[T1]{fontenc}",
             r"\usepackage{lmodern,microtype,booktabs,tabularx,enumitem,titlesec,fancyhdr,hyperref}",
             r"\hypersetup{hidelinks,pdftitle={Firmable Case Study: Parts 1--5},pdfauthor={Project owner}}",
             r"\pagestyle{fancy}\fancyhf{}\fancyhead[L]{Firmable Case Study}\fancyhead[R]{Parts 1--5}",
             r"\fancyfoot[C]{\thepage\ / 2}\renewcommand{\headrulewidth}{0.4pt}",
             r"\setlength{\parindent}{0pt}\setlength{\parskip}{3pt}\setlength{\emergencystretch}{2em}",
             r"\titleformat{\section}{\large\bfseries}{\thesection}{0.7em}{}",
             r"\titlespacing*{\section}{0pt}{7pt}{3pt}",
             r"\setlist[itemize]{leftmargin=1.4em,itemsep=1pt,topsep=3pt,parsep=0pt}",
             r"\renewcommand{\arraystretch}{1.1}\setlength{\tabcolsep}{5pt}",
             r"\begin{document}",
             r"\begin{center}{\Large\bfseries Firmable -- Case Study}\\[4pt]",
             r"Discovery, mapping, entity identification and company profiles\end{center}",
             r"\vspace{2pt}\hrule\vspace{5pt}", tex(report["context"]) + r"\par"]
    for part in report["parts"]:
        lines.append(r"\section{" + tex(part["title"].split(" — ", 1)[1]) + "}")
        lines += [tex(p) + r"\par" for p in part.get("selection", [])]
        for key in ("dataset_contributions", "profile_capabilities", "profile_examples"):
            if part.get(key):
                lines.append(r"\begin{itemize}")
                for row in part[key]:
                    lines.append(r"\item \textbf{" + tex(row["name"]) + ".} " + tex(row["detail"]))
                lines.append(r"\end{itemize}")
        lines += [tex(p) + r"\par" for p in part["answer"]]
    lines += [r"\newpage", r"\section{Engineering decisions}"]
    for item in report["part5"]:
        lines.append(r"\noindent\textbf{" + tex(item["title"]) + r".}\par")
        if item.get("show_cost_table"):
            lines += [r"Model: \texttt{" + tex(c["model"]) + r"}. USD per million tokens; uncached input.\par",
                      r"\begin{tabularx}{\linewidth}{@{}Xrr@{}}\toprule",
                      r"Price basis & Input & Output \\\midrule",
                      *[f"{tex(row['period'])} & \\${row['input']:.2f} & \\${row['output']:.2f} \\\\" for row in c["rates"]],
                      r"\bottomrule\end{tabularx}\par\vspace{4pt}",
                      r"\begin{tabularx}{\linewidth}{@{}Xrrr@{}}\toprule",
                      r"Assignment part & Input tokens & Output tokens & Est. USD \\\midrule"]
            names = ["1. Discovery and triage", "2. Schema inference and mapping", "3. Entity identification", "4. Company profiles"]
            for name, row in zip(names, c["usage"]):
                lines.append(f"{tex(name)} & {row['input_tokens']:,} & {row['output_tokens']:,} & \\${row['estimated_usd']:.2f} \\\\")
            total = c["total"]
            lines += [r"\midrule", f"\\textbf{{Total}} & \\textbf{{{total['input_tokens']:,}}} & \\textbf{{{total['output_tokens']:,}}} & \\textbf{{\\${total['estimated_usd']:.2f}}} \\\\",
                      r"\bottomrule\end{tabularx}\par", tex(c["note"]) + r" \href{" + c["source_url"] + r"}{Model pricing reference.}\par"]
        lines += [tex(p) + r"\par" for p in item["answer"]]
        lines.append(r"\vspace{4pt}")
    lines += [r"\end{document}"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "firmable-writeup.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT / "firmable-writeup.tex")


if __name__ == "__main__":
    build()
