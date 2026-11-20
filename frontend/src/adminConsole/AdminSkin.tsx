// IP of Webby-Soft SRL.
/*
 * Skin of the admin console (audit S4-9): while mounted, <html> has the class "bxa". The build scopes
 * every rule of styles.css to html.bxa (adminCssScope.ts), so the admin stylesheet styles nothing when
 * the investor area or the public site is on screen, also after the admin console was open in the same
 * tab. A mount counter keeps it right under StrictMode double effects (like SiteSkin and U33Skin).
 */
import { useLayoutEffect, type ReactNode } from "react";

const ADMIN_SKIN_CLASS = "bxa";
let adminSkinMounts = 0;

export function AdminSkin({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    adminSkinMounts += 1;
    const html = document.documentElement;
    html.classList.add(ADMIN_SKIN_CLASS);
    return () => {
      adminSkinMounts -= 1;
      if (adminSkinMounts <= 0) {
        adminSkinMounts = 0;
        html.classList.remove(ADMIN_SKIN_CLASS);
      }
    };
  }, []);
  return <>{children}</>;
}
