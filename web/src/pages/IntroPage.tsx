import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Col, Empty, Row, Spin } from 'antd'
import { ProCard } from '@ant-design/pro-components'
import { api, type Project } from '../api/client'
import { NewProjectModal } from '../components/NewProjectModal'

export function IntroPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    api.listProjects()
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const openProject = async (id: string) => {
    await api.touchProject(id).catch(() => {})
    navigate(`/workspace?id=${id}`)
  }

  const onCreated = (id: string) => {
    navigate(`/workspace?id=${id}`)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 80 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      {projects.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 24 }}>
          <Button type="primary" onClick={() => setShowModal(true)}>+ New project</Button>
        </div>
      )}

      {projects.length === 0 ? (
        <Empty description="No projects yet" style={{ marginTop: 80 }}>
          <Button type="primary" onClick={() => setShowModal(true)}>+ New project</Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map(p => (
            <Col key={p.id} xs={24} sm={12} md={8}>
              <ProjectCard project={p} onClick={() => openProject(p.id)} />
            </Col>
          ))}
        </Row>
      )}

      <NewProjectModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreated={onCreated}
      />
    </div>
  )
}

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
  const opened = project.last_opened_at
    ? new Date(project.last_opened_at).toLocaleDateString()
    : null

  return (
    <ProCard hoverable onClick={onClick} style={{ cursor: 'pointer' }}>
      <div style={{ fontWeight: 600, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {project.name}
      </div>
      {project.target_url && (
        <div style={{ fontSize: 12, opacity: 0.65, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 2 }}>
          {project.target_url}
        </div>
      )}
      <div style={{ fontSize: 12, opacity: 0.45, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {project.bootstrap_url}
      </div>
      {opened && (
        <div style={{ fontSize: 12, opacity: 0.35, marginTop: 8 }}>Last opened {opened}</div>
      )}
    </ProCard>
  )
}
