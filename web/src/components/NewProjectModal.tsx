import { useState } from 'react'
import { Form, Input, Modal } from 'antd'
import { api } from '../api/client'

interface NewProjectModalProps {
  open: boolean
  onClose: () => void
  onCreated: (id: string) => void
}

export function NewProjectModal({ open, onClose, onCreated }: NewProjectModalProps) {
  const [name, setName] = useState('')
  const [bootstrapUrl, setBootstrapUrl] = useState('')
  const [targetUrl, setTargetUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setName('')
    setBootstrapUrl('')
    setTargetUrl('')
    setError(null)
  }

  const submit = async () => {
    if (!name.trim() || !bootstrapUrl.trim()) return
    setLoading(true)
    setError(null)
    try {
      const p = await api.createProject({
        name: name.trim(),
        bootstrap_url: bootstrapUrl.trim(),
        target_url: targetUrl.trim() || undefined,
      })
      reset()
      onCreated(p.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="New project"
      open={open}
      onOk={submit}
      onCancel={() => { reset(); onClose() }}
      okText="Create"
      confirmLoading={loading}
      okButtonProps={{ disabled: !name.trim() || !bootstrapUrl.trim() }}
    >
      <Form layout="vertical" style={{ marginTop: 12 }}>
        <Form.Item label="Name" required>
          <Input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="My app"
          />
        </Form.Item>
        <Form.Item label="Bootstrap repo URL" required>
          <Input
            value={bootstrapUrl}
            onChange={e => setBootstrapUrl(e.target.value)}
            placeholder="https://github.com/org/lingua--bootstrap"
          />
        </Form.Item>
        <Form.Item label="Target repo URL (optional)">
          <Input
            value={targetUrl}
            onChange={e => setTargetUrl(e.target.value)}
            placeholder="https://github.com/org/my-app"
          />
        </Form.Item>
        {error && <div style={{ color: '#ff4d4f', fontSize: 13 }}>{error}</div>}
      </Form>
    </Modal>
  )
}
