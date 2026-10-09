import { describe, expect, it } from 'vitest'
import { supportsEditorLanguage } from './languageSupport'

describe('editor language IDs', () => {
  it.each(['cpp20', 'c++17', 'cxx', 'c', 'python3', 'py3', 'java21'])('loads a syntax mode for %s', (languageId) => {
    expect(supportsEditorLanguage(languageId)).toBe(true)
  })

  it('leaves compiler IDs outside the implemented editor modes as plain text', () => {
    expect(supportsEditorLanguage('rust')).toBe(false)
  })
})
