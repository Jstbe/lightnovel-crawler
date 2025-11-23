import { Button, Card, Form, Input, InputNumber, Switch, message } from 'antd';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { type Novel } from '@/types';
import { stringifyError } from '@/utils/errors';

interface SchedulingCardProps {
    novel: Novel;
}

export const SchedulingCard: React.FC<SchedulingCardProps> = ({ novel }) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const [messageApi, contextHolder] = message.useMessage();

    useEffect(() => {
        if (novel.extra?.schedule) {
            form.setFieldsValue(novel.extra.schedule);
        } else {
            form.setFieldsValue({
                enabled: false,
                cron: '0 0 * * *', // Default daily
                full_scan_interval_days: 30
            });
        }
    }, [novel, form]);

    const onFinish = async (values: any) => {
        setLoading(true);
        try {
            await axios.put(`/api/novel/${novel.id}/schedule`, values);
            messageApi.success('Schedule updated successfully');
        } catch (err) {
            messageApi.error(stringifyError(err, 'Failed to update schedule'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {contextHolder}
            <Card title="Scheduling" variant="outlined">
                <Form
                    form={form}
                    layout="vertical"
                    onFinish={onFinish}
                    initialValues={{
                        enabled: false,
                        cron: '0 0 * * *',
                        full_scan_interval_days: 30
                    }}
                >
                    <Form.Item
                        name="enabled"
                        label="Enable Auto Updates"
                        valuePropName="checked"
                    >
                        <Switch />
                    </Form.Item>

                    <Form.Item
                        name="cron"
                        label="Cron Expression"
                        rules={[{ required: true, message: 'Please enter a cron expression' }]}
                        tooltip="Standard cron expression (e.g., '0 0 * * *' for daily at midnight)"
                    >
                        <Input placeholder="0 0 * * *" />
                    </Form.Item>

                    <Form.Item
                        name="full_scan_interval_days"
                        label="Full Scan Interval (Days)"
                        rules={[{ required: true, message: 'Please enter days' }]}
                        tooltip="Days between full scans to check for missed chapters"
                    >
                        <InputNumber min={1} style={{ width: '100%' }} />
                    </Form.Item>

                    <Form.Item>
                        <Button type="primary" htmlType="submit" loading={loading}>
                            Save Configuration
                        </Button>
                    </Form.Item>
                </Form>
            </Card>
        </>
    );
};
