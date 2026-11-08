import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ConfigFileField } from "../ConfigFileField";
import {
  fetchConfigFileContent,
  uploadConfigFile,
} from "../../../../entities/config/api/configApi";

vi.mock("../../../../entities/config/api/configApi", () => ({
  fetchConfigFileContent: vi.fn(),
  uploadConfigFile: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn() } }));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchConfigFileContent).mockResolvedValue(null);
});

function Files() {
  const [value, setValue] = useState<unknown>([]);
  return (
    <ConfigFileField
      value={value}
      multiple
      path="comic.reference_images"
      fileTypes={["png", "webp"]}
      onChange={setValue}
    />
  );
}

it("上传失败可重选同一文件，成功后显示实际路径，选择框按配置限制类型", async () => {
  vi.mocked(uploadConfigFile)
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ path: "files/one.png" });
  render(<Files />);
  const input = screen.getByLabelText("选择参考文件");
  expect(input).toHaveAttribute("accept", ".png,.webp");
  expect(input).toHaveAttribute("multiple");
  const file = new File(["image"], "one.png");
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("上传失败"));
  expect(input).toHaveValue("");
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() => expect(screen.getByText("files/one.png")).toBeInTheDocument());
  expect(uploadConfigFile).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("地址添加保留引用、预览可单独关闭，移除后只修改配置引用", async () => {
  render(<Files />);
  fireEvent.click(screen.getByRole("button", { name: "添加图片 URL / 路径" }));
  fireEvent.change(screen.getByRole("textbox", { name: "参考文件地址" }), {
    target: { value: " https://images.example/one.webp " },
  });
  fireEvent.click(screen.getByRole("button", { name: /^添加$/ }));
  const trigger = screen.getByRole("button", {
    name: "预览参考图片 https://images.example/one.webp",
  });
  trigger.focus();
  fireEvent.click(trigger);
  expect(
    screen.getByRole("dialog", { name: "参考图片 · https://images.example/one.webp" }),
  ).toBeInTheDocument();
  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "移除参考文件 1" }));
  expect(screen.getByText("尚未添加参考文件，可上传图片或填写地址。")).toBeInTheDocument();
  expect(uploadConfigFile).not.toHaveBeenCalled();
  expect(fetchConfigFileContent).not.toHaveBeenCalled();
});
