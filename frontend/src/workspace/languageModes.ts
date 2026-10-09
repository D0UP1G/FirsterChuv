import { cpp } from '@codemirror/lang-cpp'
import { java } from '@codemirror/lang-java'
import { python } from '@codemirror/lang-python'

export { cpp, java, python }

export function languageExtension(languageId: string) {
  const normalized = languageId.toLowerCase().replace(/[._+\-\s]/g, '')
  if (/^(cpp|cxx|c)(?:\d{1,4})?$/.test(normalized)) return cpp()
  if (/^(python|py)(?:\d{1,2})?$/.test(normalized)) return python()
  if (/^java(?:\d{1,2})?$/.test(normalized)) return java()
  return null
}
