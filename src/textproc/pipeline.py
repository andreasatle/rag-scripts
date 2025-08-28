from __future__ import annotations

import concurrent.futures as cf
from pathlib import Path
from typing import List, Optional, Tuple


def _load_env(env_file: Optional[Path]) -> None:
    if env_file and env_file.exists():
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(dotenv_path=env_file, override=False)
            print(f"Loaded environment from {env_file}")
        except Exception as e:
            print(f"Warning: could not load env file {env_file}: {e}")


def _find_text_files(root: Path, recursive: bool) -> List[Path]:
    if recursive:
        return sorted(p for p in root.rglob("*.txt") if p.is_file())
    return sorted(p for p in root.glob("*.txt") if p.is_file())

def _call_openai(model: str, system_prompt: Optional[str], user_content: str, timeout_seconds: float, max_tokens: int) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as import_err:
        raise RuntimeError("OpenAI SDK is not installed. Install with 'uv add .[clean]' or 'pip install .[clean]'.") from import_err
    client = OpenAI()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout_seconds,
    )
    content = getattr(resp.choices[0].message, "content", None)

    if isinstance(content, str):
        content = content.strip()

    return content or ""


def _process_one(src: Path, dst: Path, model: str, system_prompt: Optional[str], timeout_seconds: float, max_tokens: int) -> Tuple[Path, Path]:
    text = src.read_text(encoding="utf-8")
    out = _call_openai(model, system_prompt, text, timeout_seconds, max_tokens)
    if not out:
        print(f"Warning: empty model output for {src}. Writing original text.")
        out = text
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    return src, dst


HARDCODED_SYSTEM_PROMPT = (
    "You are a legal proofreader correcting OCR of land legal descriptions.\n"
    "Follow these rules strictly:\n"
    "1) Do not invent or add content. Preserve the original sequence of calls.\n"
    "2) Paragraphs:\n"
    "   - Begin new paragraphs exactly where intended (often starting with 'Thence').\n"
    "   - Separate paragraphs with exactly one empty line.\n"
    "   - Remove stray newlines within paragraphs; preserve only true breaks.\n"
    "   - The opening paragraph usually ends with ':' (e.g., 'as follows:').\n"
    "   - Subsequent paragraphs typically end with ';'.\n"
    "   - Ensure the headline has one empty line before the first paragraph.\n"
    "3) Bearings:\n"
    "   - Normalize to DMS format: dd°dd'dd\" N/S/E/W.\n"
    "4) Correct obvious OCR errors while maintaining fidelity to the source.\n"
    "5) Output only the processed legal text. No explanations, notes, or commentary."
)

def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    env_file: Optional[Path],
    model: str,
    recursive: bool,
    concurrency: int,
    timeout_seconds: float,
    max_tokens: int,
) -> int:
    _load_env(env_file)
    system_prompt = HARDCODED_SYSTEM_PROMPT

    files = _find_text_files(input_dir, recursive=recursive)
    if not files:
        print("No .txt files found")
        return 2

    tasks: List[Tuple[Path, Path]] = []
    for f in files:
        rel = f.relative_to(input_dir)
        dst = output_dir / rel
        tasks.append((f, dst))

    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_process_one, src, dst, model, system_prompt, timeout_seconds, max_tokens) for src, dst in tasks]
        for fut in cf.as_completed(futs):
            try:
                src, dst = fut.result()
                print(f"Wrote {dst}")
            except Exception as e:
                print(f"Failed processing: {e}")
    return 0


