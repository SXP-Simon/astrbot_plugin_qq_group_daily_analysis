import React, { useState } from "react";
import {
  Card,
  Button,
  Space,
  Tag,
  Typography,
  Dropdown,
  Popconfirm,
  Empty,
  MenuProps,
  theme,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  SettingOutlined,
  DownOutlined,
} from "@ant-design/icons";
import { SchemaFieldItem } from "../../../entities/config/model/types";
import {
  AvailableProvider,
  AvailablePersona,
} from "../../../entities/config/api/configApi";
import { FieldRenderer } from "./FieldRenderer";

const { Text } = Typography;

interface TemplateListRendererProps {
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  providers?: AvailableProvider[];
  personas?: AvailablePersona[];
  fullKeyPath?: string;
  onChange: (val: unknown) => void;
}

export const TemplateListRenderer: React.FC<TemplateListRendererProps> = ({
  fieldKey,
  fieldSchema,
  value,
  providers = [],
  personas = [],
  fullKeyPath,
  onChange,
}) => {
  const { token } = theme.useToken();
  const [activeItemIndex, setActiveItemIndex] = useState<number | null>(null);

  const rawList: Record<string, unknown>[] = Array.isArray(value)
    ? (value as Record<string, unknown>[])
    : Array.isArray(fieldSchema.default)
      ? (fieldSchema.default as Record<string, unknown>[])
      : [];

  const templates = (fieldSchema.templates as Record<
    string,
    {
      name?: string;
      description?: string;
      display_item?: string;
      items?: Record<string, SchemaFieldItem>;
    }
  >) || {};

  const templateKeys = Object.keys(templates);

  // 根据条目数据匹配模板 Key
  const findTemplateKey = (item: Record<string, unknown>): string | null => {
    if (item.__template_key && templates[String(item.__template_key)]) {
      return String(item.__template_key);
    }
    if (item.name && templates[String(item.name)]) {
      return String(item.name);
    }
    for (const [key, tpl] of Object.entries(templates)) {
      if (tpl.name === item.name || key === item.name) {
        return key;
      }
    }
    return templateKeys.length > 0 ? templateKeys[0] : null;
  };

  // 根据条目数据匹配模板定义
  const findTemplateForItem = (item: Record<string, unknown>) => {
    const key = findTemplateKey(item);
    return key ? templates[key] || null : null;
  };

  // 添加新条目
  const handleAddItem = (templateKey: string) => {
    const tpl = templates[templateKey];
    if (!tpl) return;

    const newItem: Record<string, unknown> = {
      __template_key: templateKey,
      name: tpl.name || templateKey,
    };

    if (tpl.items) {
      for (const [subKey, subField] of Object.entries(tpl.items)) {
        if (subField.default !== undefined) {
          newItem[subKey] = subField.default;
        }
      }
    }

    const nextList = [...rawList, newItem];
    onChange(nextList);
    setActiveItemIndex(nextList.length - 1);
  };

  // 修改条目内字段
  const handleItemFieldChange = (
    index: number,
    subFieldKey: string,
    subVal: unknown
  ) => {
    const nextList = rawList.map((item, idx) => {
      if (idx !== index) return item;
      const tplKey = findTemplateKey(item);
      return {
        ...item,
        ...(tplKey ? { __template_key: tplKey } : {}),
        [subFieldKey]: subVal,
      };
    });
    onChange(nextList);
  };

  // 删除条目
  const handleDeleteItem = (index: number) => {
    const nextList = rawList.filter((_, idx) => idx !== index);
    onChange(nextList);
    if (activeItemIndex === index) {
      setActiveItemIndex(null);
    } else if (activeItemIndex !== null && activeItemIndex > index) {
      setActiveItemIndex(activeItemIndex - 1);
    }
  };

  // 上移条目
  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    const nextList = [...rawList];
    const temp = nextList[index - 1];
    nextList[index - 1] = nextList[index];
    nextList[index] = temp;
    onChange(nextList);
    if (activeItemIndex === index) setActiveItemIndex(index - 1);
  };

  // 下移条目
  const handleMoveDown = (index: number) => {
    if (index >= rawList.length - 1) return;
    const nextList = [...rawList];
    const temp = nextList[index + 1];
    nextList[index + 1] = nextList[index];
    nextList[index] = temp;
    onChange(nextList);
    if (activeItemIndex === index) setActiveItemIndex(index + 1);
  };

  // 添加下拉菜单项
  const menuItems: MenuProps["items"] = templateKeys.map((tplKey) => {
    const tpl = templates[tplKey];
    return {
      key: tplKey,
      label: (
        <div>
          <div style={{ fontWeight: 600, fontSize: 12 }}>
            {tpl.name || tplKey}
          </div>
          {tpl.description && (
            <div style={{ fontSize: 11, color: token.colorTextSecondary }}>
              {tpl.description}
            </div>
          )}
        </div>
      ),
      onClick: () => handleAddItem(tplKey),
    };
  });

  return (
    <div style={{ width: "100%" }}>
      {rawList.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无配置条目，请点击下方按钮添加"
          style={{
            margin: "12px 0",
            padding: "16px",
            background: token.colorFillAlter,
            borderRadius: 6,
            border: `1px dashed ${token.colorBorderSecondary}`,
          }}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
          {rawList.map((item, index) => {
            const itemTemplateKey = findTemplateKey(item) || templateKeys[0] || "character";
            const tpl = findTemplateForItem(item);
            const subItems = tpl?.items || {};

            // 标题展示
            const displayName =
              String(item.name || tpl?.name || `条目 #${index + 1}`);
            const priorityVal = item.priority !== undefined ? item.priority : null;
            const isEnable = item.enable !== undefined ? Boolean(item.enable) : true;

            return (
              <Card
                key={`${fieldKey}_item_${index}`}
                size="small"
                style={{
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: 6,
                  background: token.colorFillAlter,
                }}
                styles={{ body: { padding: "12px 14px" } }}
              >
                {/* 头部标题与控制按钮 */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 12,
                    paddingBottom: 8,
                    borderBottom: `1px solid ${token.colorBorderSecondary}`,
                  }}
                >
                  <Space size={8} align="center">
                    <SettingOutlined style={{ color: "#2563eb", fontSize: 13 }} />
                    <Text strong style={{ fontSize: 13 }}>
                      {displayName}
                    </Text>
                    {priorityVal !== null && (
                      <Tag color="blue" style={{ margin: 0, fontSize: 10 }}>
                        优先级: {String(priorityVal)}
                      </Tag>
                    )}
                    {item.enable !== undefined && (
                      <Tag
                        color={isEnable ? "success" : "default"}
                        style={{ margin: 0, fontSize: 10 }}
                      >
                        {isEnable ? "已启用" : "已禁用"}
                      </Tag>
                    )}
                  </Space>

                  <Space size={4}>
                    <Button
                      size="small"
                      type="text"
                      icon={<ArrowUpOutlined style={{ fontSize: 11 }} />}
                      disabled={index === 0}
                      onClick={() => handleMoveUp(index)}
                    />
                    <Button
                      size="small"
                      type="text"
                      icon={<ArrowDownOutlined style={{ fontSize: 11 }} />}
                      disabled={index === rawList.length - 1}
                      onClick={() => handleMoveDown(index)}
                    />
                    <Popconfirm
                      title="确认删除此配置条目？"
                      onConfirm={() => handleDeleteItem(index)}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true, size: "small" }}
                      cancelButtonProps={{ size: "small" }}
                    >
                      <Button
                        size="small"
                        type="text"
                        danger
                        icon={<DeleteOutlined style={{ fontSize: 11 }} />}
                      />
                    </Popconfirm>
                  </Space>
                </div>

                {/* 条目内部各字段渲染 */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "10px 16px" }}>
                  {Object.entries(subItems).map(([subKey, subField]) => {
                    const isFullWidth =
                      subField.type === "template_list" ||
                      subField.type === "text" ||
                      subField.type === "file" ||
                      subKey.includes("prompt") ||
                      subKey.includes("image") ||
                      subKey.includes("url") ||
                      subKey.includes("key");

                    return (
                      <div
                        key={subKey}
                        style={{
                          gridColumn: isFullWidth ? "1 / -1" : "auto",
                        }}
                      >
                        <FieldRenderer
                          fieldKey={subKey}
                          fieldSchema={subField}
                          value={item[subKey] !== undefined ? item[subKey] : subField.default}
                          providers={providers}
                          personas={personas}
                          isSubField={true}
                          fullKeyPath={`${fullKeyPath || fieldKey}.templates.${itemTemplateKey}.${subKey}`}
                          onChange={(newSubVal) =>
                            handleItemFieldChange(index, subKey, newSubVal)
                          }
                        />
                      </div>
                    );
                  })}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* 底部添加条目按钮 */}
      {templateKeys.length > 1 ? (
        <Dropdown menu={{ items: menuItems }} placement="bottomLeft">
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            style={{ width: "100%" }}
          >
            添加配置项 <DownOutlined style={{ fontSize: 10, marginLeft: 4 }} />
          </Button>
        </Dropdown>
      ) : templateKeys.length === 1 ? (
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          style={{ width: "100%" }}
          onClick={() => handleAddItem(templateKeys[0])}
        >
          添加 {templates[templateKeys[0]]?.name || "新条目"}
        </Button>
      ) : null}
    </div>
  );
};
