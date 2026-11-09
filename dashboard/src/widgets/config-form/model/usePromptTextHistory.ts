import { useCallback, useEffect, useRef, type ChangeEvent, type KeyboardEvent } from "react";

interface TextSelection {
  value: string;
  start: number;
  end: number;
}

interface TextEdit {
  before: TextSelection;
  after: TextSelection;
}

function readSelection(field: HTMLTextAreaElement): TextSelection {
  return { value: field.value, start: field.selectionStart, end: field.selectionEnd };
}

export function usePromptTextHistory(
  editing: boolean,
  text: string,
  onTextChange: (value: string) => void,
) {
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const past = useRef<TextEdit[]>([]);
  const future = useRef<TextEdit[]>([]);
  const beforeInput = useRef<TextSelection>();
  const lastGroup = useRef<{ type: string; time: number }>();

  const restore = useCallback(
    (redo: boolean) => {
      const field = fieldRef.current;
      if (!field) return;
      const edit = (redo ? future : past).current.pop();
      if (!edit) return;
      (redo ? past : future).current.push(edit);
      lastGroup.current = undefined;
      beforeInput.current = undefined;
      const selection = redo ? edit.after : edit.before;
      field.value = selection.value;
      field.setSelectionRange(selection.start, selection.end);
      onTextChange(field.value);
    },
    [onTextChange],
  );

  useEffect(() => {
    const field = fieldRef.current;
    if (!editing || !field) return;
    const handleBeforeInput = (event: InputEvent) => {
      if (event.inputType === "historyUndo" || event.inputType === "historyRedo") {
        event.preventDefault();
        restore(event.inputType === "historyRedo");
      } else {
        beforeInput.current = readSelection(field);
      }
    };
    field.addEventListener("beforeinput", handleBeforeInput);
    return () => field.removeEventListener("beforeinput", handleBeforeInput);
  }, [editing, restore]);

  const record = (before: TextSelection, after: TextSelection, type?: string) => {
    beforeInput.current = undefined;
    if (before.value === after.value) return;
    const last = past.current.at(-1);
    const now = Date.now();
    // 连续输入和同一次输入法组字合并。工具栏插入始终单独撤销。
    if (
      type &&
      last &&
      lastGroup.current?.type === type &&
      last.after.value === before.value &&
      (type === "insertCompositionText" ||
        (now - lastGroup.current.time < 500 &&
          last.after.start === before.start &&
          last.after.end === before.end &&
          before.start === before.end))
    ) {
      last.after = after;
    } else {
      past.current.push({ before, after });
      if (past.current.length > 100) past.current.shift();
    }
    lastGroup.current = type ? { type, time: now } : undefined;
    future.current = [];
    onTextChange(after.value);
  };

  return {
    fieldRef,
    reset() {
      past.current = [];
      future.current = [];
      beforeInput.current = undefined;
      lastGroup.current = undefined;
    },
    insert(token: string) {
      const field = fieldRef.current;
      if (!field) return;
      field.focus();
      const before = readSelection(field);
      field.setRangeText(token, before.start, before.end, "end");
      record(before, readSelection(field));
    },
    onChange(event: ChangeEvent<HTMLTextAreaElement>) {
      const after = readSelection(event.currentTarget);
      const before = beforeInput.current ?? { value: text, start: after.start, end: after.end };
      const inputType = event.nativeEvent instanceof InputEvent ? event.nativeEvent.inputType : "";
      const grouped =
        /^(insertText|insertCompositionText|deleteContentBackward|deleteContentForward)$/.test(
          inputType,
        );
      record(before, after, grouped ? inputType : undefined);
    },
    onCompositionStart() {
      lastGroup.current = undefined;
    },
    onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
      if (event.nativeEvent.isComposing || event.altKey || (!event.ctrlKey && !event.metaKey))
        return;
      const key = event.key.toLowerCase();
      if (key !== "z" && key !== "y") return;
      event.preventDefault();
      restore(key === "y" || event.shiftKey);
    },
  };
}
