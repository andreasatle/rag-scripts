from __future__ import annotations

from pathlib import Path
from typing import Tuple

# Lifted from root script with minimal changes

from .impl import (
    extract_links_from_docx,
    is_valid_url,
    download_file,
    save_error_report,
    save_retry_script,
    suggest_filename_from_link,
)


def process_word_document(docx_path: Path, output_dir: str | Path | None = None, dry_run: bool = False) -> None:
    docx_path = Path(docx_path)
    if not docx_path.exists() or docx_path.suffix.lower() != ".docx":
        print(f"Error: File not found: {docx_path}")
        return

    output_dir = Path(output_dir) if output_dir else docx_path.parent / f"{docx_path.stem}_files"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing: {docx_path}")
    print(f"Output directory: {output_dir}")

    links = extract_links_from_docx(str(docx_path))
    if not links:
        print("No links found in the document.")
        return

    print(f"Found {len(links)} links:")
    for i, link in enumerate(links, 1):
        print(f"  {i}. {link['text'][:60]}...")
        print(f"     URL: {link['url']}")

    links_file = output_dir / "links_found.txt"
    with open(links_file, "w", encoding="utf-8") as f:
        f.write(f"Links extracted from: {docx_path}\n")
        f.write(f"Total links: {len(links)}\n\n")
        for i, link in enumerate(links, 1):
            f.write(f"{i}. {link['text']}\n")
            f.write(f"   URL: {link['url']}\n\n")
    print(f"\nLinks saved to: {links_file}")

    if dry_run:
        print("\nDry run (no downloads). Suggested filenames:")
    else:
        print("\nDownloading files...")
    successful = 0
    total_size = 0
    failed = []
    flagged = 0  # count of suggested names differing from link text
    kept = 0     # count of names kept as-is
    for i, link in enumerate(links, 1):
        url = link["url"]
        text = link["text"]
        print(f"\n{i}/{len(links)}: {text[:50]}...")
        if not is_valid_url(url):
            print(f"  Invalid URL: {url}")
            failed.append({"url": url, "text": text, "error": "Invalid URL", "link_number": i})
            continue
        # Try legal-style suggested name first
        derived = suggest_filename_from_link(link)
        suggested = derived or text
        if dry_run:
            print(f"  URL: {url}")
            print(f"  Suggested: {suggested}")
            # Only red-flag if we had to derive the name from context (not from link text)
            if derived is not None:
                # Would the same suggestion be made from link text alone?
                from_text = suggest_filename_from_link({"text": text or "", "context": ""})
                derived_from_text = (from_text == derived)
                if not derived_from_text:
                    flagged += 1
                    prefix = (link.get('prefix') or '').strip()
                    if prefix:
                        print(f"  Context before link: '{prefix}'")
                    print("  ❌ RED FLAG: derived from context;"
                          f" text='{(text or '').strip() or '[no text]'}' -> '{suggested}'")
                else:
                    kept += 1
                    print("  ✅ OK: normalized from link text")
            else:
                kept += 1
                print("  ✅ OK: name unchanged")
            continue
        downloaded_file, size, error_info = download_file(url, output_dir, suggested)
        if downloaded_file:
            successful += 1
            total_size += size
        else:
            failed.append({"url": url, "text": text, "error": error_info, "link_number": i})

    if failed:
        error_report_file = output_dir / "failed_downloads.txt"
        save_error_report(error_report_file, failed, docx_path)
        retry_script_file = output_dir / "retry_failed_downloads.py"
        save_retry_script(retry_script_file, failed, output_dir)
        print(f"\n❌ {len(failed)} downloads failed! Report: {error_report_file}")
        print(f"🔄 Retry script: {retry_script_file}")

    print("\n" + "=" * 50)
    print("Download complete!")
    print(f"Successfully downloaded: {successful}/{len(links)} files")
    if failed:
        print(f"Failed downloads: {len(failed)} files")
    print(f"Total size: {total_size:,} bytes")
    print(f"Files saved to: {output_dir}")

    if dry_run:
        print(f"\nDry-run summary: ❌ {flagged} renamed, ✅ {kept} unchanged, total {len(links)}")


