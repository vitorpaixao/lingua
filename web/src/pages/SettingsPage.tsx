import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Flex,
  Form,
  Input,
  Layout,
  Select,
  Space,
  Spin,
  Typography,
  App as AntdApp,
  theme,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ThemeToggle } from '@/components/ThemeToggle';
import { getSettings, updateSettings } from '@/api/client';
import type { ModelProvider, SettingsRead, SettingsUpdate } from '@/types/api';

const { Header, Content } = Layout;
const { Title, Text } = Typography;

const PROVIDER_DEFAULTS: Record<ModelProvider, { base_url: string; model: string }> = {
  openrouter: { base_url: 'https://openrouter.ai/api/v1', model: 'anthropic/claude-sonnet-4.5' },
  local: { base_url: 'http://host.docker.internal:11434/v1', model: 'qwen2.5-coder' },
  custom: { base_url: '', model: '' },
};

type FormValues = {
  github_token: string;
  model_provider: ModelProvider;
  model_base_url: string;
  model_api_key: string;
  model_id: string;
};

export function SettingsPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const firstRun = params.get('firstRun') === '1';
  const { message } = AntdApp.useApp();
  const { token } = theme.useToken();
  const [form] = Form.useForm<FormValues>();
  const [settings, setSettings] = useState<SettingsRead | null>(null);
  const [saving, setSaving] = useState(false);
  const provider = Form.useWatch('model_provider', form);

  useEffect(() => {
    void (async () => {
      const s = await getSettings();
      setSettings(s);
      form.setFieldsValue({
        model_provider: s.model_provider ?? 'openrouter',
        model_base_url: s.model_base_url ?? PROVIDER_DEFAULTS.openrouter.base_url,
        model_id: s.model_id ?? '',
        github_token: '',
        model_api_key: '',
      });
    })();
  }, [form]);

  const onProviderChange = useCallback(
    (value: ModelProvider) => {
      const cur = form.getFieldValue('model_base_url');
      // Only overwrite the base URL when empty or still a known provider default.
      const isDefault = Object.values(PROVIDER_DEFAULTS).some((d) => d.base_url === cur);
      if (!cur || isDefault) {
        form.setFieldValue('model_base_url', PROVIDER_DEFAULTS[value].base_url);
      }
    },
    [form],
  );

  const onSave = useCallback(async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const patch: SettingsUpdate = {
        model_provider: values.model_provider,
        model_base_url: values.model_base_url,
        model_id: values.model_id,
      };
      // Secrets: only send when the user typed something (blank = leave unchanged).
      if (values.github_token) patch.github_token = values.github_token;
      if (values.model_api_key) patch.model_api_key = values.model_api_key;

      const next = await updateSettings(patch);
      setSettings(next);
      form.setFieldsValue({ github_token: '', model_api_key: '' });
      message.success('Settings saved');
      if (firstRun && next.is_configured) nav('/');
    } catch (err) {
      if (err instanceof Error) message.error(`Failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [form, message, firstRun, nav]);

  if (!settings) {
    return (
      <Flex justify="center" align="center" style={{ minHeight: '100vh' }}>
        <Spin size="large" />
      </Flex>
    );
  }

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
        <Space>
          {!firstRun && (
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => nav('/')} />
          )}
          <Title level={3} style={{ margin: 0 }}>Settings</Title>
        </Space>
        <ThemeToggle />
      </Header>
      <Content style={{ padding: 24, maxWidth: 720, width: '100%', margin: '0 auto' }}>
        {firstRun && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Connect a model to get started"
            description="Lingua needs a model connection before you can create a project. Optionally add a GitHub token to create repositories and publish."
          />
        )}
        <Form form={form} layout="vertical" onFinish={onSave}>
          <Card title="Model connection" style={{ marginBottom: 16 }}>
            <Form.Item
              name="model_provider"
              label="Provider"
              rules={[{ required: true }]}
            >
              <Select
                onChange={onProviderChange}
                options={[
                  { value: 'openrouter', label: 'OpenRouter' },
                  { value: 'local', label: 'Local (OpenAI-compatible)' },
                  { value: 'custom', label: 'Custom OpenAI-compatible' },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="model_base_url"
              label="Base URL"
              rules={[
                { required: true, message: 'Required' },
                { type: 'url', message: 'Must be a valid URL' },
              ]}
            >
              <Input placeholder="https://openrouter.ai/api/v1" />
            </Form.Item>
            <Form.Item
              name="model_id"
              label="Model"
              rules={[{ required: true, message: 'Required' }]}
            >
              <Input placeholder={PROVIDER_DEFAULTS[provider ?? 'openrouter'].model} />
            </Form.Item>
            <Form.Item
              name="model_api_key"
              label="API key"
              extra={
                provider === 'local'
                  ? 'Often not required for local models.'
                  : settings.has_model_api_key
                    ? 'A key is saved. Leave blank to keep it.'
                    : undefined
              }
            >
              <Input.Password
                autoComplete="off"
                placeholder={settings.has_model_api_key ? '•••••••• (saved)' : 'sk-...'}
              />
            </Form.Item>
          </Card>

          <Card title="GitHub" style={{ marginBottom: 16 }}>
            <Form.Item
              name="github_token"
              label="Personal Access Token"
              extra={
                settings.has_github_token
                  ? 'A token is saved. Leave blank to keep it. Needs repo create + contents.'
                  : 'Used to create repositories and publish. Needs repo create + contents.'
              }
            >
              <Input.Password
                autoComplete="off"
                placeholder={settings.has_github_token ? '•••••••• (saved)' : 'ghp_...'}
              />
            </Form.Item>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Stored encrypted. OAuth sign-in is planned for a future release.
            </Text>
          </Card>

          <Flex justify="flex-end">
            <Button type="primary" htmlType="submit" loading={saving}>
              Save
            </Button>
          </Flex>
        </Form>
      </Content>
    </Layout>
  );
}
