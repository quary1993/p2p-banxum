// IP of Webby-Soft SRL.
// The Swiss QR-bill code of the CHF deposit account, drawn from the payload of the deposit
// instructions API (moved from App.tsx with the old Add funds dialog): a PNG data URL for the
// download button and the on-screen image.
import QRCode from "qrcode";
import { useEffect, useState } from "react";

export function useQrDataUrl(payload: string) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let mounted = true;
    QRCode.toDataURL(payload, { errorCorrectionLevel: "M", margin: 1, width: 220, color: { dark: "#0a0a0a", light: "#ffffff" } })
      .then((next) => {
        if (mounted) setSrc(next);
      })
      .catch(() => {
        if (mounted) setSrc("");
      });
    return () => {
      mounted = false;
    };
  }, [payload]);
  return src;
}
