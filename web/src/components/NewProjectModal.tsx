import { Form, Input, Modal } from 'antd';
import { useEffect } from 'react';

export type NewProjectValues = {
  name: string;
  bootstrap_url: string;
  target_url?: string;
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
      <Form form={form} layout="vertical" preserve={false}>
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
        <Form.Item
          name="target_url"
          label="Target repo URL (optional)"
          rules={[{ type: 'url', message: 'Must be a valid URL' }]}
        >
          <Input placeholder="https://github.com/user/my-app" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
