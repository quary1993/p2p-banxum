// IP of Webby-Soft SRL.
// U33-DEC-31: the interface language chosen in the investor area applies at once (the page, its state
// and the entered data stay) and is saved in the account, so it follows the investor to every device
// and to emails and notifications.
import { useEffect } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { getV1AuthMeRetrieveQueryKey, useV1AuthPreferencesDisplayPartialUpdate } from "../api/generated/banxumApi";
import {
  applyAccountLanguage,
  chooseLanguage,
  getPreferredLanguage,
  hasUnsavedLanguageChoice,
  markLanguageChoiceSaved,
  parseInterfaceLanguage,
  type InterfaceLanguage
} from "../i18n/language";
import { isFixturePreview } from "./data";

// True while a signed-in investor area that may save preferences is mounted (useAccountLanguageSync).
let saveInAccount = false;

function useSaveLanguage() {
  const queryClient = useQueryClient();
  const mutation = useV1AuthPreferencesDisplayPartialUpdate();
  return (language: InterfaceLanguage) =>
    mutation.mutate(
      { data: { language } },
      {
        onSuccess: () => {
          markLanguageChoiceSaved();
          void queryClient.invalidateQueries({ queryKey: getV1AuthMeRetrieveQueryKey() });
        }
      }
    );
}

/** Changes the language; signed in (and not in a preview or read-only view) it is saved in the account. */
export function useSetInterfaceLanguage() {
  const save = useSaveLanguage();
  return (language: InterfaceLanguage) => {
    void chooseLanguage(language);
    if (saveInAccount && !isFixturePreview) save(language);
  };
}

/**
 * After sign-in: a language chosen before sign-in (or with ?lang= from the public site) is saved in
 * the account; otherwise the account's language applies. A read-only view keeps the viewer's language.
 */
export function useAccountLanguageSync(accountLanguage: string | null | undefined, { canSave }: { canSave: boolean }) {
  const save = useSaveLanguage();
  const account = parseInterfaceLanguage(accountLanguage);
  useEffect(() => {
    saveInAccount = canSave && Boolean(account);
    return () => {
      saveInAccount = false;
    };
  }, [account, canSave]);
  useEffect(() => {
    if (!account || !canSave || isFixturePreview) return;
    if (hasUnsavedLanguageChoice()) {
      const chosen = getPreferredLanguage();
      if (chosen === account) markLanguageChoiceSaved();
      else save(chosen);
      return;
    }
    void applyAccountLanguage(account);
    // `save` is a new function each render; the effect only runs again when the account changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account, canSave]);
}
