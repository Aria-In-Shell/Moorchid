/**
 * useEntries — React hook for journal entry CRUD.
 * Fetches from FastAPI /api/entries and provides create/delete actions.
 */

import { useCallback, useEffect, useState } from 'react'
import { createEntry, deleteEntry, loadJournalWindow } from '../api/client'
import type { Entry } from '../types'

export function useEntries(start: string, end: string) {
  const [hasEarlier, setHasEarlier] = useState(false)
  const [entries, setEntries] = useState<Entry[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [justSaved, setJustSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setEntries([])
    setError(null)
    loadJournalWindow(start, end, controller.signal).then(result => {
      if (controller.signal.aborted) return
      setEntries(result.entries)
      setHasEarlier(result.hasEarlier)
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : '读取记录失败')
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [start, end])

  // Create — POST to FastAPI, prepend to list on success
  const submit = useCallback(async (content: string, mood?: string) => {
    if (!content.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const created = await createEntry({ content, mood })
      setEntries(prev => [created, ...prev])
      setJustSaved(true)
      setTimeout(() => setJustSaved(false), 2000)
      return created
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save entry')
    } finally {
      setSubmitting(false)
    }
  }, [])

  // Delete — DELETE from FastAPI, remove from list on success
  const remove = useCallback(async (entryId: number) => {
    try {
      await deleteEntry(entryId)
      setEntries(prev => prev.filter(e => e.id !== entryId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete entry')
    }
  }, [])

  return {
    entries,
    loading,
    submitting,
    justSaved,
    error,
    submit,
    remove,
    hasEarlier,
  }
}
