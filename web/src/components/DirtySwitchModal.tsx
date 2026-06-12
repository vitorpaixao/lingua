import { Button, Modal, Typography } from 'antd';

const { Paragraph, Text } = Typography;

export function DirtySwitchModal({
  open,
  dirtyFiles,
  currentName,
  onCancel,
  onPublishFirst,
  onSwitchAnyway,
  publishing,
}: {
  open: boolean;
  dirtyFiles: number;
  currentName: string;
  onCancel: () => void;
  onPublishFirst: () => Promise<void> | void;
  onSwitchAnyway: () => Promise<void> | void;
  publishing: boolean;
}) {
  return (
    <Modal
      open={open}
      title="Switch workspace?"
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          Cancel
        </Button>,
        <Button
          key="publish"
          loading={publishing}
          onClick={async () => {
            await onPublishFirst();
          }}
        >
          Publish first
        </Button>,
        <Button
          key="switch"
          type="primary"
          danger
          onClick={async () => {
            await onSwitchAnyway();
          }}
        >
          Switch anyway
        </Button>,
      ]}
    >
      <Paragraph>
        Project <Text strong>{currentName}</Text> has{' '}
        <Text strong>{dirtyFiles}</Text> unsaved change
        {dirtyFiles === 1 ? '' : 's'}.
      </Paragraph>
      <Paragraph>
        They will stay on disk and be available when you open this project again. No
        data is lost.
      </Paragraph>
    </Modal>
  );
}
