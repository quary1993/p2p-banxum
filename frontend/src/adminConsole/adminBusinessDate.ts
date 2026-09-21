import { createContext, useContext } from "react";

export const fallbackAdminBusinessDate = new Date().toLocaleDateString("en-CA", {
  timeZone: "Europe/Zurich"
});

export const AdminBusinessDateContext = createContext(fallbackAdminBusinessDate);

export function useAdminBusinessDate() {
  return useContext(AdminBusinessDateContext);
}
