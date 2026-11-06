import { templateCapabilities } from "../../../entities/report/model/templates";
import React, { useEffect, useState } from "react";
import {
  Modal,
  List,
  Button,
  Alert,
  Empty,
  Spin,
  Popconfirm,
  Tag,
  Typography,
  message,
  Space,
} from "antd";
import { DeleteOutlined, SafetyOutlined, ReloadOutlined } from "@ant-design/icons";
import { fetchReportTemplates, uninstallTemplate } from "../../../entities/report/api/reportApi";
import { ReportTemplateItem } from "../../../entities/report/model/templates";

const { Text } = Typography;

interface TemplateUninstallModalProps {
  open: boolean;
  onClose: () => void;
  onUninstalled?: (name: string) => void;
}

export const TemplateUninstallModal: React.FC<TemplateUninstallModalProps> = ({
  open,
  onClose,
  onUninstalled,
}) => {
  const [templates, setTemplates] = useState<ReportTemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uninstalling, setUninstalling] = useState<string | null>(null);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const list = await fetchReportTemplates();
      // 移除能力由后端确认，手动放置的自定义模板也可管理。
      setTemplates(list.filter((t) => t.can_uninstall === true));
    } catch {
      message.warning("模板列表获取失败，请检查插件运行状态");
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadTemplates();
    }
  }, [open]);

  const handleUninstall = async (name: string) => {
    setUninstalling(name);
    try {
      const result = await uninstallTemplate(name);
      if (result) {
        message.success(`模板已卸载：${name}`);
        onUninstalled?.(name);
        await loadTemplates();
      } else {
        message.error("卸载失败，请查看服务器日志。");
      }
    } catch (e) {
      const err = e as { message?: string };
      message.error(err?.message || "卸载失败，请查看服务器日志。");
    } finally {
      setUninstalling(null);
    }
  };

  return (
    <Modal
      title={
        <Space>
          <DeleteOutlined style={{ color: "#ff4d4f" }} />
          <span>卸载自定义模板</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
    >
      <Alert
        type="info"
        showIcon
        icon={<SafetyOutlined />}
        message="可移除插件数据目录内的自定义模板"
        description="手动模板也可移除，内置模板保留。将删除选定模板的整个目录及素材；使用它的配置需重新选择，已生成报告不受影响。"
        style={{ marginBottom: 12 }}
      />
      <Spin spinning={loading}>
        <div
          style={{
            maxHeight: 360,
            overflowY: "auto",
            border: "1px solid rgba(128,128,128,0.2)",
            borderRadius: 6,
          }}
        >
          {templates.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无可移除的自定义模板"
              style={{ padding: "24px 0" }}
            />
          ) : (
            <List
              size="small"
              dataSource={templates}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Popconfirm
                      key="uninstall"
                      title={`确定卸载模板「${item.label || item.id}」？`}
                      description="将删除数据目录中的整个模板文件夹，操作不可恢复。"
                      okText="卸载"
                      cancelText="取消"
                      okButtonProps={{ danger: true, loading: uninstalling === item.id }}
                      onConfirm={() => handleUninstall(item.id)}
                    >
                      <Button size="small" danger type="text" icon={<DeleteOutlined />}>
                        卸载
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={6}>
                        <Text style={{ fontSize: 13 }}>{item.label || item.id}</Text>
                        <Tag color="blue" style={{ fontSize: 11 }}>
                          {item.id}
                        </Tag>
                      </Space>
                    }
                    description={
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.desc || templateCapabilities(item).join(" / ")}
                        <span>
                          {templateCapabilities(item).map((capability) => (
                            <Tag key={capability}>{capability}</Tag>
                          ))}
                        </span>
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </div>
      </Spin>
      <Button icon={<ReloadOutlined />} onClick={loadTemplates} style={{ marginTop: 12 }} block>
        刷新列表
      </Button>
    </Modal>
  );
};
