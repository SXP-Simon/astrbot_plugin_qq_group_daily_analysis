import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { FieldRenderer } from "../FieldRenderer";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

function FontField({ fieldKey }: { fieldKey: "google_fonts" | "gstatic" }) {
  const [value, setValue] = useState<unknown>("https://saved.example/proxy");
  return <>
    <FieldRenderer fieldKey={fieldKey} fieldSchema={schema.t2i_rendering.items.t2i_rendering_strategies.templates.strategy.items[fieldKey]} value={value} onChange={setValue} />
    <output data-testid="value">{String(value)}</output>
  </>;
}

it.each(["google_fonts", "gstatic"] as const)("%s 保留已有自定义值、预设选择与新地址输入", (fieldKey) => {
  render(<FontField fieldKey={fieldKey} />);
  const input = screen.getByRole("combobox");
  expect(input).toHaveValue("https://saved.example/proxy");
  fireEvent.mouseDown(input);
  fireEvent.focus(input);
  const field = schema.t2i_rendering.items.t2i_rendering_strategies.templates.strategy.items[fieldKey];
  expect(screen.getAllByText(field.labels[0]).length).toBeGreaterThan(0);
  expect(screen.queryByText("自定义地址…", { exact: true })).not.toBeInTheDocument();
  fireEvent.click(screen.getAllByText(field.labels[0])[0]);
  expect(screen.getByTestId("value")).toHaveTextContent(field.options[0]);
  fireEvent.change(input, { target: { value: "https://new.example/fonts" } });
  expect(screen.getByTestId("value")).toHaveTextContent("https://new.example/fonts");
  expect(screen.queryByRole("button", { name: "检测可用性" })).not.toBeInTheDocument();
});
