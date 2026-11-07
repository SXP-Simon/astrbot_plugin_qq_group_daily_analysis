import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FilePicker } from "../file-picker";

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
