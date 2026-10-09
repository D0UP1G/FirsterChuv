import { lazy, Suspense, useState, type ReactNode } from 'react'
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router'
import { ApiError, type UserRole } from './api/client'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { AdminTournamentsPage } from './pages/AdminTournamentsPage'
import { AdminTournamentPage } from './pages/AdminTournamentPage'
import { AdminMatchPage } from './pages/AdminMatchPage'
import { InvitePage } from './pages/InvitePage'
import './App.css'
import './responsive.css'

const ParticipantWorkspacePage = lazy(() => import('./pages/ParticipantWorkspacePage').then((module) => ({ default: module.ParticipantWorkspacePage })))
const SpectatorMapPage = lazy(() => import('./spectator/SpectatorMapPage').then((module) => ({ default: module.SpectatorMapPage })))

function App() {
  return <AuthProvider><BrowserRouter><AppFrame /></BrowserRouter></AuthProvider>
}

function AppFrame() {
  const location = useLocation()
  const isProjector = location.pathname.startsWith('/watch/') && new URLSearchParams(location.search).get('projector') === '1'
  return (
    <div className={isProjector ? 'app-frame app-frame-projector' : 'app-frame'}>
      <a className="skip-link" href="#main-content">Перейти к содержимому</a>
      {!isProjector && <Header />}
      {!isProjector && <AuthStatusNotice />}
      <main id="main-content" className="main-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/watch" element={<PublicViewerPage />} />
          <Route path="/watch/:tournamentId" element={<Suspense fallback={<LoadingState label="Загружаем зрительскую карту…" />}><SpectatorMapPage /></Suspense>} />
          <Route path="/watch/:tournamentId/matches/:matchId" element={<Suspense fallback={<LoadingState label="Загружаем зрительскую карту…" />}><SpectatorMapPage /></Suspense>} />
          <Route path="/invites/:token" element={<InvitePage />} />
          <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route path="/admin" element={<RequireRole role="admin"><AdminTournamentsPage /></RequireRole>} />
          <Route path="/admin/tournaments/:tournamentId" element={<RequireRole role="admin"><AdminTournamentPage /></RequireRole>} />
          <Route path="/admin/tournaments/:tournamentId/matches" element={<RequireRole role="admin"><AdminMatchPage /></RequireRole>} />
          <Route path="/matches/:matchId" element={<RequireRole role="participant"><Suspense fallback={<LoadingState label="Загружаем рабочее место…" />}><ParticipantWorkspacePage /></Suspense></RequireRole>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      {!isProjector && <Footer />}
    </div>
  )
}

function Header() {
  const { status, user, signOut, retry } = useAuth()
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleSignOut() {
    setSignOutError(null)
    try {
      await signOut()
      navigate('/', { replace: true })
    } catch (error) {
      setSignOutError(errorMessage(error))
    }
  }

  return (
    <>
      <header className="site-header">
        <Link className="brand" to="/" aria-label="BLITZ_ARENA — на главную">
          <span className="brand-mark" aria-hidden="true">Б</span>
          <span>BLITZ_<span className="brand-accent">ARENA</span></span>
        </Link>
        <nav className="primary-nav" aria-label="Основная навигация">
          <NavLink to="/watch" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Зрителям</NavLink>
          {status === 'authenticated' && <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Кабинет</NavLink>}
          {status === 'authenticated' && user?.role === 'admin' && <NavLink to="/admin" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Организатору</NavLink>}
        </nav>
        <div className="account-nav">
          {status === 'authenticated' && user ? (
            <>
              <span className="account-name" title={user.displayName}>{user.displayName}</span>
              <span className={`role-pill role-${user.role}`}>{user.role === 'admin' ? 'организатор' : 'участник'}</span>
              <button className="button button-quiet button-small" type="button" onClick={handleSignOut}>Выйти</button>
            </>
          ) : status === 'loading' ? (
            <span className="muted-nav" aria-live="polite">Проверяем вход…</span>
          ) : status === 'error' ? (
            <button className="button button-quiet button-small" type="button" onClick={() => void retry()}>Повторить вход</button>
          ) : (
            <>
              <Link className="nav-link login-link" to="/login">Войти</Link>
              <Link className="button button-small" to="/register">Создать аккаунт</Link>
            </>
          )}
        </div>
      </header>
      {signOutError && <div className="notice notice-error signout-notice" role="alert">{signOutError}</div>}
    </>
  )
}

function AuthStatusNotice() {
  const { status, error, retry } = useAuth()
  if (status !== 'error') return null
  return (
    <div className="notice notice-error auth-notice" role="alert">
      <span>{error ?? 'Не удалось проверить сессию.'} Публичные страницы доступны.</span>
      <button type="button" className="text-button" onClick={() => void retry()}>Повторить</button>
    </div>
  )
}

function HomePage() {
  const { status, user } = useAuth()
  return (
    <>
      <section className="hero-section">
        <div className="hero-copy">
          <p className="eyebrow"><span className="live-dot" /> Соревнования по спортивному программированию</p>
          <h1>Думай быстро.<br /><span>Играй на победу.</span></h1>
          <p className="hero-lede">Блиц-матчи один на один, задачи на время и живая борьба до последней секунды.</p>
          <div className="hero-actions">
            {status === 'authenticated' ? <Link className="button" to="/dashboard">Открыть кабинет <span aria-hidden="true">↗</span></Link> : <Link className="button" to="/register">Стать участником <span aria-hidden="true">↗</span></Link>}
            <Link className="button button-outline" to="/watch">Смотреть турниры</Link>
          </div>
          {user && <p className="welcome-line">С возвращением, {user.displayName}.</p>}
        </div>
        <div className="hero-board" aria-label="Иллюстрация маршрута матча, не трансляция">
          <div className="board-topline"><span>ПРИНЦИП КАРТЫ</span><span>2 ДОРОЖКИ</span></div>
          <div className="board-players"><span><i className="player-key player-key-green">1</i>Участник 1</span><span><i className="player-key player-key-orange">2</i>Участник 2</span></div>
          <div className="track-labels"><span>СТАРТ</span><span>A</span><span>B</span><span>C</span><span>D</span><span>ФИНИШ</span></div>
          <div className="track track-top"><span className="track-line" /><span className="runner runner-green" style={{ left: '61%' }} aria-hidden="true" /><span className="checkpoint checkpoint-a" /><span className="checkpoint checkpoint-b" /><span className="checkpoint checkpoint-c" /><span className="checkpoint checkpoint-d" /></div>
          <div className="track track-bottom"><span className="track-line" /><span className="runner runner-orange" style={{ left: '43%' }} aria-hidden="true" /><span className="checkpoint checkpoint-a" /><span className="checkpoint checkpoint-b" /><span className="checkpoint checkpoint-c" /><span className="checkpoint checkpoint-d" /></div>
          <div className="board-legend"><span className="checkpoint-swatch" />Задачи становятся контрольными точками</div>
          <p className="board-caption">Схематичная иллюстрация механики матча</p>
        </div>
        <span className="hero-index" aria-hidden="true">01 / 04</span>
      </section>
      <section className="intro-strip">
        <p>Соревнования,<br />которые видно.</p>
        <div><span className="strip-number">01</span><b>Один на один</b><small>Одинаковые задачи, разные решения</small></div>
        <div><span className="strip-number">02</span><b>Код в матче</b><small>Пиши, отправляй, получай вердикт</small></div>
        <div><span className="strip-number">03</span><b>Борьба на экране</b><small>Зритель видит счёт и прогресс</small></div>
      </section>
    </>
  )
}

function PublicViewerPage() {
  return (
    <section className="page-section public-page">
      <div className="page-heading">
        <p className="eyebrow"><span className="live-dot" /> Открытый просмотр</p>
        <h1>Публичные турниры</h1>
        <p>Зрительский просмотр доступен без аккаунта. Код участников здесь не показывается.</p>
      </div>
      <div className="empty-state">
        <div className="empty-orbit" aria-hidden="true"><span>Б</span></div>
        <h2>Открытых турниров пока нет</h2>
        <p>Открытые трансляции появятся здесь после подключения списка публичных турниров.</p>
        <Link className="text-link" to="/">На главную <span aria-hidden="true">↗</span></Link>
      </div>
    </section>
  )
}

function DashboardPage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <section className="page-section dashboard-page">
      <p className="eyebrow">Личный кабинет</p>
      <h1>Привет, {user.displayName}</h1>
      <p className="page-lede">{user.role === 'admin' ? 'Управляйте турнирами и следите за ходом соревнований.' : 'Здесь будут ваши приглашения и предстоящие матчи.'}</p>
      <div className="dashboard-card">
        <span className="card-kicker">ВАША РОЛЬ</span>
        <strong>{user.role === 'admin' ? 'Организатор' : 'Участник'}</strong>
        <p>{user.role === 'admin' ? 'У вас есть доступ к инструментам управления турниром.' : 'Войдите по ссылке-приглашению, чтобы присоединиться к турниру.'}</p>
        {user.role === 'admin' ? <Link className="text-link" to="/admin">К управлению турнирами <span aria-hidden="true">↗</span></Link> : <span className="muted-copy">Список матчей появится после подключения к турниру.</span>}
      </div>
    </section>
  )
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { status, error, retry } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingState label="Проверяем сессию…" />
  if (status === 'error') return <ErrorState message={error ?? 'Не удалось проверить сессию.'} onRetry={() => void retry()} />
  if (status === 'anonymous') return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return children
}

function RequireRole({ role, children }: { role: UserRole; children: ReactNode }) {
  const { status, user, retry } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingState label="Проверяем права доступа…" />
  if (status === 'error') return <ErrorState message="Не удалось проверить права доступа." onRetry={() => void retry()} />
  if (status === 'anonymous') {
    const next = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  if (user?.role !== role) return <Navigate to="/dashboard" replace />
  return children
}

function LoadingState({ label }: { label: string }) {
  return <div className="state-card" role="status"><span className="spinner" aria-hidden="true" />{label}</div>
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="state-card state-card-error" role="alert"><span>{message}</span><button className="text-button" onClick={onRetry} type="button">Повторить</button></div>
}

function NotFoundPage() {
  return <section className="page-section not-found"><p className="eyebrow">404 · Нет такой страницы</p><h1>Похоже, вы свернули не туда.</h1><Link className="button" to="/">Вернуться на главную</Link></section>
}

function Footer() {
  return <footer className="site-footer"><Link className="footer-brand" to="/">BLITZ_<span className="brand-accent">ARENA</span></Link><span>Первенство по спортивному программированию</span><span>Чувашия · 2026</span></footer>
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.'
}

export default App
