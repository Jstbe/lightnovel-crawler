import {API_BASE_URL} from '@/config';
import {type Novel} from '@/types';
import {formatDate} from '@/utils/time';
import {ExportOutlined, SyncOutlined} from '@ant-design/icons';
import {
    Card,
    Descriptions,
    Divider,
    Empty,
    Flex,
    Grid,
    Image,
    Tag,
    Tooltip,
    Typography,
    Button,
    Space
} from 'antd';
import {useState} from 'react';
import {Link, useLocation} from 'react-router-dom';
import {NovelDomainName} from './NovelDomainName';
import axios from 'axios';
import {type MessageInstance} from "antd/es/message/interface";

export const NovelDetailsCard: React.FC<{ novel?: Novel; messageApi: MessageInstance; }> = ({novel, messageApi}) => {
    const location = useLocation();
    const {lg} = Grid.useBreakpoint();

    const [hasMore, setHasMore] = useState<boolean>(false);
    const [showMore, setShowMore] = useState<boolean>(false);

    const handleUpdate = async () => {
        if (!novel) return;
        try {
            await axios.post('/api/job', new URLSearchParams({url: novel.url}),
                {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                });
            messageApi.success('Update job has been created successfully.');
        } catch (err) {
            messageApi.error('Failed to create update job.');
        }
    };

    if (!novel?.title) {
        return (
            <Card variant="outlined">
                <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="Novel details is not available"
                />
            </Card>
        );
    }

    return (
        <Card
            variant="outlined"
            styles={{
                title: {
                    padding: '8px 0',
                    marginRight: 10,
                },
            }}
            title={
                <Flex vertical>
                    <NovelDomainName novel={novel}/>
                    <Typography.Text style={{fontSize: '24px', whiteSpace: 'wrap'}}>
                        {location.pathname === `/novel/${novel.id}` ? (
                            novel.title
                        ) : (
                            <Link to={`/novel/${novel.id}`}>{novel.title}</Link>
                        )}
                    </Typography.Text>
                </Flex>
            }
            extra={[
                <Space>
                    <Tooltip title={'Update novel'}>
                        <Button
                            shape="circle"
                            icon={<SyncOutlined/>}
                            onClick={handleUpdate}
                        />
                    </Tooltip>
                    <Tooltip title={'Original source'}>
                        <Typography.Link
                            href={novel.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            style={{fontSize: '24px'}}
                        >
                            <ExportOutlined/>
                        </Typography.Link>
                    </Tooltip>
                </Space>
            ]}
        >
            <Flex gap="20px" vertical={!lg}>
                <Flex vertical align="center" justify="flex-start" gap="5px">
                    <Image
                        alt="Novel Cover"
                        src={`${API_BASE_URL}/api/novel/${novel.id}/cover`}
                        fallback="/no-image.svg"
                        style={{
                            display: 'block',
                            objectFit: 'cover',
                            borderRadius: 8,
                            width: 'auto',
                            height: '300px',
                        }}
                    />
                </Flex>
                <Flex vertical flex="auto" gap="5px">
                    <Descriptions
                        size="small"
                        layout="horizontal"
                        column={lg ? 2 : 1}
                        bordered
                        items={[
                            {
                                label: 'Authors',
                                span: 2,
                                children: novel.authors,
                            },
                            {
                                label: 'Volumes',
                                children: novel.volume_count,
                            },
                            {
                                label: 'Chapters',
                                children: novel.chapter_count,
                            },
                            {
                                label: 'Created',
                                children: formatDate(novel.created_at),
                            },
                            {
                                label: 'Last Update',
                                children: formatDate(novel.updated_at),
                            },
                        ]}
                    />

                    <Typography.Paragraph
                        type="secondary"
                        style={{
                            textAlign: 'justify',
                            overflow: 'hidden',
                            maxHeight: showMore ? undefined : '280px',
                        }}
                        ref={(el) => {
                            if (!el) return;
                            setHasMore(Math.abs(el.scrollHeight - el.clientHeight) > 10);
                        }}
                    >
                        {novel.synopsis ? (
                            <span dangerouslySetInnerHTML={{__html: novel.synopsis}}/>
                        ) : (
                            'No synopsis available'
                        )}
                    </Typography.Paragraph>

                    {(hasMore || showMore) && (
                        <Typography.Link
                            italic
                            onClick={() => setShowMore((v) => !v)}
                            style={{textAlign: showMore ? 'left' : 'right'}}
                        >
                            {showMore ? '< See less' : 'See more >'}
                        </Typography.Link>
                    )}
                </Flex>
            </Flex>

            {novel.tags && Array.isArray(novel.tags) && novel.tags.length > 0 && (
                <Flex wrap gap="5px" justify="center" style={{width: '100%'}}>
                    <Divider size="small"/>
                    {novel.tags.map((tag) => (
                        <Tag key={tag} style={{textTransform: 'capitalize', margin: 0}}>
                            {tag.toLowerCase()}
                        </Tag>
                    ))}
                </Flex>
            )}
        </Card>
    );
};
