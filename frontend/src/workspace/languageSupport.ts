export function supportsEditorLanguage(languageId: string): boolean {
  const normalized = languageId.toLowerCase().replace(/[._+\-\s]/g, '')
  return /^(cpp|cxx|c)(?:\d{1,4})?$/.test(normalized)
    || /^(python|py)(?:\d{1,2})?$/.test(normalized)
    || /^java(?:\d{1,2})?$/.test(normalized)
}
