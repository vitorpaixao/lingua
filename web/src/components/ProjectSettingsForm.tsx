import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Flex, Form, Input, Typography, App as AntdApp } from 'antd';
import { updateProject } from '@/api/client';
import type { Project } from '@/types/api';

const { Text } = Typography;

type FormValues = { name: string; target_url: string };

/** Project Configuration: per-project settings shown in the workspace gear view.
 *  Edits name + Target Repo (origin/publish dest); Bootstrap Repo is read-only.
 *  On save the backend also rewrites the checkout's `origin` remote. */
export function ProjectSettingsForm({
  project,
  onSaved,
}: {
  project: Project;
  onSaved?: (p: Project) => void;
}) {
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm<FormValues>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    form.setFieldsValue({ name: project.name, target_url: project.target_url ?? '' });
  }, [form, project]);

  const onSave = useCallback(async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const next = await updateProject(project.id, {
        name: values.name,
        target_url: values.target_url || null,
      });
      message.success('Project settings saved');
      onSaved?.(next);
    } catch (err) {
      if (err instanceof Error) message.error(`Failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [form, project.id, message, onSaved]);

  return (
    <Flex vertical style={{ height: '100%', overflow: 'auto', padding: 8 }}>
      <Form form={form} layout="vertical" onFinish={onSave}>
        <Card title="Project" style={{ marginBottom: 16 }}>
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Required' }]}>
            <Input placeholder="My App" />
          </Form.Item>
          <Form.Item
            name="target_url"
            label="Target repository (origin)"
            extra="Where Publish pushes commits."
            rules={[{ type: 'url', message: 'Must be a valid URL' }]}
          >
            <Input placeholder="https://github.com/me/my-app" />
          </Form.Item>
          <Form.Item label="Bootstrap repository">
            <Text code>{project.bootstrap_url}</Text>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Cloned once at creation — not editable.
              </Text>
            </div>
          </Form.Item>
        </Card>
        <Flex justify="flex-end">
          <Button type="primary" htmlType="submit" loading={saving}>
            Save
          </Button>
        </Flex>
      </Form>
    </Flex>
  );
}
