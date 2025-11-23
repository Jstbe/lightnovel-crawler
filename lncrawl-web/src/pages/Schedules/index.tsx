import React, { useEffect, useState } from 'react';
import {
    Button,
    Flex,
    Form,
    Input,
    InputNumber,
    Result,
    Space,
    Spin,
    Switch,
    Table,
    Typography,
    message,
    Image
} from 'antd';
import { SyncOutlined, EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import axios from 'axios';
import { type Novel } from '@/types';
import { stringifyError } from '@/utils/errors';
import { formatDate } from '@/utils/time';
import { API_BASE_URL } from '@/config';

export const SchedulesPage: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [novels, setNovels] = useState<Novel[]>([]);
    const [error, setError] = useState<string>();
    const [messageApi, contextHolder] = message.useMessage();
    const [editingId, setEditingId] = useState<string | null>(null);
    const [form] = Form.useForm();

    const fetchNovels = async () => {
        setLoading(true);
        setError(undefined);
        try {
            const { data } = await axios.get('/api/novels', {
                params: { limit: 1000, with_orphans: false },
            });
            setNovels(data.items);
        } catch (err) {
            setError(stringifyError(err, 'Failed to load novels'));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchNovels();
    }, []);

    const handleSave = async (id: string) => {
        try {
            const row = await form.validateFields();
            const novel = novels.find((n) => n.id === id);
            if (!novel) return;

            const currentSchedule = novel.extra?.schedule || {};
            const newSchedule = {
                ...currentSchedule,
                ...row,
            };

            await axios.put(`/api/novel/${id}/schedule`, newSchedule);

            setNovels((prev) =>
                prev.map((n) =>
                    n.id === id
                        ? { ...n, extra: { ...n.extra, schedule: newSchedule } }
                        : n
                )
            );

            setEditingId(null);
            messageApi.success('Schedule updated');
        } catch (err) {
            messageApi.error(stringifyError(err, 'Failed to save schedule'));
        }
    };

    const columns = [
        {
            title: 'Cover',
            key: 'cover',
            width: 80,
            render: (_: any, record: Novel) => (
                <Image
                    src={`${API_BASE_URL}/api/novel/${record.id}/cover`}
                    fallback="/no-image.svg"
                    width={50}
                    height={70}
                    style={{ objectFit: 'cover', borderRadius: 4 }}
                    preview={false}
                />
            ),
        },
        {
            title: 'Title',
            dataIndex: 'title',
            key: 'title',
            render: (text: string, record: Novel) => (
                <Space direction="vertical" size={0}>
                    <Typography.Text strong>{text}</Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {record.chapter_count} Chapters
                    </Typography.Text>
                </Space>
            )
        },
        {
            title: 'Last Update',
            dataIndex: 'updated_at',
            key: 'updated_at',
            render: (ts: number) => formatDate(ts),
        },
        {
            title: 'Next Update',
            key: 'next_run',
            render: (_: any, record: Novel) => {
                const nextRun = record.extra?.schedule?.next_run;
                return nextRun ? formatDate(nextRun * 1000) : '-';
            },
        },
        {
            title: 'Cron Expression',
            dataIndex: ['extra', 'schedule', 'cron'],
            key: 'cron',
            editable: true,
            render: (text: string, record: Novel) => {
                if (editingId === record.id) {
                    return (
                        <Form.Item
                            name="cron"
                            style={{ margin: 0 }}
                            rules={[{ required: true, message: 'Required' }]}
                            initialValue={text || '0 0 * * *'}
                        >
                            <Input />
                        </Form.Item>
                    );
                }
                return text || '-';
            },
        },
        {
            title: 'Full Scan (Days)',
            dataIndex: ['extra', 'schedule', 'full_scan_interval_days'],
            key: 'full_scan',
            editable: true,
            render: (text: number, record: Novel) => {
                if (editingId === record.id) {
                    return (
                        <Form.Item
                            name="full_scan_interval_days"
                            style={{ margin: 0 }}
                            rules={[{ required: true, message: 'Required' }]}
                            initialValue={text || 30}
                        >
                            <InputNumber min={1} />
                        </Form.Item>
                    );
                }
                return text || 30;
            },
        },
        {
            title: 'Enabled',
            dataIndex: ['extra', 'schedule', 'enabled'],
            key: 'enabled',
            render: (enabled: boolean, record: Novel) => {
                if (editingId === record.id) {
                    return (
                        <Form.Item
                            name="enabled"
                            valuePropName="checked"
                            style={{ margin: 0 }}
                            initialValue={enabled}
                        >
                            <Switch size="small" />
                        </Form.Item>
                    )
                }
                return <Switch size="small" checked={enabled} disabled />;
            },
        },
        {
            title: 'Action',
            key: 'action',
            render: (_: any, record: Novel) => {
                const isEditing = editingId === record.id;
                return isEditing ? (
                    <Space>
                        <Button
                            type="primary"
                            size="small"
                            icon={<SaveOutlined />}
                            onClick={() => handleSave(record.id)}
                        />
                        <Button
                            size="small"
                            danger
                            icon={<CloseOutlined />}
                            onClick={() => setEditingId(null)}
                        />
                    </Space>
                ) : (
                    <Button
                        size="small"
                        icon={<EditOutlined />}
                        disabled={editingId !== null}
                        onClick={() => {
                            setEditingId(record.id);
                            form.setFieldsValue({
                                cron: record.extra?.schedule?.cron || '0 0 * * *',
                                full_scan_interval_days: record.extra?.schedule?.full_scan_interval_days || 30,
                                enabled: record.extra?.schedule?.enabled || false
                            });
                        }}
                    />
                );
            },
        },
    ];

    if (loading) {
        return (
            <Flex align="center" justify="center" style={{ height: '100%' }}>
                <Spin size="large" style={{ marginTop: 100 }} />
            </Flex>
        );
    }

    if (error) {
        return (
            <Flex align="center" justify="center" style={{ height: '100%' }}>
                <Result
                    status="error"
                    title="Failed to load schedules"
                    subTitle={error}
                    extra={[<Button onClick={fetchNovels}>Retry</Button>]}
                />
            </Flex>
        );
    }

    return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
            {contextHolder}
            <Flex justify="space-between" align="center">
                <Typography.Title level={2} style={{ margin: 0 }}>
                    📅 Schedules
                </Typography.Title>
                <Button icon={<SyncOutlined />} onClick={fetchNovels}>
                    Refresh
                </Button>
            </Flex>

            <Form form={form} component={false}>
                <Table
                    components={{
                        body: {
                            cell: ({ children, ...restProps }: any) => (
                                <td {...restProps}>{children}</td>
                            ),
                        },
                    }}
                    bordered
                    dataSource={novels}
                    columns={columns}
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                />
            </Form>
        </Space>
    );
};
