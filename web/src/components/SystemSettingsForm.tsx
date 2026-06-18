import { useCallback, useEffect, useState } from 'react';
import {
  AutoComplete,
  Button,
  Card,
  Flex,
  Form,
  Input,
  Select,
  Space,
  Spin,
  Tooltip,
  Typography,
  App as AntdApp,
} from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { getSettings, listModels, updateSettings } from '@/api/client';
import type { ModelInfo, ModelProvider, SettingsRead, SettingsUpdate } from '@/types/api';

const { Text } = Typography;

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

/** System Configuration: instance-wide Credential Vault — Model Connection + GitHub PAT.
 *  Chrome-less; rendered inside the IntroPage drawer. Calls `onSaved` after a successful
 *  save so the host can close/unblock (e.g. enable "New project" on first run). */
export function SystemSettingsForm({ onSaved }: { onSaved?: (s: SettingsRead) => void }) {
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm<FormValues>();
  const [settings, setSettings] = useState<SettingsRead | null>(null);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const provider = Form.useWatch('model_provider', form);

  const fetchModels = useCallback(async () => {
    const p: ModelProvider = form.getFieldValue('model_provider') ?? 'openrouter';
    const base = form.getFieldValue('model_base_url') as string | undefined;
    if (p !== 'openrouter' && !base) {
      // Local/Custom need a base URL before we can list anything.
      setModels([]);
      setModelsError(null);
      return;
    }
    setModelsLoading(true);
    setModelsError(null);
    try {
      const res = await listModels({
        provider: p,
        base_url: base,
        api_key: form.getFieldValue('model_api_key') || undefined,
      });
      setModels(res.models);
      setModelsError(res.error ?? null);
    } catch (err) {
      setModels([]);
      setModelsError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setModelsLoading(false);
    }
  }, [form]);

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
      void fetchModels();
    })();
  }, [form, fetchModels]);

  const onProviderChange = useCallback(
    (value: ModelProvider) => {
      const cur = form.getFieldValue('model_base_url');
      const isDefault = Object.values(PROVIDER_DEFAULTS).some((d) => d.base_url === cur);
      if (!cur || isDefault) {
        form.setFieldValue('model_base_url', PROVIDER_DEFAULTS[value].base_url);
      }
      void fetchModels();
    },
    [form, fetchModels],
  );

  const onSave = useCallback(async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const patch: SettingsUpdate = {
        model_provider: values.model_provider,
        // OpenRouter's URL field is hidden; always send its fixed default.
        model_base_url:
          values.model_provider === 'openrouter'
            ? PROVIDER_DEFAULTS.openrouter.base_url
            : values.model_base_url,
        model_id: values.model_id,
      };
      if (values.github_token) patch.github_token = values.github_token;
      if (values.model_api_key) patch.model_api_key = values.model_api_key;

      const next = await updateSettings(patch);
      setSettings(next);
      form.setFieldsValue({ github_token: '', model_api_key: '' });
      message.success('Settings saved');
      onSaved?.(next);
    } catch (err) {
      if (err instanceof Error) message.error(`Failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [form, message, onSaved]);

  if (!settings) {
    return (
      <Flex justify="center" align="center" style={{ padding: 48 }}>
        <Spin size="large" />
      </Flex>
    );
  }

  return (
    <Form form={form} layout="vertical" onFinish={onSave}>
      <Card title="Model connection" style={{ marginBottom: 16 }}>
        <Form.Item name="model_provider" label="Provider" rules={[{ required: true }]}>
          <Select
            onChange={onProviderChange}
            options={[
              { value: 'openrouter', label: 'OpenRouter' },
              { value: 'local', label: 'Local (OpenAI-compatible)' },
              { value: 'custom', label: 'Custom OpenAI-compatible' },
            ]}
          />
        </Form.Item>
        {provider !== 'openrouter' && (
          <Form.Item
            name="model_base_url"
            label="Base URL"
            rules={[
              { required: true, message: 'Required' },
              { type: 'url', message: 'Must be a valid URL' },
            ]}
          >
            <Input placeholder="http://host.docker.internal:11434/v1" onBlur={() => void fetchModels()} />
          </Form.Item>
        )}
        <Form.Item
          name="model_id"
          rules={[{ required: true, message: 'Required' }]}
          extra={modelsError ?? undefined}
          validateStatus={modelsError ? 'warning' : undefined}
          label={
            <Space>
              Model
              <Tooltip title="Reload models">
                <Button
                  size="small"
                  type="text"
                  icon={<ReloadOutlined />}
                  loading={modelsLoading}
                  onClick={() => void fetchModels()}
                />
              </Tooltip>
            </Space>
          }
        >
          <AutoComplete
            options={models.map((m) => ({
              value: m.id,
              label: m.name && m.name !== m.id ? `${m.name} — ${m.id}` : m.id,
            }))}
            filterOption={(input, option) =>
              String(option?.value ?? '').toLowerCase().includes(input.toLowerCase())
            }
            placeholder={PROVIDER_DEFAULTS[provider ?? 'openrouter'].model}
            allowClear
          />
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
  );
}
