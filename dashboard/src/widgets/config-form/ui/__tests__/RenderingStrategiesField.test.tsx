import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { renderingRuntimeSchema } from "../../../../entities/config/model/renderingConfig";
import { FieldRenderer } from "../FieldRenderer";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

function StrategiesField() {
  const [value, setValue] = useState<unknown>([]);
  const preview = renderingRuntimeSchema.parse({
    t2i_mainland_cdn_base_url: "https://mainland.example",
    t2i_overseas_cdn_base_url: "https://overseas.example",
    t2i_rendering_strategies: value,
  });
  return <>
    <FieldRenderer
      fieldKey="t2i_rendering_strategies"
      fieldSchema={schema.t2i_rendering.items.t2i_rendering_strategies}
      value={value}
      onChange={setValue}
    />
    <pre data-testid="strategies">{JSON.stringify(value)}</pre>
    <output data-testid="preview">{preview.t2i_cdn_base_url}</output>
  </>;
}

it("可添加多轮、设置环境和优先级，并驱动第一优先级预览", () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加 渲染方案/ }));
  let strategies: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(strategies).toHaveLength(1);
  expect(strategies).toMatchObject([{ __template_key: "strategy", priority: 10, environment: "Overseas" }]);
  fireEvent.mouseDown(screen.getAllByRole("combobox")[0]);
  fireEvent.click(screen.getByText("内地（Mainland）"));
  expect(screen.getByTestId("preview")).toHaveTextContent("https://mainland.example");
  fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "20" } });
  fireEvent.click(screen.getByRole("button", { name: /添加 渲染方案/ }));
  strategies = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(strategies).toHaveLength(2);
  expect(strategies).toMatchObject([{ priority: 20, environment: "Mainland" }, { priority: 10, environment: "Overseas" }]);
  expect(screen.getByTestId("preview")).toHaveTextContent("https://overseas.example");
});
