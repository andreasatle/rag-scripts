import argparse
import sys
from pathlib import Path
from typing import List


def split_text_minmax(text: str, min_chars: int, max_chars: int) -> List[str]:
    # Ensure valid thresholds
    if min_chars <= 0 or max_chars <= 0:
        return [text]
    if min_chars > max_chars:
        # Swap or adjust: enforce min <= max by treating max as min if misconfigured
        min_chars, max_chars = max_chars, min_chars

    chunks: List[str] = []
    current_parts: List[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_parts, current_len
        if current_parts:
            chunks.append("".join(current_parts))
            current_parts = []
            current_len = 0

    paras = text.split("\n\n")
    for para in paras:
        para_len = len(para)
        sep = "\n\n" if current_parts else ""
        extra = len(sep)
        # If paragraph itself is extremely long, split by lines/hard-cuts but still target >= min where possible
        if para_len + extra > max_chars:
            # First, if current chunk has at least min, flush before handling big para
            if current_len >= min_chars:
                flush_current()
            # Split paragraph by lines, then hard cut lines that exceed max
            lines = para.split("\n")
            acc: List[str] = []
            acc_len = 0
            for line in lines:
                piece = ("\n" if acc else "") + line
                ps = len(piece)
                # If adding keeps within max, accumulate
                if acc_len + ps <= max_chars:
                    acc.append(piece)
                    acc_len += ps
                else:
                    # If current acc is below min, allow overflow to meet min
                    if acc_len < min_chars:
                        acc.append(piece)
                        acc_len += ps
                        chunks.append("".join(acc))
                        acc = []
                        acc_len = 0
                    else:
                        # Flush acc as a chunk
                        if acc:
                            chunks.append("".join(acc))
                        # If single line is too large, hard cut it
                        if ps > max_chars:
                            s = piece
                            start = 0
                            L = len(s)
                            while start < L:
                                end = min(start + max_chars, L)
                                chunk = s[start:end]
                                # If chunk still < min and not at end, extend to meet min (overflow allowed)
                                if len(chunk) < min_chars and end < L:
                                    end = min(start + max(len(chunk), min_chars), L)
                                    chunk = s[start:end]
                                chunks.append(chunk)
                                start = end
                            acc = []
                            acc_len = 0
                        else:
                            # Start new acc with this line
                            acc = [line]
                            acc_len = len(line)
            if acc:
                # Ensure last piece meets min by merging with previous
                if len("".join(acc)) < min_chars and chunks:
                    prev = chunks.pop()
                    merged = prev + "\n" + "".join(acc)
                    chunks.append(merged)
                else:
                    chunks.append("".join(acc))
            continue

        # Normal path: paragraph fits within max
        cand_len = current_len + extra + para_len
        if cand_len <= max_chars:
            current_parts.append(sep + para if sep else para)
            current_len = cand_len
        else:
            # Exceeds max; if current below min, force include this paragraph (overflow) to satisfy min
            if current_len < min_chars:
                current_parts.append(sep + para if sep else para)
                current_len += extra + para_len
                flush_current()
            else:
                # Close current and start new chunk with this paragraph
                flush_current()
                current_parts = [para]
                current_len = para_len

    # Flush remainder, ensuring min by merging if needed
    if current_parts:
        last = "".join(current_parts)
        if len(last) < min_chars and chunks:
            prev = chunks.pop()
            chunks.append(prev + "\n\n" + last)
        else:
            chunks.append(last)
    return chunks


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="split-text-files",
        description="Split .txt files in a directory into smaller files by size",
    )
    p.add_argument("inputdir", help="Directory containing input .txt files")
    p.add_argument("outputdir", help="Directory to write split files")
    p.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    p.add_argument("--min-chars", type=int, required=True, help="Minimum characters per output chunk (except when input file itself is shorter)")
    p.add_argument("--max-chars", type=int, required=True, help="Target maximum characters per chunk; may overflow to satisfy min")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    in_dir = Path(args.inputdir)
    out_dir = Path(args.outputdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in (in_dir.rglob("*.txt") if args.recursive else in_dir.glob("*.txt")) if p.is_file())
    if not files:
        print("No .txt files found")
        return 2

    for src in files:
        text = src.read_text(encoding="utf-8")
        length = len(text)
        if length <= args.min_chars or length <= args.max_chars:
            chunks = [text]
        else:
            chunks = split_text_minmax(text, args.min_chars, args.max_chars)
        total = len(chunks)
        stem = src.stem
        rel = src.relative_to(in_dir)
        base_out_dir = out_dir / rel.parent
        base_out_dir.mkdir(parents=True, exist_ok=True)
        if total <= 1:
            dst = base_out_dir / f"{stem}.txt"
            dst.write_text(chunks[0] if chunks else "", encoding="utf-8")
            print(f"Wrote {dst}")
            continue
        for idx, chunk in enumerate(chunks, start=1):
            dst = base_out_dir / f"{stem}_split_{idx}_of_{total}.txt"
            dst.write_text(chunk, encoding="utf-8")
            print(f"Wrote {dst}")
    return 0


