import argparse
import sys
from pathlib import Path

from .bmp_lsb import embed_text, embed_file, extract


def main(argv=None):
    parser = argparse.ArgumentParser(description="BMP LSB steganography utility")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_text = sub.add_parser("hide-text", help="Hide UTF-8 text into BMP")
    p_text.add_argument("input_bmp")
    p_text.add_argument("output_bmp")
    p_text.add_argument("text")
    p_text.add_argument("--method", type=int, default=0, choices=[0, 1, 2, 3])

    p_file = sub.add_parser("hide-file", help="Hide a file into BMP")
    p_file.add_argument("input_bmp")
    p_file.add_argument("output_bmp")
    p_file.add_argument("file_path")
    p_file.add_argument("--method", type=int, default=0, choices=[0, 1, 2, 3])

    p_extract = sub.add_parser("extract", help="Extract hidden content from BMP")
    p_extract.add_argument("input_bmp")
    p_extract.add_argument("--out", help="Output path for files; for text prints to stdout")

    args = parser.parse_args(argv)

    if args.cmd == "hide-text":
        embed_text(args.input_bmp, args.output_bmp, args.text, method=args.method)
        return 0
    if args.cmd == "hide-file":
        embed_file(args.input_bmp, args.output_bmp, args.file_path, method=args.method)
        return 0
    if args.cmd == "extract":
        kind, data, fname = extract(args.input_bmp)
        if kind == "text":
            text = data.decode("utf-8", errors="replace") if data else ""
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8")
            else:
                print(text)
        else:
            out_path = args.out or fname or "output.bin"
            Path(out_path).write_bytes(data or b"")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


