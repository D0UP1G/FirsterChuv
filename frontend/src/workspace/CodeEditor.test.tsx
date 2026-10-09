import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CodeEditor } from './CodeEditor'

afterEach(() => cleanup())

describe('CodeEditor', () => {
  it('exposes an accessible editor and reports typed source', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<CodeEditor value="" languageId="cpp20" ariaLabel="Исходный код" onChange={onChange} />)

    const editor = screen.getByRole('textbox', { name: 'Исходный код' })
    await user.type(editor, 'int main()')

    expect(onChange).toHaveBeenLastCalledWith('int main()')
  })

  it('invokes the submit callback on Ctrl+Enter', async () => {
    const onSubmitHotkey = vi.fn()
    render(<CodeEditor value="int main() {}" languageId="cpp20" ariaLabel="Исходный код" onChange={vi.fn()} onSubmitHotkey={onSubmitHotkey} />)

    const editor = screen.getByRole('textbox', { name: 'Исходный код' })
    editor.focus()
    expect(editor).toHaveFocus()
    fireEvent.keyDown(editor, { key: 'Enter', code: 'Enter', ctrlKey: true })

    expect(onSubmitHotkey).toHaveBeenCalledOnce()
  })

  it('keeps the editor read-only and ignores submit hotkeys when disabled', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const onSubmitHotkey = vi.fn()
    render(<CodeEditor value="locked" languageId="cpp20" disabled ariaLabel="Исходный код" onChange={onChange} onSubmitHotkey={onSubmitHotkey} />)

    const editor = screen.getByRole('textbox', { name: 'Исходный код' })
    expect(editor).toHaveAttribute('contenteditable', 'false')
    await user.click(editor)
    fireEvent.keyDown(editor, { key: 'Enter', code: 'Enter', ctrlKey: true })

    expect(onChange).not.toHaveBeenCalled()
    expect(onSubmitHotkey).not.toHaveBeenCalled()
  })
})
