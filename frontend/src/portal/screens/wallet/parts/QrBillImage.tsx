// IP of Webby-Soft SRL.
// The on-screen Swiss QR-bill code of the CHF deposit account (image from qrBill.ts).
import { useT } from "../../../../i18n";

export function QrBillImage({ src }: { src: string }) {
  const t = useT();
  if (!src) return <div className="wl-qr-placeholder">{t("QR code unavailable")}</div>;
  return <img alt={t("Swiss QR-bill code of the CHF deposit account")} className="wl-qr-image" src={src} />;
}
