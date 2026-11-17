# Two-page LaTeX write-up

`firmable-writeup.pdf` is compiled from the self-contained `firmable-writeup.tex`. It contains all five parts of the website write-up, including dataset selection, company-profile examples, the six Part 5 answers and the cost table. The same concise content is exported to `docs/ASSIGNMENT_ANSWERS.md` and `frontend/data/firmable-writeup.md`.

Regenerate from the repository root:

```text
python frontend/scripts/build-assignment-writeup.py
python frontend/scripts/build-writeup-latex.py
tectonic --outdir output/pdf output/pdf/firmable-writeup.tex
```

For Overleaf, upload `firmable-writeup.tex`, select it as the main document and compile with pdfLaTeX. It uses the standard `article` class, common packages and no external fonts or images. The reviewed output is exactly two A4 pages at 10-point body text, with a plain serif layout, numbered sections and page numbers. After editing, check the page count and render both pages again before publishing.

`WRITEUP.md` remains the standalone Part 5 file required by the original assignment. The website's full-report Markdown download and PDF contain Parts 1–5.
