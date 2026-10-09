import { useEffect, useRef } from 'react'
import { languageExtension } from './languageModes'
import { EditorState } from '@codemirror/state'
import { indentWithTab } from '@codemirror/commands'
import { EditorView, keymap } from '@codemirror/view'
import { basicSetup } from 'codemirror'
import './workspace.css'

interface CodeEditorProps {
  value: string
  languageId: string
  disabled?: boolean
  ariaLabel: string
  onChange(value: string): void
  onSubmitHotkey?(): void
}

export function CodeEditor({ value, languageId, disabled = false, ariaLabel, onChange, onSubmitHotkey }: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const onSubmitRef = useRef(onSubmitHotkey)

  useEffect(() => {
    valueRef.current = value
    onChangeRef.current = onChange
    onSubmitRef.current = onSubmitHotkey
  }, [value, onChange, onSubmitHotkey])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const mode = languageExtension(languageId)
    const state = EditorState.create({
      doc: valueRef.current,
      extensions: [
        basicSetup,
        ...(mode ? [mode] : []),
        keymap.of([
          indentWithTab,
          {
            key: 'Mod-Enter',
            run: () => {
              onSubmitRef.current?.()
              return Boolean(onSubmitRef.current)
            },
          },
        ]),
        EditorState.readOnly.of(disabled),
        EditorView.editable.of(!disabled),
        EditorView.contentAttributes.of({ 'aria-label': ariaLabel, spellcheck: 'false' }),
        EditorView.lineWrapping,
        EditorView.theme({
          '&': { height: '100%', color: 'var(--paper)', backgroundColor: '#101714', fontSize: '13px' },
          '.cm-content': { minHeight: '300px', padding: '16px 0', fontFamily: 'var(--mono)' },
          '.cm-gutters': { color: '#6f8073', backgroundColor: '#141d18', border: 'none' },
          '&.cm-focused': { outline: 'none' },
          '.cm-activeLine': { backgroundColor: 'rgba(221, 239, 224, .035)' },
          '.cm-activeLineGutter': { backgroundColor: 'rgba(221, 239, 224, .035)' },
        }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current(update.state.doc.toString())
        }),
      ],
    })
    const view = new EditorView({ state, parent: host })
    viewRef.current = view
    return () => {
      view.destroy()
      if (viewRef.current === view) viewRef.current = null
    }
  }, [ariaLabel, disabled, languageId])

  useEffect(() => {
    const view = viewRef.current
    if (!view || view.state.doc.toString() === value) return
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
  }, [value])

  return <div className="code-editor" ref={hostRef} />
}
