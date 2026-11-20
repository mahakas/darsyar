import type { ReactNode } from 'react'

/** Minimal Markdown subset rendered as React nodes with no raw HTML injection. */
const INLINE_TOKEN = /(`[^`]+`|\*\*[^*]+\*\*)/g

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(INLINE_TOKEN).map((part, index) => {
    const key = `${keyPrefix}-${index}`
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return <code key={key}>{part.slice(1, -1)}</code>
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

export default function SafeMarkdown({ text }: { text: string }) {
  const lines = text.split('\n')
  const blocks: ReactNode[] = []
  let inCode = false
  let codeLines: string[] = []
  let listItems: string[] = []

  const flushList = () => {
    if (!listItems.length) return
    blocks.push(
      <ul key={`list-${blocks.length}`}>
        {listItems.map((item, index) => (
          <li key={index}>{renderInline(item, `li-${blocks.length}-${index}`)}</li>
        ))}
      </ul>,
    )
    listItems = []
  }
  const flushCode = () => {
    if (!codeLines.length) return
    blocks.push(<pre key={`code-${blocks.length}`}><code>{codeLines.join('\n')}</code></pre>)
    codeLines = []
  }

  lines.forEach((line, index) => {
    if (line.trim().startsWith('```')) {
      if (inCode) { flushCode(); inCode = false }
      else { flushList(); inCode = true }
      return
    }
    if (inCode) { codeLines.push(line); return }
    if (line.startsWith('- ')) { listItems.push(line.slice(2)); return }
    flushList()
    if (line.trim()) blocks.push(<p key={`p-${index}`}>{renderInline(line, `p-${index}`)}</p>)
  })
  flushList()
  flushCode()

  return <>{blocks}</>
}
