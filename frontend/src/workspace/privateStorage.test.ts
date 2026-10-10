import { beforeEach, describe, expect, it } from 'vitest'
import { draftStorageKey } from './localDrafts'
import { purgePrivateBrowserData } from './privateStorage'
import { submissionKeyStorageKey } from './submissionKeys'

const scope = (userId: string) => ({ userId, runId: 'run-1', problemId: 'problem-1', languageId: 'python' })

describe('purgePrivateBrowserData', () => {
  beforeEach(() => window.localStorage.clear())

  it('removes drafts and submission keys of the signed-out user only', () => {
    const storage = window.localStorage
    storage.setItem(draftStorageKey(scope('user-1')), 'a')
    storage.setItem(submissionKeyStorageKey(scope('user-1')), 'b')
    storage.setItem(draftStorageKey(scope('user-2')), 'c')
    storage.setItem(draftStorageKey(scope('user-10')), 'd')
    storage.setItem('firsterchuv:theme', 'dark')

    purgePrivateBrowserData('user-1')

    expect(storage.getItem(draftStorageKey(scope('user-1')))).toBeNull()
    expect(storage.getItem(submissionKeyStorageKey(scope('user-1')))).toBeNull()
    expect(storage.getItem(draftStorageKey(scope('user-2')))).toBe('c')
    expect(storage.getItem(draftStorageKey(scope('user-10')))).toBe('d')
    expect(storage.getItem('firsterchuv:theme')).toBe('dark')
  })

  it('handles ids with characters that are special in regular expressions', () => {
    const storage = window.localStorage
    storage.setItem(draftStorageKey(scope('a.b(c)')), 'x')
    storage.setItem(draftStorageKey(scope('aXb(c)')), 'y')

    purgePrivateBrowserData('a.b(c)')

    expect(storage.getItem(draftStorageKey(scope('a.b(c)')))).toBeNull()
    expect(storage.getItem(draftStorageKey(scope('aXb(c)')))).toBe('y')
  })

  it('does not throw when storage is unavailable', () => {
    const broken = { get length(): number { throw new Error('blocked') } } as unknown as Storage
    expect(() => purgePrivateBrowserData('user-1', broken)).not.toThrow()
  })
})
