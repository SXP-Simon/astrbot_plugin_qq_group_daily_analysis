import React, { useState } from "react";
import {
  Modal,
  Tabs,
  Form,
  Input,
  Button,
  Alert,
  Upload,
  Typography,
  message,
  Space,
} from "antd";
import {
  GithubOutlined,
  InboxOutlined,
  DownloadOutlined,
  InfoCircleOutlined,
  BookOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import {
  installTemplateFromUrl,
  installTemplateFromFile,
  TemplateInstallResult,
} from "../../../entities/report/api/reportApi";

const { Dragger } = Upload;
const { Text, Paragraph } = Typography;

interface TemplateInstallModalProps {
  open: boolean;
  onClose: () => void;
  onInstalled?: (result: TemplateInstallResult) => void;
}

const NAMING_GUIDE = (
  <Space direction="vertical" size={2} style={{ width: "100%" }}>
    <Text strong>
      <BookOutlined style={{ marginRight: 6, color: "#1677ff" }} />
      命名与参考规范
    </Text>
    <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.6 }}>
      模板名建议使用小写英文蛇形并带命名空间前缀（如{" "}
      <Text code style={{ fontSize: 12 }}>gda_miku_dream</Text>
      ）：仅含小写字母、数字、下划线，长度不超过 50。避免空格与特殊字符，
      以免报告文件名、预览图与 CDN 链接出错，并与内置模板（scrapbook 等）区分。
      不填写时将从压缩包 / 仓库名自动推断（GitHub 归档的 -main 后缀会被自动去除）。
      中文显示名可在模板根目录下放置可选的{" "}
      <Text code style={{ fontSize: 12 }}>template.json</Text>{" "}
      （如 {"{\"name\": \"初音梦境\"}"}），作为下拉框中的展示名称。可参考标准示例仓库{" "}
      <Typography.Link
        href="https://github.com/lingyun14beta/daily-analysis-report-theme"
        target="_blank"
        rel="noopener noreferrer"
        style={{ fontSize: 12 }}
      >
        lingyun14beta/daily-analysis-report-theme
      </Typography.Link>
      。
    </Text>
  </Space>
);

export const TemplateInstallModal: React.FC<TemplateInstallModalProps> = ({
  open,
  onClose,
  onInstalled,
}) => {
  const [activeTab, setActiveTab] = useState("url");
  const [urlForm] = Form.useForm();
  const [fileForm] = Form.useForm();
  const [pickedFile, setPickedFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const resetState = () => {
    setPickedFile(null);
    urlForm.resetFields();
    fileForm.resetFields();
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleInstallUrl = async () => {
    try {
      const values = await urlForm.validateFields();
      setSubmitting(true);
      const result = await installTemplateFromUrl({
        repo_url: values.repo_url,
        name: values.name || undefined,
      });
      if (result) {
        message.success(`模板已安装：${result.label}（${result.name}）`);
        onInstalled?.(result);
        handleClose();
      } else {
        message.error("安装失败，请检查链接或服务器日志。");
      }
    } catch (e) {
      if (typeof e === "object" && e !== null && "errorFields" in e) {
        return; // form validation
      }
      const err = e as { message?: string };
      message.error(err?.message || "安装失败，请检查链接与网络。");
    } finally {
      setSubmitting(false);
    }
  };

  const handleInstallFile = async () => {
    try {
      const values = await fileForm.validateFields();
      if (!pickedFile) {
        message.warning("请先选择 zip 压缩包。");
        return;
      }
      setSubmitting(true);
      const result = await installTemplateFromFile(pickedFile, values.name || undefined);
      if (result) {
        message.success(`模板已安装：${result.label}（${result.name}）`);
        onInstalled?.(result);
        handleClose();
      } else {
        message.error("安装失败，请检查压缩包内容或服务器日志。");
      }
    } catch (e) {
      if (typeof e === "object" && e !== null && "errorFields" in e) {
        return; // form validation
      }
      const err = e as { message?: string };
      message.error(err?.message || "安装失败，请确认压缩包内包含 image_template.html。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={
        <Space>
          <DownloadOutlined style={{ color: "#1677ff" }} />
          <span>安装自定义报告模板</span>
        </Space>
      }
      open={open}
      onCancel={handleClose}
      footer={null}
      width={620}
    >
      <Alert
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        message="安装即生效"
        description="模板安装后无需重启机器人，会立即出现在「断点续跑」与「免 Token 切换主题重绘」的模板下拉列表中。内置模板不能被覆盖，与内置模板重名时会被拒绝。"
        style={{ marginBottom: 12 }}
      />
      {NAMING_GUIDE}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "url",
            label: (
              <span>
                <GithubOutlined /> GitHub 链接
              </span>
            ),
            children: (
              <Form form={urlForm} layout="vertical">
                <Form.Item
                  name="repo_url"
                  label="GitHub 仓库链接"
                  rules={[
                    { required: true, message: "请填写 GitHub 仓库链接" },
                    {
                      pattern: /^https:\/\/(?:www\.)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+/i,
                      message: "仅支持 https://github.com 仓库链接（如 https://github.com/owner/repo）",
                    },
                  ]}
                >
                  <Input
                    placeholder="https://github.com/lingyun14beta/daily-analysis-report-theme"
                    allowClear
                  />
                </Form.Item>
                <Form.Item
                  name="name"
                  label="模板名（可选，留空自动推断）"
                  extra="留空时使用仓库名（自动去除 -main / -master 后缀）。"
                >
                  <Input placeholder="gda_miku_dream" allowClear />
                </Form.Item>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  loading={submitting}
                  onClick={handleInstallUrl}
                  block
                >
                  下载并安装
                </Button>
              </Form>
            ),
          },
          {
            key: "file",
            label: (
              <span>
                <InboxOutlined /> 上传 zip
              </span>
            ),
            children: (
              <Form form={fileForm} layout="vertical">
                <Form.Item label="zip 压缩包（需包含 image_template.html 或 html_template.html）">
                  <Dragger
                    accept=".zip"
                    maxCount={1}
                    beforeUpload={(file) => {
                      setPickedFile(file);
                      return false; // 阻止自动上传，由手动提交触发
                    }}
                    onRemove={() => setPickedFile(null)}
                  >
                    <p className="ant-upload-drag-icon">
                      <InboxOutlined />
                    </p>
                    <p className="ant-upload-text">点击或拖拽 zip 到此处</p>
                    <p className="ant-upload-hint">
                      单个文件，打包时请保留模板根目录（建议仅包含 7 个 HTML 模板文件与可选 template.json）
                    </p>
                  </Dragger>
                </Form.Item>
                <Form.Item
                  name="name"
                  label="模板名（可选，留空自动推断）"
                  extra="留空时使用压缩包根目录名（GitHub 归档的 -main 后缀会自动去除）。"
                >
                  <Input placeholder="gda_miku_dream" allowClear />
                </Form.Item>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  loading={submitting}
                  onClick={handleInstallFile}
                  block
                >
                  解压并安装
                </Button>
              </Form>
            ),
          },
        ]}
      />
      <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}>
        <BulbOutlined style={{ marginRight: 6, color: "#faad14" }} />
        模板结构参考：内置模板位于插件目录{" "}
        <Text code style={{ fontSize: 12 }}>src/infrastructure/reporting/templates/scrapbook/</Text>
        ，完整 7 件套为 image_template.html / html_template.html / topic_item.html /
        user_title_item.html / quote_item.html / activity_chart.html / chat_quality_item.html。
      </Paragraph>
    </Modal>
  );
};
