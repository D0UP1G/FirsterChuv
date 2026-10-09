import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import type { Components } from 'react-markdown'
import type { MatchProblemDetails } from '../api/client'
import 'katex/dist/katex.min.css'
import './workspace.css'

const mathSanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...(defaultSchema.attributes?.code ?? []),
      ['className', 'math-inline', 'math-display'],
    ],
  },
}

function assetPath(problem: MatchProblemDetails, url: string): string | undefined {
  if (!url.startsWith('/') || url.startsWith('//')) return undefined
  let parsed: URL
  try {
    parsed = new URL(url, window.location.origin)
  } catch {
    return undefined
  }
  if (parsed.origin !== window.location.origin) return undefined
  const match = /^\/api\/v1\/problem-assets\/([0-9a-f-]{36})$/i.exec(parsed.pathname)
  if (!match || !problem.assetIds.some((assetId) => assetId.toLowerCase() === match[1].toLowerCase())) return undefined
  return parsed.pathname
}

function safeUrlTransform(problem: MatchProblemDetails, url: string, key: string): string | undefined {
  if (key === 'src') return assetPath(problem, url)
  if (key === 'href' && /^#[a-z0-9_-]+$/i.test(url)) return url
  return undefined
}

function componentsFor(problem: MatchProblemDetails): Components {
  return {
    a({ href, children }) {
      return href ? <a href={href} rel="noreferrer noopener">{children}</a> : <span>{children}</span>
    },
    img({ src, alt }) {
      const allowed = typeof src === 'string' ? assetPath(problem, src) : undefined
      return allowed ? <img src={allowed} alt={alt ?? ''} loading="lazy" referrerPolicy="no-referrer" /> : null
    },
  }
}

export function ProblemStatement({ problem }: { problem: MatchProblemDetails }) {
  return (
    <article className="problem-statement" aria-labelledby="problem-title">
      <h2 id="problem-title">{problem.title}</h2>
      <Markdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          [rehypeSanitize, mathSanitizeSchema],
          [rehypeKatex, { trust: false, maxExpand: 1000, maxSize: 20, throwOnError: false }],
        ]}
        urlTransform={(url, key) => safeUrlTransform(problem, url, key)}
        components={componentsFor(problem)}
      >
        {problem.statementMarkdown}
      </Markdown>
      <section className="problem-limits" aria-label="Ограничения задачи">
        <span>Время: {(problem.timeLimitMs / 1000).toLocaleString('ru-RU')} с</span>
        <span>Память: {(problem.memoryLimitBytes / (1024 * 1024)).toLocaleString('ru-RU')} МиБ</span>
      </section>
      {problem.examples.map((example, index) => (
        <section className="problem-example" key={`${problem.problemId}-example-${index}`}>
          <h3>Пример {index + 1}</h3>
          <div className="problem-example-grid">
            <pre><code>{example.input}</code></pre>
            <pre><code>{example.output}</code></pre>
          </div>
        </section>
      ))}
    </article>
  )
}
