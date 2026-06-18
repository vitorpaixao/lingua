import { Checkbox, Form, Input, Modal, Radio } from 'antd';
import { useEffect } from 'react';

export type NewProjectValues = {
  name: string;
  bootstrap_url: string;
  target_url?: string;
  create_github_repo?: boolean;
  visibility?: 'private' | 'public';
  description?: string;
};

export function NewProjectModal({
  open,
  onCancel,
  onSubmit,
  submitting,
}: {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: NewProjectValues) => Promise<void> | void;
  submitting: boolean;
}) {
  const [form] = Form.useForm<NewProjectValues>();
  const createRepo = Form.useWatch('create_github_repo', form);

  useEffect(() => {
    if (!open) form.resetFields();
  }, [open, form]);

  return (
    <Modal
      open={open}
      title="New project"
      okText="Create"
      onCancel={onCancel}
      confirmLoading={submitting}
      onOk={async () => {
        const values = await form.validateFields();
        await onSubmit(values);
      }}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={{ create_github_repo: false, visibility: 'private' }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: 'Required' }]}
        >
          <Input placeholder="My App" />
        </Form.Item>
        <Form.Item
          name="bootstrap_url"
          label="Bootstrap repo URL"
          rules={[
            { required: true, message: 'Required' },
            { type: 'url', message: 'Must be a valid URL' },
          ]}
        >
          <Input placeholder="https://github.com/org/vite-template" />
        </Form.Item>

        <Form.Item name="create_github_repo" valuePropName="checked">
          <Checkbox>Create a GitHub repository for me</Checkbox>
        </Form.Item>

        {createRepo ? (
          <>
            <Form.Item name="visibility" label="Visibility">
              <Radio.Group
                options={[
                  { value: 'private', label: 'Private' },
                  { value: 'public', label: 'Public' },
                ]}
                optionType="button"
              />
            </Form.Item>
            <Form.Item name="description" label="Description (optional)">
              <Input placeholder="Built with Lingua" />
            </Form.Item>
          </>
        ) : (
          <Form.Item
            name="target_url"
            label="Target repo URL (optional)"
            rules={[{ type: 'url', message: 'Must be a valid URL' }]}
          >
            <Input placeholder="https://github.com/user/my-app" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
