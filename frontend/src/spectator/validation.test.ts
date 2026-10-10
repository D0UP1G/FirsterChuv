import { describe, expect, it } from 'vitest'
import { PublicProtocolError } from './types'
import { validatePublicBracket } from './validation'

function bracket(id: string) {
  return {
    tournamentId: '00000000-0000-0000-0000-000000000001',
    title: 'Публичный турнир',
    bracketSize: 2,
    matches: [{
      id, key: 'r1-p1', roundIndex: 0, position: 0, status: 'READY',
      slots: [{ displayName: 'Ира' }, { displayName: 'Олег' }], winnerName: null,
    }],
  }
}

describe('public identifier validation', () => {
  it('accepts canonical UUIDs from imported packages, including the all-zero demo prefix', () => {
    expect(validatePublicBracket(bracket('00000000-0000-0000-0000-000000000101')).matches[0].id)
      .toBe('00000000-0000-0000-0000-000000000101')
  })

  it('still rejects text that is not a canonical UUID', () => {
    for (const value of ['not-a-uuid', '00000000-0000-0000-0000-00000000010', '../../etc/passwd', '']) {
      expect(() => validatePublicBracket(bracket(value))).toThrow(PublicProtocolError)
    }
  })
})
