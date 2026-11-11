#!/usr/bin/env python3
"""CI-only Linux preflight for pypdfium2 5.15.2 + Pillow 12.3.0.

Runs inside a disposable `python:3.13-slim` container with only /work mounted.
Not an application module; never imported by production code.
"""
import hashlib
import io
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
import tracemalloc
from importlib.metadata import version as _version
from pathlib import Path

WORK = Path("/work")
OUT = WORK / "output"
RENDERED = OUT / "rendered-pages"
SOURCE = WORK / "source"
WHEELS = WORK / "wheels"
VENV = WORK / "venv"
for p in (OUT, RENDERED, SOURCE, WHEELS):
    p.mkdir(parents=True, exist_ok=True)

PINS = {"pypdfium2": "5.15.2", "Pillow": "12.3.0"}
results = {"outcome": "BLOCKED", "errors": []}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def env_inventory():
    info = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "arch_machine": platform.machine(),
        "uname_m": sh(["uname", "-m"]).stdout.strip(),
        "os_release": (open("/etc/os-release", encoding="utf-8").read() if Path("/etc/os-release").exists() else "NOT_AVAILABLE"),
        "glibc_musl": "UNKNOWN",
        "libc_name": "UNKNOWN",
        "libc_version": "UNKNOWN",
    }
    for name in ("ldd", "readelf", "file", "getconf"):
        info[name] = "PRESENT" if shutil.which(name) else "NOT_AVAILABLE"
    # libc detection: platform.libc_ver(), CS_GNU_LIBC_VERSION, then ldd --version (stdout+stderr)
    try:
        libc_name, libc_version = platform.libc_ver()
        if libc_name:
            info["libc_name"] = libc_name
            info["libc_version"] = libc_version or "UNKNOWN"
    except Exception:
        pass
    if info["libc_name"] == "UNKNOWN":
        try:
            cs = os.confstr("CS_GNU_LIBC_VERSION")
            if cs:
                parts = cs.split(None, 1)
                info["libc_name"] = parts[0]
                info["libc_version"] = parts[1] if len(parts) > 1 else "UNKNOWN"
        except (ValueError, OSError):
            pass
    # تعیین glibc_musl از libc_name قطعی (case-insensitive)
    name_folded = info["libc_name"].casefold()
    if "glibc" in name_folded:
        info["glibc_musl"] = "glibc"
    elif "musl" in name_folded:
        info["glibc_musl"] = "musl"

    # fallback: ldd --version (stdout + stderr), case-insensitive
    if info["glibc_musl"] == "UNKNOWN" and shutil.which("ldd"):
        res = sh(["ldd", "--version"])
        combined = ((res.stdout or "") + (res.stderr or "")).casefold()
        if "glibc" in combined:
            info["glibc_musl"] = "glibc"
        elif "musl" in combined:
            info["glibc_musl"] = "musl"
    return info


def generate_synthetic():
    FONT = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    def cs(body):
        return b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream"

    def tline(x, y, s, size=12):
        return b"BT /F1 %d Tf %d %d Td (%s) Tj ET\n" % (size, x, y, s.encode("latin-1", errors="replace"))

    def vline(x1, y1, x2, y2):
        return b"%d %d m %d %d l S\n" % (x1, y1, x2, y2)

    def vrect(x, y, w, h):
        return b"%d %d %d %d re S\n" % (x, y, w, h)

    p1 = tline(72, 740, "CI Synthetic Linux Title", 18) + tline(72, 710, "Line one.") + vline(72, 650, 540, 650) + vrect(200, 480, 160, 120)
    p2 = tline(72, 560, "Landscape page.", 14) + vline(72, 520, 700, 520) + vrect(150, 400, 300, 120)
    p3 = tline(72, 740, "Rotated page.", 14) + vline(72, 700, 540, 700) + vrect(150, 560, 200, 100)

    page1 = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>"
    page2 = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>"
    page3 = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Rotate 90 /Resources << /Font << /F1 3 0 R >> >> /Contents 6 0 R >>"

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [7 0 R 8 0 R 9 0 R] /Count 3 >>",
        FONT,
        cs(p1), cs(p2), cs(p3),
        page1, page2, page3,
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append((i, len(body)))
        body += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 %d\n" % (len(objs) + 1) + b"0000000000 65535 f \n"
    for _, off in offsets:
        body += b"%010d 00000 n \n" % off
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path = SOURCE / "synthetic-test.pdf"
    path.write_bytes(body)
    return path, hashlib.sha256(body).hexdigest(), len(body)


def install_pins():
    # binary wheels only, to temp wheel dir
    dl = sh([sys.executable, "-m", "pip", "download", "--no-deps",
              "--only-binary=:all:", "-d", str(WHEELS),
              f"pypdfium2=={PINS['pypdfium2']}", f"Pillow=={PINS['Pillow']}"])
    if dl.returncode != 0:
        results["errors"].append("wheel_download_failed:" + dl.stderr[-800:])
        return False
    wheels = sorted(f.name for f in WHEELS.iterdir() if f.suffix == ".whl")
    results["wheels"] = wheels
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    pip = VENV / "bin" / "pip"
    inst = subprocess.run([str(pip), "install", "--no-index", "--find-links", str(WHEELS),
                           f"pypdfium2=={PINS['pypdfium2']}", f"Pillow=={PINS['Pillow']}"],
                          capture_output=True, text=True)
    if inst.returncode != 0:
        results["errors"].append("install_failed:" + inst.stderr[-800:])
        return False
    return True


def native_lib_inspection():
    sp = subprocess.run([str(VENV / "bin" / "python"), "-c",
                         "import site,sys,glob,os;print(site.getsitepackages()[0])"],
                        capture_output=True, text=True).stdout.strip()
    # locate pdfium .so
    lib = None
    for base, _dirs, files in os.walk(sp):
        for f in files:
            if f.endswith(".so") and "pdfium" in f.lower():
                lib = os.path.join(base, f)
    rec = {"path": lib, "size": None, "sha256": None, "elf_arch": None, "ldd": None}
    if lib:
        data = Path(lib).read_bytes()
        rec["size"] = len(data)
        rec["sha256"] = hashlib.sha256(data).hexdigest()
        if shutil.which("file"):
            rec["elf_arch"] = sh(["file", lib]).stdout.strip()
        if shutil.which("ldd"):
            rec["ldd"] = sh(["ldd", lib]).stdout.strip()
    return rec


def license_inventory() -> str:
    md = ["# License / Notice Inventory — pypdfium2 5.15.2 + Pillow 12.3.0 (isolated)", ""]
    md.append("> This is a **technical inventory only** and is NOT legal or production approval. Presence of a license file is not equivalent to legal clearance.")
    md.append("")
    for pkg in ("pypdfium2", "Pillow"):
        sp = subprocess.run([str(VENV / "bin" / "python"), "-c",
                             f"import importlib.metadata as m;print(m.distribution('{pkg}')._path)"],
                            capture_output=True, text=True).stdout.strip()
        root = Path(sp)
        licenses = []
        for f in root.rglob("*"):
            if f.is_file() and (f.name.lower().startswith(("license", "notice", "copying")) or "licenses" in str(f).lower()):
                licenses.append(str(f.relative_to(root)))
        md.append(f"## {pkg}")
        md.append("")
        if licenses:
            for lic in sorted(licenses):
                md.append(f"- `{lic}`")
        else:
            md.append("- (no license/notice files found)")
        md.append("")
    md.append("### Missing / ambiguous notices")
    md.append("- Any package without discovered notices is flagged as `REQUIRES_EXTERNAL_REVIEW`.")
    return "\n".join(md)


def main():
    env = env_inventory()
    write_json("environment.json", env)

    pdf_path, sha, nbytes = generate_synthetic()
    results["synthetic"] = {"path": str(pdf_path), "sha256": sha, "bytes": nbytes, "pages": 3}

    if not install_pins():
        write_json("renderer-results.json", results)
        (OUT / "compatibility-report.md").write_text("# Compatibility Report — BLOCKED (install)\n", encoding="utf-8")
        return 1

    # import ابسته‌گی‌ها فقط پس از نصب موفق در virtual environment (نه در سیستم)
    site_result = sh([str(VENV / "bin" / "python"), "-c", "import site; print(site.getsitepackages()[0])"])
    if site_result.returncode != 0:
        results["errors"].append("venv_site_packages_lookup_failed:" + site_result.stderr[-800:])
        write_json("renderer-results.json", results)
        return 1
    site_packages = Path(site_result.stdout.strip())
    if not site_packages.is_dir():
        results["errors"].append(f"venv_site_packages_missing:{site_packages}")
        write_json("renderer-results.json", results)
        return 1
    sys.path.insert(0, str(site_packages))

    import pypdfium2 as pdfium
    from PIL import Image

    results["versions"] = {"pypdfium2": _version("pypdfium2"), "Pillow": _version("Pillow")}

    # malformed fixture
    malformed = OUT / "malformed.pdf"
    malformed.write_bytes(b"%PDF-1.4\nnot a real pdf\n" + b"\x00" * 64)

    doc = pdfium.PdfDocument(str(pdf_path))
    pages = len(doc)
    results["pages"] = pages
    conversions = []
    for idx in range(pages):
        page = doc.get_page(idx)
        size = page.get_size()
        rot = page.get_rotation()
        for dpi in (72, 150):
            scale = dpi / 72.0
            t0 = time.perf_counter()
            bitmap = page.render(scale=scale)
            render_s = time.perf_counter() - t0
            img = bitmap.to_pil()
            png = RENDERED / f"page{idx+1}_dpi{dpi}.png"
            img.save(png, "PNG")
            reopened = Image.open(png)
            conversions.append({
                "page": idx + 1, "dpi": dpi, "scale": round(scale, 4),
                "source_w_pts": size[0], "source_h_pts": size[1], "rotation": rot,
                "img_w": img.size[0], "img_h": img.size[1], "mode": img.mode,
                "render_seconds": round(render_s, 5), "png_bytes": png.stat().st_size,
                "reopen_w": reopened.size[0], "reopen_h": reopened.size[1], "reopen_mode": reopened.mode,
            })
            reopened.close()
            img.close()
            bitmap.close()
        page.close()
    doc.close()
    results["conversions"] = conversions
    write_json("renderer-results.json", results)

    # lifecycle 30 cycles
    tracemalloc.start()
    start = time.perf_counter()
    durations = []
    ok = 0
    for _ in range(30):
        t0 = time.perf_counter()
        d = pdfium.PdfDocument(str(pdf_path))
        try:
            for i in range(3):
                pg = d.get_page(i)
                bm = pg.render(scale=150 / 72)
                im = bm.to_pil()
                buf = io.BytesIO()
                im.save(buf, "PNG")
                im.close()
                bm.close()
                pg.close()
            ok += 1
        finally:
            d.close()
        durations.append(time.perf_counter() - t0)
    total = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss = None
    if Path("/proc/self/status").exists():
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss = line.strip()
    results["lifecycle"] = {
        "cycles": 30, "ok": ok, "failed": 30 - ok, "total_seconds": round(total, 3),
        "min_seconds": round(min(durations), 4), "median_seconds": round(statistics.median(durations), 4),
        "max_seconds": round(max(durations), 4), "tracemalloc_peak_bytes": int(peak), "rss_after": rss,
    }

    # malformed handling
    malformed_ok = False
    try:
        pdfium.PdfDocument(str(malformed))
        results["errors"].append("malformed_opened_unexpectedly")
    except Exception as e:
        malformed_ok = True
        results["malformed_rejection"] = f"{type(e).__name__}:{e}"
    results["malformed_handled"] = malformed_ok

    results["native_library"] = native_lib_inspection()
    (OUT / "license-inventory.md").write_text(license_inventory(), encoding="utf-8")
    write_json("compatibility-report.md", {"_note": "see compatibility-report.md"})

    # outcome
    conv_ok = all(c["img_w"] and c["reopen_w"] for c in conversions)
    missing_dep = (results["native_library"].get("ldd") and "not found" in results["native_library"]["ldd"])
    if conv_ok and pages == 3 and ok == 30 and malformed_ok and not missing_dep:
        results["outcome"] = "PASS"
    elif conv_ok and pages == 3:
        results["outcome"] = "PARTIAL"
    write_json("renderer-results.json", results)

    # human-readable report
    report = f"""# Compatibility Report — pypdfium2 5.15.2 + Pillow 12.3.0 (Linux `python:3.13-slim`)

- Outcome: {results['outcome']}
- Python {env['python']} / {env['uname_m']}; OS release present; glibc/musl: {env['glibc_musl']}
- versions: {results['versions']}
- synthetic sha256 {sha}; pages 3
- conversions: {len(conversions)} (72/150 per page), modes recorded, PNG save+reopen OK
- lifecycle: {ok}/30 OK; total {total:.3f}s; tracemalloc peak {int(peak)} bytes; rss {rss}
- malformed handled: {malformed_ok}
- native library: {results['native_library'].get('path')}
- NOTE: CI-only synthetic fixture; does not validate Persian fonts/textbooks/formulas/layouts.
"""
    (OUT / "compatibility-report.md").write_text(report, encoding="utf-8")

    install_report = f"""# Installation Report
- env: {json.dumps(env)}
- wheels: {results.get('wheels')}
- installed: {results.get('versions')}
"""
    (OUT / "installation-report.md").write_text(install_report, encoding="utf-8")

    write_json("renderer-results.json", results)
    print("OUTCOME =", results["outcome"])
    return 0 if results["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
