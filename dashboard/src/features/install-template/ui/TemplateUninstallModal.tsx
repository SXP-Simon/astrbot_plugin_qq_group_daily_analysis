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
import {
  DeleteOutlined,
  SafetyOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  fetchReportTemplates,
  uninstallTemplate,
} from "../../../entities/report/api/reportApi";
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
      // 仅展示可通过安装器卸载的自定义模板（带安装标记的后端确认项）；
      // 内置模板与手动放置/自动备份目录（含内置模板的“自定义修改版”）不显示
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
        message="仅可卸载通过「安装模板」下载的模板"
        description="内置模板不可卸载；手动复制到数据目录的模板（无安装标记）也需手动删除文件。卸载后模板将从断点续跑 / 免 Token 重绘下拉中移除；若当前正在使用该模板，报告会自动回退到默认手账风格。"
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
              description="暂无通过插件安装的自定义模板"
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
                      <Button
                        size="small"
                        danger
                        type="text"
                        icon={<DeleteOutlined />}
                      >
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
                        {item.desc
                          ? item.desc
                          : item.has_image && item.has_html
                          ? "长图 + 网页 双模式"
                          : item.has_image
                          ? "长图模式"
                          : "网页模式"}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </div>
      </Spin>
      <Button
        icon={<ReloadOutlined />}
        onClick={loadTemplates}
        style={{ marginTop: 12 }}
        block
      >
        刷新列表
      </Button>
    </Modal>
  );
};
