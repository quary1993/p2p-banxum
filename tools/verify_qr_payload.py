#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import qrcode
from PIL import Image
import zxingcpp


def _decode_qr(path: Path) -> str:
    image = Image.open(path)
    results = zxingcpp.read_barcodes(image)
    qr_results = [result for result in results if str(result.format) == "BarcodeFormat.QRCode"]
    if not qr_results:
        qr_results = [result for result in results if "QR" in str(result.format)]
    if len(qr_results) != 1:
        raise SystemExit(f"Expected exactly one QR code in {path}, found {len(qr_results)}.")
    return qr_results[0].text


def _generate_qr(payload: str, output_path: Path) -> None:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _swiss_qr_summary(payload: str) -> dict[str, str]:
    lines = payload.splitlines()
    return {
        "type": lines[0] if len(lines) > 0 else "",
        "version": lines[1] if len(lines) > 1 else "",
        "account": lines[3] if len(lines) > 3 else "",
        "creditor_name": lines[5] if len(lines) > 5 else "",
        "creditor_street": lines[6] if len(lines) > 6 else "",
        "creditor_house_number": lines[7] if len(lines) > 7 else "",
        "creditor_post_code": lines[8] if len(lines) > 8 else "",
        "creditor_town": lines[9] if len(lines) > 9 else "",
        "creditor_country": lines[10] if len(lines) > 10 else "",
        "currency": lines[19] if len(lines) > 19 else "",
        "reference_type": lines[27] if len(lines) > 27 else "",
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a stored Swiss QR-bill payload against a source QR image."
    )
    parser.add_argument("--source-image", required=True, type=Path)
    parser.add_argument("--payload-file", required=True, type=Path)
    parser.add_argument("--generated-image", required=True, type=Path)
    args = parser.parse_args()

    expected_payload = args.payload_file.read_text(encoding="utf-8")
    source_payload = _decode_qr(args.source_image)
    if source_payload != expected_payload:
        raise SystemExit(
            "Source QR payload does not match payload file.\n"
            f"source_sha256={_sha256(source_payload)}\n"
            f"expected_sha256={_sha256(expected_payload)}"
        )

    _generate_qr(expected_payload, args.generated_image)
    generated_payload = _decode_qr(args.generated_image)
    if generated_payload != expected_payload:
        raise SystemExit(
            "Generated QR payload does not decode back to payload file.\n"
            f"generated_sha256={_sha256(generated_payload)}\n"
            f"expected_sha256={_sha256(expected_payload)}"
        )

    print("QR payload verification passed.")
    print(f"payload_sha256={_sha256(expected_payload)}")
    print(f"source_image={args.source_image}")
    print(f"generated_image={args.generated_image}")
    for key, value in _swiss_qr_summary(expected_payload).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
