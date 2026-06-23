# Payment Assets

The CHF deposit QR-bill payload in `chf-collector-qr-payload.txt` was decoded from the supplied Yapeal screenshot and is the source used by the BANXUM investor deposit instruction UI.

Decoded CHF collector details:

- Collection account label: `Garanta_CHF`
- Account IBAN in QR payload: `CH1183019GARANTAFI001`
- QR IBAN shown by the banking app: `CH8330334GARANTAFI001`
- BIC: `YAPECHZ2`
- Creditor: `Garanta Finanzgruppe AG`, `Schauplatzgasse 26`, `3011 Bern`, `CH`
- Currency: `CHF`
- QR reference type: `NON`

The Swiss QR payload does not include the investor-specific BANXUM payment reference. Investors must still enter the platform-generated reference, formatted as `BX-{currency}-{investor_reference}`, in their bank transfer reference or description for reconciliation.

The EUR collector account was configured from the supplied Yapeal account screenshot:

- Collection account label: `Garanta_EUR`
- Account IBAN: `CH8183019GARANTAFI002`
- BIC: `YAPECHZ2`

No EUR QR-bill payload has been supplied. The platform therefore shows the EUR IBAN/BIC and the investor-specific BANXUM payment reference, but no EUR QR code.

Verify the stored payload against a source screenshot and a generated QR image with:

```bash
uv run --with zxing-cpp --with pillow --with qrcode \
  tools/verify_qr_payload.py \
  --source-image /path/to/source-screenshot.jpg \
  --payload-file docs/payment-assets/chf-collector-qr-payload.txt \
  --generated-image /tmp/banxum-chf-collector-qr.png
```
