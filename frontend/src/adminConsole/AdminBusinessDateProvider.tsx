import type { ReactNode } from "react";
import {
  AdminBusinessDateContext,
  fallbackAdminBusinessDate
} from "./adminBusinessDate";

export function AdminBusinessDateProvider({
  businessDate,
  children
}: {
  businessDate: string;
  children: ReactNode;
}) {
  return (
    <AdminBusinessDateContext.Provider value={businessDate || fallbackAdminBusinessDate}>
      {children}
    </AdminBusinessDateContext.Provider>
  );
}
