import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ParticipantWorkspacePage } from './ParticipantWorkspacePage'

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: { id: '00000000-0000-0000-0000-000000000001', displayName: 'Участник', role: 'participant' } }),
}))

function renderWorkspace(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes><Route path="/matches/:matchId" element={<ParticipantWorkspacePage />} /></Routes>
    </MemoryRouter>,
  )
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('ParticipantWorkspacePage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('keeps task conditions and editor closed until the match starts', async () => {
    renderWorkspace('/matches/match-1?scenario=workspace-ui&status=READY')

    expect(await screen.findByRole('heading', { name: 'Задачи откроются после старта матча' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Задачи матча' })).not.toBeInTheDocument()
    expect(screen.queryByText('Найдите значение a + b.')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('renders the isolated workspace fixture without enabling fake submissions or verdicts', async () => {
    renderWorkspace('/matches/match-1?scenario=workspace-ui')

    expect(await screen.findByText(/Изолированный dev-сценарий/)).toBeInTheDocument()
    expect(await screen.findByRole('table', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Отправить решение' })).toBeDisabled()
    expect(screen.getByText(/синтетические попытки не создаются/)).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('keeps a language response and template when no local syntax mode exists', async () => {
    renderWorkspace('/matches/match-1?scenario=workspace-ui&compiler=rust-fixture')

    const languagePicker = await screen.findByRole('combobox', { name: 'Язык программирования' })
    expect(languagePicker).toHaveValue('rust2024')
    expect(languagePicker).toHaveTextContent('Rust 2024')

    const editor = await screen.findByRole('textbox', { name: 'Исходный код, задача A, Rust 2024' })
    await waitFor(() => expect(editor).toHaveTextContent('println!("Hello, world!");'))
    expect(editor).toHaveAttribute('contenteditable', 'true')
    expect(screen.getByText(/нет локального режима подсветки/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отправить решение' })).toBeDisabled()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('restores task-scoped local drafts across task switches and page remount when draft API is unavailable', async () => {
    const user = userEvent.setup({ delay: 1 })
    const entry = '/matches/match-1?scenario=workspace-ui&draft=offline-fixture'
    const firstPage = renderWorkspace(entry)

    const editorA = await screen.findByRole('textbox', { name: 'Исходный код, задача A, C++20' })
    editorA.focus()
    for (const character of 'draftA') await user.keyboard(character)
    await waitFor(() => expect(editorA).toHaveTextContent('draftA'))

    await user.click(screen.getByRole('button', { name: /Задача B/ }))
    const editorB = await screen.findByRole('textbox', { name: 'Исходный код, задача B, C++20' })
    editorB.focus()
    for (const character of 'draftB') await user.keyboard(character)
    await waitFor(() => expect(editorB).toHaveTextContent('draftB'))

    await user.click(screen.getByRole('button', { name: /Задача A/ }))
    const restoredA = await screen.findByRole('textbox', { name: 'Исходный код, задача A, C++20' })
    await waitFor(() => expect(restoredA).toHaveTextContent('draftA'))

    firstPage.unmount()
    renderWorkspace(entry)

    const remountedA = await screen.findByRole('textbox', { name: 'Исходный код, задача A, C++20' })
    await waitFor(() => expect(remountedA).toHaveTextContent('draftA'))
    await user.click(screen.getByRole('button', { name: /Задача B/ }))
    const remountedB = await screen.findByRole('textbox', { name: 'Исходный код, задача B, C++20' })
    await waitFor(() => expect(remountedB).toHaveTextContent('draftB'))

    expect(screen.getByText(/Серверное хранилище недоступно/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отправить решение' })).toBeDisabled()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('restores separate language-scoped drafts after switching languages and remounting the page', async () => {
    const user = userEvent.setup({ delay: 1 })
    const entry = '/matches/match-1?scenario=workspace-ui&draft=offline-fixture'
    const firstPage = renderWorkspace(entry)

    const cppEditor = await screen.findByRole('textbox', { name: 'Исходный код, задача A, C++20' })
    cppEditor.focus()
    for (const character of 'cppDraft') await user.keyboard(character)
    await waitFor(() => expect(cppEditor).toHaveTextContent('cppDraft'))

    const languagePicker = screen.getByRole('combobox', { name: 'Язык программирования' })
    await user.selectOptions(languagePicker, 'python3')
    const pythonEditor = await screen.findByRole('textbox', { name: 'Исходный код, задача A, Python 3' })
    pythonEditor.focus()
    for (const character of 'pythonDraft') await user.keyboard(character)
    await waitFor(() => expect(pythonEditor).toHaveTextContent('pythonDraft'))

    await user.selectOptions(languagePicker, 'cpp20')
    const restoredCpp = await screen.findByRole('textbox', { name: 'Исходный код, задача A, C++20' })
    await waitFor(() => expect(restoredCpp).toHaveTextContent('cppDraft'))
    await user.selectOptions(languagePicker, 'python3')
    const restoredPython = await screen.findByRole('textbox', { name: 'Исходный код, задача A, Python 3' })
    await waitFor(() => expect(restoredPython).toHaveTextContent('pythonDraft'))

    firstPage.unmount()
    renderWorkspace(entry)

    const remountedCppPicker = await screen.findByRole('combobox', { name: 'Язык программирования' })
    const remountedCpp = await screen.findByRole('textbox', { name: 'Исходный код, задача A, C++20' })
    await waitFor(() => expect(remountedCpp).toHaveTextContent('cppDraft'))
    await user.selectOptions(remountedCppPicker, 'python3')
    const remountedPython = await screen.findByRole('textbox', { name: 'Исходный код, задача A, Python 3' })
    await waitFor(() => expect(remountedPython).toHaveTextContent('pythonDraft'))

    expect(screen.getByText(/Серверное хранилище недоступно/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отправить решение' })).toBeDisabled()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('does not fall back to fixtures when the production match API is unavailable', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ error: { code: 'not_found', message: 'Матч не найден.' } }, 404))
    renderWorkspace('/matches/match-1')

    expect(await screen.findByRole('alert')).toHaveTextContent('Матч не найден.')
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    expect(fetch).toHaveBeenCalledWith('/api/v1/matches/match-1', expect.objectContaining({ cache: 'no-store' }))
    expect(screen.queryByText(/Изолированный dev-сценарий/)).not.toBeInTheDocument()
  })
})
