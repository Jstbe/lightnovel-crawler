import { Auth } from '@/store/_auth';
import { JobStatus, type Job } from '@/types';
import { stringifyError } from '@/utils/errors';
import {
  CloseOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Button, message, Modal } from 'antd';
import axios from 'axios';
import { useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';

export const JobActionButtons: React.FC<{
  job: Job;
  onChange?: () => any;
}> = ({ job, onChange }) => {
  const navigate = useNavigate();
  const isAdmin = useSelector(Auth.select.isAdmin);
  const currentUser = useSelector(Auth.select.user);
  const [messageApi, contextHolder] = message.useMessage();
  const [modal, modalContextHolder] = Modal.useModal();

  const cancelJob = async () => {
    try {
      await axios.post(`/api/job/${job.id}/cancel`);
      if (onChange) onChange();
    } catch (err) {
      messageApi.open({
        type: 'error',
        content: stringifyError(err, 'Something went wrong!'),
      });
    }
  };

  const deleteJob = async () => {
    try {
      await axios.delete(`/api/job/${job.id}`);
      if (onChange) onChange();
      messageApi.success('Job deleted successfully');
    } catch (err) {
      messageApi.open({
        type: 'error',
        content: stringifyError(err, 'Failed to delete job'),
      });
    }
  };

  const showDeleteConfirm = () => {
    modal.confirm({
      title: 'Are you sure you want to delete this job?',
      content: 'This action cannot be undone.',
      okText: 'Yes, Delete',
      okType: 'danger',
      cancelText: 'No',
      onOk: deleteJob,
    });
  };

  const replayJob = async () => {
    try {
      const result = await axios.post<Job>(
        `/api/job`,
        new URLSearchParams({ url: job.url }).toString(),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );
      navigate({ pathname: `/job/${result.data.id}` });
    } catch (err) {
      messageApi.open({
        type: 'error',
        content: stringifyError(err, 'Something went wrong!'),
      });
    }
  };

  return (
    <>
      {contextHolder}
      {modalContextHolder}
      {job.status === JobStatus.COMPLETED && (
        <>
          <Button onClick={replayJob}>
            <ReloadOutlined /> Replay
          </Button>
          {(isAdmin || job.user_id === currentUser?.id) && (
            <Button danger onClick={showDeleteConfirm}>
              <DeleteOutlined /> Delete
            </Button>
          )}
        </>
      )}
      {(isAdmin || job.user_id === currentUser?.id) &&
        job.status !== JobStatus.COMPLETED && (
          <Button danger onClick={cancelJob}>
            <CloseOutlined /> Cancel
          </Button>
        )}
    </>
  );
};
