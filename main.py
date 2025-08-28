from textract_ocr.cli import main as cli_main  # type: ignore


def main(argv: list[str] | None = None) -> int:
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())


