#!/usr/bin/env python3
"""Recalculate every formula in an .xlsx with headless LibreOffice and report formula errors.

  python recalc.py workbook.xlsx [timeout_seconds]

openpyxl writes formulas without cached values, so viewers that read cached values (pandas,
openpyxl data_only, many previews) see empty cells until something recalculates the file.
This script uses a throwaway LibreOffice profile set to "always recalculate on load", converts
the file in a temp directory, replaces the original, then scans every cell for error values.

Prints JSON and exits:
  0  {"status": "success" | "errors_found", "total_formulas", "total_errors", "errors": {...}}
  2  {"status": "error", "error": "..."}            LibreOffice ran but failed
  3  {"status": "unavailable", "error": "..."}      LibreOffice not installed — see SKILL.md fallback
"""
import json, os, shutil, subprocess, sys, tempfile

ERRORS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "Err:")
PROFILE = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>
"""


def find_office():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
              r"C:\Program Files\LibreOffice\program\soffice.exe"):
        if os.path.exists(p):
            return p
    return None


def out(obj, code):
    print(json.dumps(obj, indent=2))
    sys.exit(code)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(64)
    src = os.path.abspath(sys.argv[1])
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    office = find_office()
    if not office:
        out({"status": "unavailable", "error": "LibreOffice (soffice) not found; formulas will compute when the file is "
             "opened in Excel, LibreOffice or Google Sheets, but they were not checked here."}, 3)
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "profile", "user")
        os.makedirs(prof)
        with open(os.path.join(prof, "registrymodifications.xcu"), "w", encoding="utf-8") as f:
            f.write(PROFILE)
        outdir = os.path.join(tmp, "out")
        os.makedirs(outdir)
        cmd = [office, f"-env:UserInstallation=file://{os.path.join(tmp, 'profile')}", "--headless",
               "--convert-to", "xlsx", "--outdir", outdir, src]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            out({"status": "error", "error": f"LibreOffice timed out after {timeout}s"}, 2)
        res = os.path.join(outdir, os.path.basename(src))
        if not os.path.exists(res):
            out({"status": "error", "error": (p.stderr or p.stdout or "conversion produced no file").strip()[-500:]}, 2)
        shutil.copyfile(res, src)

    from openpyxl import load_workbook
    wf = load_workbook(src)
    wv = load_workbook(src, data_only=True)
    total, errors = 0, {}
    for ws in wf.worksheets:
        vs = wv[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    total += 1
                v = vs[c.coordinate].value
                if isinstance(v, str) and v.startswith(ERRORS):
                    errors.setdefault(v.split()[0], []).append(f"{ws.title}!{c.coordinate}")
    n = sum(len(v) for v in errors.values())
    out({"status": "errors_found" if n else "success", "total_formulas": total, "total_errors": n,
         "errors": {k: v[:50] for k, v in errors.items()}}, 0)


if __name__ == "__main__":
    main()
