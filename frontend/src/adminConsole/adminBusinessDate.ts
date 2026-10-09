import { createContext, useContext } from "react";

// Only for the fixture preview, which has no server. The live console waits for the platform
// business date from /auth/me before it renders any form (AdminApp).
export const fallbackAdminBusinessDate = new Date().toLocaleDateString("en-CA", {
  timeZone: "Europe/Zurich"
});

export const AdminBusinessDateContext = createContext(fallbackAdminBusinessDate);

export function useAdminBusinessDate() {
  return useContext(AdminBusinessDateContext);
}
