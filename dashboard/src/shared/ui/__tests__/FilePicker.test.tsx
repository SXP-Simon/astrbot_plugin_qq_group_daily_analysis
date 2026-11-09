import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FilePicker } from "@/shared/ui/file-picker";

it("多选将同一批文件一次性交给调用方，仍可重新选择相同批次", () => {
  const selected = vi.fn();
  render(
    <FilePicker label="选择参考文件" multiple onSelect={selected}>
      上传参考文件
    </FilePicker>,
  );
  const input = screen.getByLabelText("选择参考文件");
  const files = [new File(["one"], "one.png"), new File(["two"], "two.png")];
  expect(input).toHaveAttribute("multiple");
  fireEvent.change(input, { target: { files } });
  fireEvent.change(input, { target: { files } });
  expect(selected).toHaveBeenCalledTimes(2);
  expect(selected).toHaveBeenLastCalledWith(files);
  expect(input).toHaveValue("");
});

it("选择文件立即交给调用方，同一文件可重新选择；禁用时不执行", () => {
  const selected = vi.fn();
  const view = render(
    <FilePicker label="选择字体文件" accept=".ttf" onSelect={selected}>
      上传字体
    </FilePicker>,
  );
  const file = new File(["font"], "sample.ttf");
  const input = screen.getByLabelText("选择字体文件");
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.change(input, { target: { files: [file] } });
  expect(selected).toHaveBeenCalledTimes(2);
  expect(selected).toHaveBeenLastCalledWith(file);
  expect(input).toHaveValue("");
  view.rerender(
    <FilePicker label="选择字体文件" disabled onSelect={selected}>
      上传字体
    </FilePicker>,
  );
  expect(screen.getByRole("button", { name: "上传字体" })).toBeDisabled();
  fireEvent.change(input, { target: { files: [file] } });
  expect(selected).toHaveBeenCalledTimes(2);
});
