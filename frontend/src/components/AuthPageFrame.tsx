import type { ReactNode } from 'react'

interface AuthPageFrameProps {
  eyebrow: string
  title: string
  description: string
  footer: ReactNode
  children: ReactNode
}

export function AuthPageFrame({ eyebrow, title, description, footer, children }: AuthPageFrameProps) {
  return (
    <section className="auth-layout">
      <aside className="auth-aside">
        <span className="auth-aside-mark" aria-hidden="true">Б</span>
        <p className="eyebrow">{eyebrow}</p>
        <h2>Свой темп.<br /><span>Своя игра.</span></h2>
        <p className="auth-aside-copy">Блиц объединяет игроков, организаторов и зрителей вокруг одного матча.</p>
        <div className="auth-aside-rule"><span>ПЕРВЕНСТВО ЧУВАШИИ</span><span>2026</span></div>
      </aside>
      <div className="auth-card">
        <div className="auth-card-heading">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {children}
        <div className="auth-footer">{footer}</div>
      </div>
    </section>
  )
}
