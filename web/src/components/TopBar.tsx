import { useEffect, useState, useCallback } from 'react';
import { Button, Flex, Space, Tag, Tooltip, App as AntdApp, theme } from 'antd';
import {
  BranchesOutlined,
  CloudUploadOutlined,
  AimOutlined,
  CloseCircleFilled,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { gitStatus, gitPublish } from '@/api/client';
import type { GitStatus, SelectionPayload } from '@/types/api';
import { ThemeToggle } from '@/components/ThemeToggle';

const POLL_MS = 5000;

export function TopBar({
  projectName,
  pickMode,
  onTogglePick,
  selection,
  onClearSelection,
}: {
  projectName: string;
  pickMode: boolean;
  onTogglePick: () => void;
  selection: SelectionPayload | null;
  onClearSelection: () => void;
}) {
  const nav = useNavigate();
  const { message } = AntdApp.useApp();
  const { token } = theme.useToken();
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [publishing, setPublishing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await gitStatus();
        if (!cancelled) setStatus(s);
      } catch {
        // ignore
      }
    };
    void tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const onPublish = useCallback(async () => {
    setPublishing(true);
    try {
      const res = await gitPublish();
      if (res.ok) {
        message.success(`Published → ${res.branch}`);
      } else {
        message.error(`Failed at ${res.step}: ${res.error}`);
      }
    } finally {
      setPublishing(false);
    }
  }, [message]);

  return (
    <Flex
      justify="space-between"
      align="center"
      style={{
        height: 48,
        padding: '0 16px',
        background: token.colorBgContainer,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        flexShrink: 0,
      }}
    >
      <Space>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => nav('/')}>
          Projects
        </Button>
        <strong>{projectName}</strong>
        <BranchBadge status={status} />
      </Space>

      <Space>
        {selection && (
          <Tag
            closable
            closeIcon={<CloseCircleFilled />}
            color="blue"
            onClose={(e) => {
              e.preventDefault();
              onClearSelection();
            }}
          >
            Selected: {selection.summary}
          </Tag>
        )}
        <Tooltip title={pickMode ? 'Disable picker (ESC)' : 'Click an element in the preview'}>
          <Button
            type={pickMode ? 'primary' : 'default'}
            icon={<AimOutlined />}
            onClick={onTogglePick}
          >
            Select
          </Button>
        </Tooltip>
        <ThemeToggle />
        <Button
          type="primary"
          icon={<CloudUploadOutlined />}
          loading={publishing}
          onClick={onPublish}
        >
          Publish
        </Button>
      </Space>
    </Flex>
  );
}

function BranchBadge({ status }: { status: GitStatus | null }) {
  if (!status) return <Tag>loading…</Tag>;
  if (!status.ok) return <Tag color="red">no git</Tag>;

  const extras: string[] = [];
  if (status.no_upstream) extras.push('no upstream');
  else if (status.ahead && Number(status.ahead) > 0)
    extras.push(`${status.ahead} ahead`);
  if (status.dirty_files > 0) extras.push(`${status.dirty_files} unsaved`);

  return (
    <Tag
      icon={<BranchesOutlined />}
      color={status.dirty_files > 0 ? 'orange' : 'default'}
    >
      {status.branch}
      {extras.length > 0 && ` · ${extras.join(' · ')}`}
    </Tag>
  );
}
