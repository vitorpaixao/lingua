import { useEffect, useState, useCallback } from 'react';
import {
  Alert,
  Button,
  Card,
  Drawer,
  Empty,
  Flex,
  Layout,
  Space,
  Spin,
  Tooltip,
  Typography,
  App as AntdApp,
  theme,
} from 'antd';
import {
  PlusOutlined,
  FolderOpenOutlined,
  DeleteOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { ThemeToggle } from '@/components/ThemeToggle';
import {
  listProjects,
  createProject,
  switchWorkspace,
  archiveProject,
  gitPublish,
  getSettings,
} from '@/api/client';
import type { Project, SwitchNeedsConfirm } from '@/types/api';
import { NewProjectModal, type NewProjectValues } from '@/components/NewProjectModal';
import { SystemSettingsForm } from '@/components/SystemSettingsForm';
import { DirtySwitchModal } from '@/components/DirtySwitchModal';

const { Header, Content } = Layout;
const { Title, Text } = Typography;

export function IntroPage() {
  const nav = useNavigate();
  const { message } = AntdApp.useApp();
  const { token } = theme.useToken();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [dirtyTarget, setDirtyTarget] = useState<{
    project: Project;
    dirtyFiles: number;
    currentName: string;
  } | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // null = unknown (still loading); drives the first-run gate.
  const [configured, setConfigured] = useState<boolean | null>(null);

  const load = useCallback(async () => {
    setProjects(await listProjects());
  }, []);

  const refreshConfigured = useCallback(async () => {
    try {
      const s = await getSettings();
      setConfigured(s.is_configured);
      return s.is_configured;
    } catch {
      setConfigured(true); // fail open — don't trap the user on API error
      return true;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // First-run gate: empty vault → open the System settings drawer and block New project.
  useEffect(() => {
    void (async () => {
      const ok = await refreshConfigured();
      if (!ok) setSettingsOpen(true);
    })();
  }, [refreshConfigured]);

  const open = useCallback(
    async (project: Project, force = false) => {
      const result = await switchWorkspace(project.id, force);
      if (!('ok' in result) || result.ok === false) {
        const needs = result as SwitchNeedsConfirm;
        if (needs.needs_confirm) {
          const current = projects?.find((p) => p.id === needs.current_project_id);
          setDirtyTarget({
            project,
            dirtyFiles: needs.dirty_files,
            currentName: current?.name ?? 'current project',
          });
          return;
        }
      }
      nav(`/workspace?id=${project.id}`);
    },
    [nav, projects],
  );

  const onCreate = useCallback(
    async (values: NewProjectValues) => {
      setSubmitting(true);
      try {
        const proj = await createProject(values);
        message.success(`Created "${proj.name}"`);
        setNewOpen(false);
        await load();
        await open(proj);
      } catch (err) {
        message.error(`Failed: ${(err as Error).message}`);
      } finally {
        setSubmitting(false);
      }
    },
    [load, open, message],
  );

  const onArchive = useCallback(
    async (p: Project) => {
      await archiveProject(p.id);
      message.success(`Archived "${p.name}"`);
      await load();
    },
    [load, message],
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
        }}
      >
        <Title level={3} style={{ margin: 0 }}>Lingua</Title>
        <Space>
          <ThemeToggle />
          <Button icon={<SettingOutlined />} onClick={() => setSettingsOpen(true)}>
            System settings
          </Button>
          <Tooltip title={configured === false ? 'Connect a model in System settings first' : ''}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              disabled={configured !== true}
              onClick={() => setNewOpen(true)}
            >
              New project
            </Button>
          </Tooltip>
        </Space>
      </Header>
      <Content style={{ padding: 24 }}>
        {configured === false && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Connect a model to get started"
            description="Open System settings and add a Model Connection before creating a project. A GitHub token is optional, for creating repos and publishing."
            action={
              <Button size="small" onClick={() => setSettingsOpen(true)}>
                System settings
              </Button>
            }
          />
        )}
        {projects === null ? (
          <Flex justify="center" align="center" style={{ padding: 48 }}>
            <Spin size="large" />
          </Flex>
        ) : projects.length === 0 ? (
          <Empty description="No projects yet. Create one to get started.">
            <Button type="primary" onClick={() => setNewOpen(true)}>New project</Button>
          </Empty>
        ) : (
          <Space wrap size={[16, 16]} style={{ alignItems: 'flex-start' }}>
            {projects.map((p) => (
              <Card
                key={p.id}
                style={{ width: 320 }}
                title={p.name}
                actions={[
                  <Button key="open" type="link" icon={<FolderOpenOutlined />} onClick={() => open(p)}>
                    Open
                  </Button>,
                  <Button key="archive" type="link" danger icon={<DeleteOutlined />} onClick={() => onArchive(p)}>
                    Archive
                  </Button>,
                ]}
              >
                <Flex vertical gap={4} style={{ width: '100%' }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>Bootstrap</Text>
                  <Text code ellipsis>{p.bootstrap_url}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>Target</Text>
                  <Text code ellipsis>{p.target_url ?? '(unset)'}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Last opened: {p.last_opened_at ? new Date(p.last_opened_at).toLocaleString() : 'never'}
                  </Text>
                </Flex>
              </Card>
            ))}
          </Space>
        )}
      </Content>

      <Drawer
        title="System settings"
        placement="right"
        width={480}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        // Don't let a first-run user dismiss until a model is connected.
        closable={configured !== false}
        maskClosable={configured !== false}
      >
        <SystemSettingsForm onSaved={(s) => setConfigured(s.is_configured)} />
      </Drawer>

      <NewProjectModal
        open={newOpen}
        onCancel={() => setNewOpen(false)}
        onSubmit={onCreate}
        submitting={submitting}
      />

      <DirtySwitchModal
        open={dirtyTarget !== null}
        dirtyFiles={dirtyTarget?.dirtyFiles ?? 0}
        currentName={dirtyTarget?.currentName ?? ''}
        onCancel={() => setDirtyTarget(null)}
        publishing={publishing}
        onPublishFirst={async () => {
          if (!dirtyTarget) return;
          setPublishing(true);
          try {
            const res = await gitPublish();
            if (res.ok) {
              message.success(`Published to ${res.branch}`);
              const tgt = dirtyTarget.project;
              setDirtyTarget(null);
              await open(tgt, true);
            } else {
              message.error(`Publish failed at ${res.step}: ${res.error}`);
            }
          } finally {
            setPublishing(false);
          }
        }}
        onSwitchAnyway={async () => {
          if (!dirtyTarget) return;
          const tgt = dirtyTarget.project;
          setDirtyTarget(null);
          await open(tgt, true);
        }}
      />
    </Layout>
  );
}
