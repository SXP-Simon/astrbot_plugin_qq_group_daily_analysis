/** 将上传内容读取为 Base64；文件名和目标目录由对应业务模块决定。 */
export async function readUploadFile(file: File): Promise<string> {
  if (file.size > 32 * 1024 * 1024) throw new Error("文件不得超过 32 MiB");
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      typeof reader.result === "string"
        ? resolve(reader.result.split(",")[1])
        : reject(new Error("无法读取上传文件"));
    reader.onerror = () => reject(new Error("无法读取上传文件"));
    reader.readAsDataURL(file);
  });
}
