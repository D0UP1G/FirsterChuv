import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MatchProblemDetails } from '../api/client'
import { ProblemStatement } from './ProblemStatement'

const assetId = '00000000-0000-0000-0000-000000000040'

function makeProblem(statementMarkdown: string): MatchProblemDetails {
  return {
    problemId: '00000000-0000-0000-0000-000000000041',
    version: 'test-v1',
    label: 'A',
    title: 'Безопасный рендеринг',
    conditionAvailable: true,
    statementMarkdown,
    assetIds: [assetId],
    examples: [{ input: '<img src=x onerror=alert(1)>', output: '5' }],
    timeLimitMs: 1500,
    memoryLimitBytes: 64 * 1024 * 1024,
  }
}

describe('ProblemStatement', () => {
  it('renders tables, math, examples, and limits as problem content', () => {
    render(<ProblemStatement problem={makeProblem('Таблица:\n\n| x | y |\n|---|---|\n| 2 | 3 |\n\nФормула $x + y$.')} />)

    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(document.querySelector('.katex')).toBeInTheDocument()
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument()
    expect(screen.getByText(/Время: 1,5 с/)).toBeInTheDocument()
    expect(screen.getByText(/Память: 64 МиБ/)).toBeInTheDocument()
  })

  it('drops raw HTML and unsafe or non-allowlisted asset URLs', () => {
    const markdown = [
      '<script>window.compromised = true</script>',
      '<img src=x onerror="alert(1)">',
      '[Опасная ссылка](javascript:alert(1))',
      '![внешняя](https://example.test/image.png)',
      `![разрешённая](/api/v1/problem-assets/${assetId})`,
      '![чужой asset](/api/v1/problem-assets/00000000-0000-0000-0000-000000000099)',
    ].join('\n\n')

    const { container } = render(<ProblemStatement problem={makeProblem(markdown)} />)

    expect(container.querySelector('script')).not.toBeInTheDocument()
    expect(container.querySelector('[onerror]')).not.toBeInTheDocument()
    expect(container.querySelector('a[href^="javascript:"]')).not.toBeInTheDocument()
    expect(container.querySelectorAll('img')).toHaveLength(1)
    expect(container.querySelector('img')).toHaveAttribute('src', `/api/v1/problem-assets/${assetId}`)
    expect(container.querySelector('img')).toHaveAttribute('referrerpolicy', 'no-referrer')
  })
})
