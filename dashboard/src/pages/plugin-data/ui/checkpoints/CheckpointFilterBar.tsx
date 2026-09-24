import React from "react";
import { Card, Row, Col, Select, Input, Space, Button } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { usePluginDataViewModel } from "../../model/usePluginDataViewModel";

interface CheckpointFilterBarProps {
  vm: ReturnType<typeof usePluginDataViewModel>;
}

export const CheckpointFilterBar: React.FC<CheckpointFilterBarProps> = ({
  vm,
}) => {
  const {
    ckptGroups,
    ckptFilterGroup,
    ckptFilterDate,
    ckptFilterStage,
    checkpointsPageSize,
    loadingCheckpoints,
  } = vm;

  return (
    <Card size="small">
      <Row gutter={[12, 8]} align="middle">
        <Col xs={24} sm={6} md={5}>
          <Select
            style={{ width: "100%" }}
            allowClear
            placeholder="按群号筛选"
            value={ckptFilterGroup}
            onChange={(val) => {
              vm.setCkptFilterGroup(val);
              vm.loadCheckpoints(
                1,
                checkpointsPageSize,
                val,
                ckptFilterDate,
                ckptFilterStage
              );
            }}
            options={ckptGroups.map((g) => ({ label: `群: ${g}`, value: g }))}
          />
        </Col>

        <Col xs={24} sm={6} md={5}>
          <Input
            allowClear
            placeholder="归属日期 (如 2026-09-10)"
            value={ckptFilterDate}
            onChange={(e) =>
              vm.setCkptFilterDate(e.target.value.trim() || undefined)
            }
            onPressEnter={() =>
              vm.loadCheckpoints(
                1,
                checkpointsPageSize,
                ckptFilterGroup,
                ckptFilterDate,
                ckptFilterStage
              )
            }
          />
        </Col>

        <Col xs={24} sm={6} md={5}>
          <Select
            style={{ width: "100%" }}
            allowClear
            placeholder="按流水线阶段筛选"
            value={ckptFilterStage}
            onChange={(val) => {
              vm.setCkptFilterStage(val);
              vm.loadCheckpoints(
                1,
                checkpointsPageSize,
                ckptFilterGroup,
                ckptFilterDate,
                val
              );
            }}
            options={[
              { label: "全部阶段", value: "" },
              {
                label: "拉取聊天记录 (FETCH_MESSAGES)",
                value: "FETCH_MESSAGES",
              },
              {
                label: "消息清洗过滤 (CLEAN_MESSAGES)",
                value: "CLEAN_MESSAGES",
              },
              {
                label: "基础统计分析 (STATS_ANALYSIS)",
                value: "STATS_ANALYSIS",
              },
              {
                label: "大模型话题与画像分析 (LLM_ANALYSIS)",
                value: "LLM_ANALYSIS",
              },
              {
                label: "历史记录持久化 (SAVE_SUMMARY)",
                value: "SAVE_SUMMARY",
              },
              {
                label: "报告长图渲染 (RENDER_REPORT)",
                value: "RENDER_REPORT",
              },
              {
                label: "群聊消息投递 (DISPATCH_REPORT)",
                value: "DISPATCH_REPORT",
              },
            ]}
          />
        </Col>

        <Col xs={24} sm={6} md={6}>
          <Space size={8}>
            <Button
              type="primary"
              size="small"
              onClick={() =>
                vm.loadCheckpoints(
                  1,
                  checkpointsPageSize,
                  ckptFilterGroup,
                  ckptFilterDate,
                  ckptFilterStage
                )
              }
              loading={loadingCheckpoints}
            >
              查询
            </Button>
            <Button
              size="small"
              icon={<ReloadOutlined spin={loadingCheckpoints} />}
              onClick={() => {
                vm.refreshCheckpointGroups();
                vm.loadCheckpoints();
              }}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>
    </Card>
  );
};
