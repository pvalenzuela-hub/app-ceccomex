"use client"

import { useEffect, useRef, useState } from 'react'

export type Option = { value: string; label: string; hint?: string }

type Props = {
  label: string
  placeholder: string
  selected: string[]
  onChange: (values: string[]) => void
  /** Static options are filtered in the browser by value or label. */
  options?: Option[]
  /** Remote options for large lists (e.g. 25k importers); called once 2+ characters are typed. */
  search?: (text: string) => Promise<Option[]>
  /** Labels for selected values that are not in the current option list. */
  selectedLabels?: Record<string, string>
}

const MAX_VISIBLE = 60

export default function SearchableMultiSelect({ label, placeholder, selected, onChange, options, search, selectedLabels = {} }: Props) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [remote, setRemote] = useState<Option[]>([])
  const [known, setKnown] = useState<Record<string, string>>({})
  const request = useRef(0)

  useEffect(() => {
    if (!search) return
    if (text.trim().length < 2) { setRemote([]); return }
    const current = ++request.current
    const timer = window.setTimeout(async () => {
      const results = await search(text.trim())
      if (current === request.current) setRemote(results)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [search, text])

  const needle = text.trim().toLowerCase()
  const matches = search
    ? remote
    : (options ?? []).filter((option) => !needle || option.value.toLowerCase().startsWith(needle) || option.label.toLowerCase().includes(needle)).slice(0, MAX_VISIBLE)
  const labelOf = (value: string) => selectedLabels[value] ?? known[value] ?? options?.find((option) => option.value === value)?.label ?? value

  function toggle(option: Option) {
    setKnown({ ...known, [option.value]: option.label })
    onChange(selected.includes(option.value) ? selected.filter((value) => value !== option.value) : [...selected, option.value])
  }

  return (
    <div className="searchable-select">
      <label className="tariff-search">
        <span>{label}{selected.length ? ` (${selected.length})` : ''}</span>
        <input value={text} onChange={(event) => { setText(event.target.value); setOpen(true) }} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} placeholder={placeholder} />
        {open && matches.length ? (
          <div className="tariff-options tariff-options-multi">
            {matches.map((option) => (
              <button key={option.value} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => toggle(option)}>
                <input type="checkbox" checked={selected.includes(option.value)} readOnly />
                <strong>{option.hint ?? option.value}</strong><span>{option.label}</span>
              </button>
            ))}
          </div>
        ) : null}
        {open && search && needle.length >= 2 && !remote.length ? <small>Sin coincidencias.</small> : null}
      </label>
      {selected.length ? <div className="selected-values">{selected.map((value) => <button key={value} type="button" onClick={() => onChange(selected.filter((item) => item !== value))}>{labelOf(value)} ×</button>)}</div> : null}
    </div>
  )
}
